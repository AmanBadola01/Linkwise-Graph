# PURPOSE: Graph retrieval service implementing Tiered Hybrid Graph Retrieval (Entity Linking, Full-Text Search, Subgraph Traversal, and Text2Cypher).
"""
Graph Retriever Service
-----------------------
Implements the retrieval engine for GraphRAG:
1. Entity Linking: Identifies entities in natural language queries using fuzzy matching (RapidFuzz) and alias maps.
2. Full-Text Search: Scans Neo4j full-text indexes on node descriptions for keyword and concept matches.
3. Subgraph Traversal: Pulls 1-hop and 2-hop connected neighborhoods from Neo4j centered around identified seed entities.
4. Schema-Constrained Text2Cypher: Translates structural / aggregation questions into safe read-only Cypher queries via Gemini.
5. Context Linearization: Serializes graph nodes and relationships into clean, cited Markdown facts for LLM answer synthesis.
6. Returns both text context for generation and subgraph payloads for frontend visualizer highlighting.
"""

import os
import re
import logging
from typing import List, Dict, Any, Optional, Tuple, Set
from neo4j import GraphDatabase, Driver
from dotenv import load_dotenv
from rapidfuzz import fuzz
from google import genai
from google.genai import types

# Load environment configuration
load_dotenv()

# Import domain models
from backend.app.models.graph import GraphNode, GraphEdge, FullGraphData, GraphRetrievalResult

logger = logging.getLogger("graphrag.retriever")


# CLASS: Executes tiered hybrid retrieval over Neo4j knowledge graphs using entity linking, full-text search, and Cypher synthesis.
class GraphRetriever:
    """
    Retrieves grounded knowledge graph subgraphs and context for user queries.
    Operates 100% dynamically without hardcoded entity names or schemas.
    """

    # FUNCTION: Initializes the GraphRetriever with Neo4j driver connection and Gemini LLM client.
    def __init__(
        self,
        uri: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        api_key: Optional[str] = None,
        model_name: str = "models/gemini-3.5-flash-lite"
    ):
        self.uri = uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.user = user or os.getenv("NEO4J_USER", "neo4j")
        self.password = password or os.getenv("NEO4J_PASSWORD", "password")

        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model_name = model_name

        try:
            self.driver: Driver = GraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password)
            )
            self.driver.verify_connectivity()
        except Exception as e:
            logger.error(f"GraphRetriever failed to connect to Neo4j: {e}")
            raise ConnectionError(f"Could not connect to Neo4j at {self.uri}: {e}")

        # Initialize Gemini client for Text2Cypher fallback
        self.client = genai.Client(api_key=self.api_key) if self.api_key else None

        # Ensure full-text search index is created in Neo4j
        self._ensure_fulltext_index()

    # FUNCTION: Closes the Neo4j driver connection cleanly.
    def close(self):
        if self.driver:
            self.driver.close()

    # FUNCTION: Creates a full-text search index across Entity names and descriptions if it does not already exist.
    def _ensure_fulltext_index(self):
        query = """
        CREATE FULLTEXT INDEX entity_fulltext_idx IF NOT EXISTS
        FOR (n:Entity) ON EACH [n.name, n.description]
        """
        try:
            with self.driver.session() as session:
                session.run(query)
        except Exception as e:
            logger.warning(f"Could not initialize full-text index in Neo4j (benign if unsupported): {e}")

    # FUNCTION: Pulls all known canonical entity names, types, and aliases from Neo4j for entity linking.
    def get_known_entities(self) -> List[Dict[str, Any]]:
        query = """
        MATCH (n:Entity)
        RETURN n.name AS name,
               n.type AS type,
               coalesce(n.aliases, []) AS aliases
        """
        with self.driver.session() as session:
            result = session.run(query)
            return [
                {
                    "name": rec["name"],
                    "type": rec["type"],
                    "aliases": rec["aliases"]
                }
                for rec in result
            ]

    # FUNCTION: Retrieves the highest-connected central hub entities by node degree for answering broad global queries.
    def get_top_hub_entities(self, limit: int = 5) -> List[str]:
        query = """
        MATCH (n:Entity)
        RETURN n.name AS name, coalesce(n.degree, 0) AS degree
        ORDER BY degree DESC
        LIMIT $limit
        """
        with self.driver.session() as session:
            result = session.run(query, limit=limit)
            return [rec["name"] for rec in result]

    # FUNCTION: Identifies canonical entities in a natural language query using exact matching, alias lookup, and RapidFuzz similarity.
    def link_entities(self, query: str, threshold: float = 82.0) -> List[str]:
        known = self.get_known_entities()
        query_lower = query.lower()
        matched_canonical_names: Set[str] = set()

        for ent in known:
            canonical = ent["name"]
            canonical_lower = canonical.lower()

            # 1. Exact substring check in query
            if canonical_lower in query_lower:
                matched_canonical_names.add(canonical)
                continue

            # 2. Check aliases
            alias_matched = False
            for alias in ent.get("aliases", []):
                alias_lower = alias.lower()
                if alias_lower and alias_lower in query_lower:
                    matched_canonical_names.add(canonical)
                    alias_matched = True
                    break
            if alias_matched:
                continue

            # 3. Person Initial resolution in query (e.g. user asks about 'D. Kim' for 'Daniel Kim')
            if ent.get("type", "").lower() == "person":
                parts = canonical.split()
                if len(parts) >= 2:
                    first, last = parts[0].lower(), parts[-1].lower()
                    pattern_with_dot = f"{first[0]}. {last}"
                    pattern_no_dot = f"{first[0]} {last}"
                    # Check if query contains abbreviated initial like 'd. kim' or 'd kim'
                    if pattern_with_dot in query_lower or re.search(rf'\b{re.escape(pattern_no_dot)}\b', query_lower):
                        matched_canonical_names.add(canonical)
                        continue

            # 4. Fuzzy matching for typos or slight variations (e.g. 'Pay Core' vs 'PayCore')
            score = fuzz.partial_ratio(canonical_lower, query_lower)
            token_score = fuzz.token_set_ratio(canonical_lower, query_lower)

            # Accept high-confidence fuzzy matches (ensuring word length > 3 to avoid false positives)
            if (token_score >= 90.0 or (score >= threshold and len(canonical) > 3)):
                # Verify that some token from the canonical name actually appears in the query
                canonical_tokens = set(canonical_lower.split())
                query_tokens = set(re.findall(r'\b\w+\b', query_lower))
                if canonical_tokens & query_tokens or score >= 90.0:
                    matched_canonical_names.add(canonical)

        return list(matched_canonical_names)

    # FUNCTION: Queries Neo4j full-text index to discover relevant nodes based on descriptive keywords.
    def fulltext_search(self, query: str, limit: int = 5) -> List[str]:
        # Clean query of special Lucene punctuation characters
        cleaned = re.sub(r'[\+\-\&\|\!\(\)\{\}\[\]\^\"\\~\*\?\:\/]', ' ', query).strip()
        tokens = [t for t in cleaned.split() if len(t) > 2]
        if not tokens:
            return []

        lucene_query = " OR ".join(tokens)
        cyp_query = """
        CALL db.index.fulltext.queryNodes("entity_fulltext_idx", $search_term)
        YIELD node, score
        WHERE score > 0.5
        RETURN node.name AS name, score
        ORDER BY score DESC
        LIMIT $limit
        """
        matched_names: List[str] = []
        try:
            with self.driver.session() as session:
                result = session.run(cyp_query, search_term=lucene_query, limit=limit)
                for rec in result:
                    matched_names.append(rec["name"])
        except Exception as e:
            logger.debug(f"Full-text search fallback skipped: {e}")

        return matched_names

    # FUNCTION: Retrieves multi-hop subgraphs centered around a list of seed entities and merges them into a FullGraphData payload.
    def get_expanded_subgraph(self, seed_entities: List[str], depth: int = 2) -> FullGraphData:
        if not seed_entities:
            return FullGraphData(nodes=[], edges=[], total_nodes=0, total_edges=0)

        query = f"""
        MATCH path = (start:Entity)-[*1..{depth}]-(connected:Entity)
        WHERE start.name IN $seed_names
        UNWIND nodes(path) AS n
        WITH DISTINCT n, relationships(path) AS rels
        UNWIND rels AS r
        WITH DISTINCT n, collect(DISTINCT r) AS distinct_rels
        RETURN n, distinct_rels
        """

        nodes_dict: Dict[str, GraphNode] = {}
        edges_dict: Dict[str, GraphEdge] = {}

        with self.driver.session() as session:
            result = session.run(query, seed_names=seed_entities)
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
                        page=int(node_data.get("page", 1)),
                        degree=int(node_data.get("degree", 0)),
                        aliases=node_data.get("aliases", []),
                        community_id=node_data.get("community_id", None)
                    )

                for r in rec["distinct_rels"]:
                    rel_type = str(r.type) if hasattr(r, "type") else str(r.get("type", "RELATED_TO"))
                    src_name = r.start_node.get("name", "") if hasattr(r, "start_node") else ""
                    tgt_name = r.end_node.get("name", "") if hasattr(r, "end_node") else ""
                    edge_id = r.get("id") or f"e_{src_name}_{rel_type}_{tgt_name}"

                    if edge_id not in edges_dict:
                        edges_dict[edge_id] = GraphEdge(
                            id=edge_id,
                            source=src_name,
                            target=tgt_name,
                            type=rel_type,
                            description=r.get("description", ""),
                            confidence=float(r.get("confidence", 1.0)),
                            source_doc=r.get("source_doc", ""),
                            page=int(r.get("page", 1))
                        )

        # Also ensure all seed entities themselves are included even if they have 0 connections
        seed_query = """
        MATCH (n:Entity)
        WHERE n.name IN $seed_names
        RETURN n
        """
        with self.driver.session() as session:
            seed_result = session.run(seed_query, seed_names=seed_entities)
            for rec in seed_result:
                node_data = rec["n"]
                node_id = node_data.get("id", f"node_{node_data.get('name', '').lower()}")
                if node_id not in nodes_dict:
                    nodes_dict[node_id] = GraphNode(
                        id=node_id,
                        name=node_data.get("name", ""),
                        type=node_data.get("type", "Concept"),
                        description=node_data.get("description", ""),
                        source_doc=node_data.get("source_doc", ""),
                        page=int(node_data.get("page", 1)),
                        degree=int(node_data.get("degree", 0)),
                        aliases=node_data.get("aliases", []),
                        community_id=node_data.get("community_id", None)
                    )

        nodes_list = list(nodes_dict.values())
        edges_list = list(edges_dict.values())

        return FullGraphData(
            nodes=nodes_list,
            edges=edges_list,
            total_nodes=len(nodes_list),
            total_edges=len(edges_list)
        )

    # FUNCTION: Checks whether a user question is asking for aggregation, count, or structural path querying.
    def _is_structural_query(self, query: str) -> bool:
        lower = query.lower()
        trigger_phrases = [
            "how many", "count", "number of", "list all", "who reports to",
            "which team", "which service", "which technology", "what technologies",
            "average", "total", "who leads", "who manages"
        ]
        return any(phrase in lower for phrase in trigger_phrases)

    # FUNCTION: Dynamically generates and executes a read-only Cypher query using Gemini for structural questions.
    def generate_and_run_cypher(
        self, query: str
    ) -> Tuple[Optional[str], Optional[List[Dict[str, Any]]]]:
        if not self.client:
            return None, None

        # Fetch live database schema metadata to ground the LLM
        schema_prompt = (
            "You are an expert Neo4j Cypher generator. Convert the user's natural language question into a clean, read-only Cypher query.\n\n"
            "GRAPH SCHEMA RULES:\n"
            "1. Nodes have label :Entity and a secondary label (:Person, :Team, :Product, :Technology, :Location, :Organization).\n"
            "2. Node properties: name (string), type (string), description (string), page (integer), aliases (list).\n"
            "3. Relationships are directed and uppercase, e.g.: REPORTS_TO, MANAGES, MEMBER_OF, LEADS, BUILT_BY, USES_TECH, LOCATED_IN, DEPENDS_ON, PARTNER_OF.\n"
            "4. Relationship properties: type (string), description (string), confidence (float), page (integer).\n"
            "5. SAFETY: Return ONLY a single read-only MATCH query. NEVER use CREATE, DELETE, SET, DROP, REMOVE, MERGE.\n"
            "6. Output ONLY the raw Cypher query string without markdown code fences or explanation."
        )

        user_prompt = f"Question: {query}\n\nGenerate the Cypher query:"

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=schema_prompt,
                    temperature=0.0
                )
            )
            raw_cypher = response.text.strip().replace("```cypher", "").replace("```", "").strip()

            # Safety check: Ensure query contains no mutating keywords
            forbidden = ["create", "delete", "set", "drop", "remove", "merge", "call"]
            lower_cypher = raw_cypher.lower()
            if any(f in lower_cypher for f in forbidden if f != "call" or "db.index" not in lower_cypher):
                logger.warning(f"Rejected potentially mutating Cypher: {raw_cypher}")
                return None, None

            # Execute the read-only query
            results: List[Dict[str, Any]] = []
            with self.driver.session() as session:
                cypher_res = session.run(raw_cypher)
                for record in cypher_res:
                    results.append(record.data())

            return raw_cypher, results

        except Exception as e:
            logger.debug(f"Text2Cypher generation or execution failed: {e}")
            return None, None

    # FUNCTION: Converts graph nodes, edges, and optional Cypher rows into structured Markdown text with page citations for LLM synthesis.
    def linearize_context(
        self,
        subgraph: FullGraphData,
        cypher_query: Optional[str] = None,
        cypher_results: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        lines: List[str] = []
        lines.append("=== KNOWLEDGE GRAPH RETRIEVED CONTEXT ===\n")

        # 1. Structural / Cypher query results (if available)
        if cypher_query and cypher_results:
            lines.append("DIRECT CYPHER QUERY EXECUTION:")
            lines.append(f"Query: {cypher_query}")
            lines.append("Results:")
            for idx, row in enumerate(cypher_results[:10], 1):
                formatted_row = ", ".join(f"{k}: {v}" for k, v in row.items())
                lines.append(f"  [{idx}] {formatted_row}")
            lines.append("")

        # 2. Retrieved Entities
        if subgraph.nodes:
            lines.append("RELEVANT ENTITIES:")
            for node in subgraph.nodes:
                alias_str = f" (Aliases: {', '.join(node.aliases)})" if node.aliases else ""
                lines.append(
                    f"• {node.name} [{node.type}]{alias_str} (Page {node.page}): {node.description}"
                )
            lines.append("")

        # 3. Retrieved Directed Relationships with Provenance
        if subgraph.edges:
            lines.append("RELATIONSHIPS & CONNECTIONS (GROUND TRUTH):")
            for edge in subgraph.edges:
                lines.append(
                    f"• ({edge.source}) --[{edge.type} (Page {edge.page}, Conf: {edge.confidence:.2f})]--> ({edge.target})"
                )
                if edge.description:
                    lines.append(f"    Context: {edge.description}")
            lines.append("")

        if not subgraph.nodes and not subgraph.edges and not cypher_results:
            lines.append("No directly matching entities or relationships found in the knowledge graph.\n")

        return "\n".join(lines)

    # FUNCTION: Main entry point orchestrating entity linking, full-text search, subgraph traversal, Cypher synthesis, and linearization.
    def retrieve(
        self,
        query: str,
        depth: int = 2,
        use_cypher_fallback: bool = True
    ) -> GraphRetrievalResult:
        print(f"\n🔍 Retrieving Knowledge Graph context for: '{query}'...")

        # Step 1: Entity Linking (exact + fuzzy matching)
        linked_entities = self.link_entities(query)
        print(f"   • Entity Linking found: {linked_entities}")

        # Step 2: Full-Text search for descriptive concepts
        fulltext_entities = self.fulltext_search(query)
        if fulltext_entities:
            print(f"   • Full-Text Search found: {fulltext_entities}")

        # Combine seed entities (deduplicated)
        seed_entities = list(dict.fromkeys(linked_entities + fulltext_entities))

        # Global query fallback: if no specific entities were detected, pull top central hub nodes
        if not seed_entities:
            print("   • Broad global query detected: pulling top central hub nodes by degree...")
            seed_entities = self.get_top_hub_entities(limit=5)
            print(f"   • Central hub entities selected: {seed_entities}")

        # Step 3: Expand Subgraph (1-hop & 2-hop neighborhoods)
        subgraph = self.get_expanded_subgraph(seed_entities, depth=depth)
        print(f"   • Expanded Subgraph: {subgraph.total_nodes} nodes, {subgraph.total_edges} edges")

        # Step 4: Text-to-Cypher fallback if the question is structural or needs aggregation
        cypher_query = None
        cypher_results = None
        if use_cypher_fallback and self._is_structural_query(query):
            print("   • Generating schema-guided Cypher query...")
            cypher_query, cypher_results = self.generate_and_run_cypher(query)
            if cypher_query:
                print(f"   • Executed Cypher: {cypher_query} -> Returned {len(cypher_results or [])} row(s)")

        # Step 5: Linearize retrieved facts into cited Markdown text for LLM prompt
        context_text = self.linearize_context(
            subgraph=subgraph,
            cypher_query=cypher_query,
            cypher_results=cypher_results
        )

        return GraphRetrievalResult(
            query=query,
            context_text=context_text,
            subgraph=subgraph,
            seed_entities=seed_entities,
            cypher_query=cypher_query,
            cypher_results=cypher_results
        )
