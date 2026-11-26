# PURPOSE: Service to ingest canonical nodes and relationships into Neo4j, manage constraints/indexes, and query graph structures.
"""
Graph Builder Service
---------------------
Manages the lifecycle of graph data in Neo4j:
1. Establishes and manages the official Neo4j Python driver connection.
2. Creates uniqueness constraints and search indexes for performance.
3. Ingests canonical GraphNode instances using Cypher MERGE queries with dynamic type labels.
4. Ingests canonical GraphEdge relationships with typed verbs and confidence scores.
5. Computes and sets node connectivity degrees for visual graph layout sizing.
6. Provides query methods: full graph export (FullGraphData) and entity subgraphs (multi-hop).
7. Fully document-agnostic — operates on any domain models without hardcoded schemas.
"""

import os
import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from neo4j import GraphDatabase, Driver, Session
from dotenv import load_dotenv

# Load environment configuration
# Load the repo-root .env explicitly (no upward search, which can hit unreadable parent dirs)
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..", ".env"))

# Import graph domain models
from backend.app.models.graph import GraphNode, GraphEdge, FullGraphData
from backend.app.core.tenant import get_current_account_id

logger = logging.getLogger("graphrag.builder")

# Shared Neo4j drivers (one per URI+user, process-wide) and accounts whose
# schema is already ensured. Previously every upload/query created a driver,
# paid a verify_connectivity round-trip, and re-ran 4 schema statements.
_DRIVERS: Dict[Tuple[str, str], Driver] = {}
_SCHEMA_DONE: set = set()


def _shared_driver(uri: str, user: str, password: str) -> Driver:
    key = (uri, user)
    driver = _DRIVERS.get(key)
    if driver is None:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        driver.verify_connectivity()
        _DRIVERS[key] = driver
    return driver


# CLASS: Manages Neo4j graph database operations including schema creation, ingestion, degree calculation, and retrieval.
class GraphBuilder:
    """
    Service responsible for building and querying the Knowledge Graph inside Neo4j.
    """

    # FUNCTION: Initializes the GraphBuilder by connecting to Neo4j using credentials from environment variables.
    def __init__(
        self,
        uri: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        account_id: Optional[str] = None,
    ):
        self.account_id = account_id or get_current_account_id()
        self.uri = uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.user = user or os.getenv("NEO4J_USER", "neo4j")
        self.password = password or os.getenv("NEO4J_PASSWORD", "password")

        try:
            self.driver: Driver = _shared_driver(self.uri, self.user, self.password)
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j at {self.uri}: {e}")
            raise ConnectionError(
                f"Could not connect to Neo4j at {self.uri}. "
                f"Ensure your Docker container 'graphrag-neo4j' is running: {e}"
            )

    # FUNCTION: No-op — the driver is shared process-wide and stays open.
    def close(self):
        return None

    # FUNCTION: Creates unique constraints and performance indexes on node properties.
    def setup_schema(self):
        # Ensured once per account per process, not on every upload.
        if self.account_id in _SCHEMA_DONE:
            return
        queries = [
            # Migrate pre-tenancy nodes (BUG-02): legacy rows have
            # account_id IS NULL and belong to no account. Quarantine them
            # under a sentinel account so they neither collide with nor leak
            # into any real tenant's graph.
            """
            MATCH (n:Entity) WHERE n.account_id IS NULL
            SET n.account_id = 'legacy-unassigned'
            """,
            # Legacy pre-tenancy constraint on (id) alone: superseded by the
            # composite below. Left in place it made any re-upload crash —
            # MERGE on (id, account_id) could not match pre-tenancy nodes
            # (account_id IS NULL) and the CREATE then violated (id) UNIQUE,
            # failing the whole ingest after all Gemini work was done.
            "DROP CONSTRAINT entity_id_unique IF EXISTS",
            # Composite uniqueness per account (multi-tenant)
            """
            CREATE CONSTRAINT entity_account_id_unique IF NOT EXISTS
            FOR (e:Entity) REQUIRE (e.account_id, e.id) IS UNIQUE
            """,
            """
            CREATE INDEX entity_account_id_idx IF NOT EXISTS
            FOR (e:Entity) ON (e.account_id)
            """,
            # Index: Fast lookups by entity canonical name
            """
            CREATE INDEX entity_name_idx IF NOT EXISTS
            FOR (e:Entity) ON (e.name)
            """,
            # Index: Fast lookups and filtering by entity type
            """
            CREATE INDEX entity_type_idx IF NOT EXISTS
            FOR (e:Entity) ON (e.type)
            """
        ]

        with self.driver.session() as session:
            for query in queries:
                session.run(query).consume()
        _SCHEMA_DONE.add(self.account_id)

    # FUNCTION: Ingests canonical nodes with one UNWIND query per type label.
    def ingest_nodes(self, nodes: List[GraphNode]) -> int:
        if not nodes:
            return 0
        by_label: Dict[str, List[Dict[str, Any]]] = {}
        for node in nodes:
            # Sanitize entity type to use as a valid secondary Cypher label (e.g. :Person, :Product)
            sanitized_label = re.sub(r'[^a-zA-Z0-9]', '', node.type.strip().capitalize()) or "Concept"
            by_label.setdefault(sanitized_label, []).append({
                "id": node.id, "name": node.name, "type": node.type,
                "description": node.description, "source_doc": node.source_doc,
                "page": node.page, "aliases": node.aliases,
            })

        ingested_count = 0
        with self.driver.session() as session:
            for label, rows in by_label.items():
                query = f"""
                UNWIND $rows AS row
                MERGE (n:Entity {{id: row.id, account_id: $account_id}})
                SET n:{label},
                    n.name = row.name,
                    n.type = row.type,
                    n.description = row.description,
                    n.source_doc = row.source_doc,
                    n.page = row.page,
                    n.aliases = row.aliases,
                    n.community_id = null,
                    n.account_id = $account_id
                RETURN count(n) AS written
                """
                record = session.run(query, rows=rows, account_id=self.account_id).single()
                ingested_count += int(record["written"]) if record else 0
        return ingested_count

    # FUNCTION: Ingests directed relationships with one UNWIND query per type.
    def ingest_edges(self, edges: List[GraphEdge]) -> int:
        if not edges:
            return 0
        by_type: Dict[str, List[Dict[str, Any]]] = {}
        for edge in edges:
            # Sanitize relationship type for Cypher syntax (e.g. REPORTS_TO, BUILT_BY)
            sanitized_rel_type = re.sub(r'[^A-Z0-9_]', '_', edge.type.strip().upper()) or "RELATED_TO"
            by_type.setdefault(sanitized_rel_type, []).append({
                "id": edge.id, "source": edge.source, "target": edge.target,
                "type": sanitized_rel_type, "description": edge.description,
                "confidence": edge.confidence, "source_doc": edge.source_doc, "page": edge.page,
            })

        ingested_count = 0
        with self.driver.session() as session:
            for rel_type, rows in by_type.items():
                query = f"""
                UNWIND $rows AS row
                MATCH (s:Entity {{name: row.source, account_id: $account_id}})
                MATCH (t:Entity {{name: row.target, account_id: $account_id}})
                MERGE (s)-[r:{rel_type}]->(t)
                SET r.id = row.id,
                    r.type = row.type,
                    r.description = row.description,
                    r.confidence = row.confidence,
                    r.source_doc = row.source_doc,
                    r.page = row.page
                RETURN count(r) AS written
                """
                record = session.run(query, rows=rows, account_id=self.account_id).single()
                ingested_count += int(record["written"]) if record else 0
        return ingested_count

    # FUNCTION: Calculates and updates the connection degree on all nodes for graph visualizer sizing.
    def compute_degrees(self) -> int:
        print(" Calculating node connectivity degrees...")
        query = """
        MATCH (n:Entity {account_id: $account_id})
        OPTIONAL MATCH (n)-[r]-()
        WITH n, count(r) AS degree
        SET n.degree = degree
        RETURN count(n) AS updated_count
        """

        with self.driver.session() as session:
            result = session.run(query, account_id=self.account_id)
            record = result.single()
            count = record["updated_count"] if record else 0

        print(f" Updated degrees for {count} nodes.")
        return count

    # FUNCTION: High-level pipeline method that creates schema, ingests nodes and edges, and computes degrees.
    def build_graph(self, nodes: List[GraphNode], edges: List[GraphEdge]) -> Dict[str, int]:
        print("\n" + "=" * 80)
        print("🏗️  BUILDING NEO4J KNOWLEDGE GRAPH")
        print("=" * 80)

        # Step 1: Ensure constraints and indexes are in place
        self.setup_schema()

        # Step 2: Insert canonical nodes
        nodes_created = self.ingest_nodes(nodes)

        # Step 3: Insert directed relationships
        edges_created = self.ingest_edges(edges)

        # Step 4: Calculate degree centrality for visual rendering
        nodes_updated = self.compute_degrees()

        print("=" * 80)
        print(f" Graph Build Complete: {nodes_created} nodes, {edges_created} edges in Neo4j.\n")

        return {
            "nodes_ingested": nodes_created,
            "edges_ingested": edges_created,
            "nodes_updated": nodes_updated
        }

    # FUNCTION: Retrieves the full knowledge graph from Neo4j formatted as a FullGraphData payload for the visualizer.
    def get_full_graph(self) -> FullGraphData:
        nodes: List[GraphNode] = []
        edges: List[GraphEdge] = []

        with self.driver.session() as session:
            # Query all canonical nodes
            node_result = session.run(
                """
                MATCH (n:Entity {account_id: $account_id})
                RETURN n.id AS id,
                       n.name AS name,
                       n.type AS type,
                       coalesce(n.description, '') AS description,
                       coalesce(n.source_doc, '') AS source_doc,
                       coalesce(n.page, 1) AS page,
                       coalesce(n.degree, 0) AS degree,
                       coalesce(n.aliases, []) AS aliases,
                       n.community_id AS community_id
                """,
                account_id=self.account_id,
            )

            for rec in node_result:
                nodes.append(GraphNode(
                    id=rec["id"],
                    name=rec["name"],
                    type=rec["type"],
                    description=rec["description"],
                    source_doc=rec["source_doc"],
                    page=rec["page"],
                    degree=rec["degree"],
                    aliases=rec["aliases"],
                    community_id=rec["community_id"]
                ))

            # Query all directed edges
            edge_result = session.run(
                """
                MATCH (s:Entity {account_id: $account_id})-[r]->(t:Entity {account_id: $account_id})
                RETURN coalesce(r.id, s.id + '_' + type(r) + '_' + t.id) AS id,
                       s.name AS source,
                       t.name AS target,
                       type(r) AS type,
                       coalesce(r.description, '') AS description,
                       coalesce(r.confidence, 1.0) AS confidence,
                       coalesce(r.source_doc, '') AS source_doc,
                       coalesce(r.page, 1) AS page
                """,
                account_id=self.account_id,
            )

            for rec in edge_result:
                edges.append(GraphEdge(
                    id=rec["id"],
                    source=rec["source"],
                    target=rec["target"],
                    type=rec["type"],
                    description=rec["description"],
                    confidence=rec["confidence"],
                    source_doc=rec["source_doc"],
                    page=rec["page"]
                ))

        return FullGraphData(
            nodes=nodes,
            edges=edges,
            total_nodes=len(nodes),
            total_edges=len(edges)
        )

    # FUNCTION: Extracts a multi-hop subgraph neighborhood centered around a specific entity name.
    def get_subgraph(self, entity_name: str, depth: int = 2) -> FullGraphData:
        nodes_dict: Dict[str, GraphNode] = {}
        edges: List[GraphEdge] = []

        query = f"""
        MATCH path = (start:Entity {{name: $name, account_id: $account_id}})-[*1..{depth}]-(connected:Entity)
        WHERE all(x IN nodes(path) WHERE x.account_id = $account_id)
        UNWIND nodes(path) AS n
        WITH DISTINCT n, relationships(path) AS rels
        UNWIND rels AS r
        WITH DISTINCT n, collect(DISTINCT r) AS distinct_rels
        RETURN n, distinct_rels
        """

        with self.driver.session() as session:
            result = session.run(query, name=entity_name, account_id=self.account_id)

            for rec in result:
                node_data = rec["n"]
                node_id = node_data.get("id", f"node_{node_data.get('name', '').lower()}")

                if node_id not in nodes_dict:
                    nodes_dict[node_id] = GraphNode(
                        id=node_id,
                        name=node_data.get("name", ""),
                        type=node_data.get("type", "Concept"),
                        description=node_data.get("description", ""),
                        source_doc=node_data.get("source_doc", ""),
                        page=node_data.get("page", 1),
                        degree=node_data.get("degree", 0),
                        aliases=node_data.get("aliases", []),
                        community_id=node_data.get("community_id", None)
                    )

                for r in rec["distinct_rels"]:
                    # Safely extract relationship endpoints and type string
                    rel_type = str(r.type) if hasattr(r, "type") else str(r.get("type", "RELATED_TO"))
                    src_name = r.start_node.get("name", "") if hasattr(r, "start_node") else ""
                    tgt_name = r.end_node.get("name", "") if hasattr(r, "end_node") else ""
                    edge_id = r.get("id") or f"e_{src_name}_{rel_type}_{tgt_name}"

                    edges.append(GraphEdge(
                        id=edge_id,
                        source=src_name,
                        target=tgt_name,
                        type=rel_type,
                        description=r.get("description", ""),
                        confidence=float(r.get("confidence", 1.0)),
                        source_doc=r.get("source_doc", ""),
                        page=int(r.get("page", 1))
                    ))

        # Deduplicate edges by id
        unique_edges = list({e.id: e for e in edges}.values())

        return FullGraphData(
            nodes=list(nodes_dict.values()),
            edges=unique_edges,
            total_nodes=len(nodes_dict),
            total_edges=len(unique_edges)
        )

    # FUNCTION: Removes one document's nodes (ingest rollback, BUG-03).
    def delete_by_source_doc(self, source_doc: str) -> int:
        query = """
        MATCH (n:Entity {account_id: $account_id, source_doc: $source_doc})
        DETACH DELETE n
        RETURN count(n) AS deleted
        """
        with self.driver.session() as session:
            record = session.run(query, account_id=self.account_id, source_doc=source_doc).single()
        return int(record["deleted"]) if record else 0

    # FUNCTION: Completely clears all nodes and relationships from the Neo4j database.
    def clear_database(self) -> int:
        print(f"Clearing graph data for account {self.account_id}...")
        query = "MATCH (n:Entity {account_id: $account_id}) DETACH DELETE n"
        with self.driver.session() as session:
            session.run(query, account_id=self.account_id)
        print(" Account graph cleared successfully.")
        return 0
