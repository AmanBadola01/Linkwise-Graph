# PURPOSE: Service for executing multi-hop graph path traversals (2-to-4 hops), calculating relational reasoning chains, and synthesizing answers via LLM.
"""
Multi-Hop Graph Reasoner Service
---------------------------------
Solves complex relational questions that span multiple connected entities:
1. Multi-Hop Path Discovery: Executes Cypher queries traversing 2, 3, or 4 hops between entities.
2. Shortest Path Traversal: Finds the most direct relational link connecting two distant concepts.
3. Explicit Reasoning Chains: Formats ordered step-by-step hops with exact page citations.
4. LLM Answer Synthesis: Uses Gemini to synthesize answers strictly grounded in the reasoning chain.
5. Visualizer Path Extraction: Returns ordered sequences of nodes and edges for frontend canvas animation.
"""

import os
import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from neo4j import GraphDatabase, Driver
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Load environment configuration
load_dotenv()

# Import domain models and retriever helper
from backend.app.models.graph import (
    GraphNode,
    GraphEdge,
    FullGraphData,
    MultiHopReasoningResult
)
from backend.app.services.graph.graph_retriever import GraphRetriever

logger = logging.getLogger("graphrag.multihop")


# CLASS: Executes multi-hop graph traversals, traces reasoning chains across connected entities, and synthesizes grounded answers.
class MultiHopReasoner:
    """
    Solves complex multi-hop relational questions across the knowledge graph.
    Operates 100% dynamically without hardcoded entity names or schemas.
    """

    # FUNCTION: Initializes the MultiHopReasoner with Neo4j connection and Gemini client.
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
            logger.error(f"MultiHopReasoner failed to connect to Neo4j: {e}")
            raise ConnectionError(f"Could not connect to Neo4j at {self.uri}: {e}")

        self.client = genai.Client(api_key=self.api_key) if self.api_key else None
        # Reuse GraphRetriever for robust entity linking and full-text search
        self.retriever = GraphRetriever(
            uri=self.uri,
            user=self.user,
            password=self.password,
            api_key=self.api_key,
            model_name=self.model_name
        )

    # FUNCTION: Closes the Neo4j driver connection cleanly.
    def close(self):
        if self.driver:
            self.driver.close()
        if self.retriever:
            self.retriever.close()

    # FUNCTION: Finds all multi-hop paths connecting two entities up to a maximum number of hops.
    def find_connecting_paths(
        self,
        start_entity: str,
        target_entity: str,
        max_hops: int = 3,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        query = f"""
        MATCH (s:Entity), (t:Entity)
        WHERE s.name = $start AND t.name = $target
        MATCH path = (s)-[*1..{max_hops}]-(t)
        RETURN [n IN nodes(path) | {{
                    id: n.id,
                    name: n.name,
                    type: n.type,
                    description: coalesce(n.description, ''),
                    page: coalesce(n.page, 1),
                    aliases: coalesce(n.aliases, [])
               }}] AS nodes,
               [r IN relationships(path) | {{
                    id: coalesce(r.id, startNode(r).name + '_' + type(r) + '_' + endNode(r).name),
                    type: type(r),
                    source: startNode(r).name,
                    target: endNode(r).name,
                    description: coalesce(r.description, ''),
                    confidence: coalesce(r.confidence, 1.0),
                    page: coalesce(r.page, 1)
               }}] AS edges,
               length(path) AS hops
        ORDER BY hops ASC
        LIMIT $limit
        """
        paths: List[Dict[str, Any]] = []
        with self.driver.session() as session:
            result = session.run(query, start=start_entity, target=target_entity, limit=limit)
            for rec in result:
                paths.append({
                    "nodes": rec["nodes"],
                    "edges": rec["edges"],
                    "hops": rec["hops"]
                })
        return paths

    # FUNCTION: Finds the single shortest path connecting two entities in the graph.
    def find_shortest_path(self, start_entity: str, target_entity: str) -> Optional[Dict[str, Any]]:
        query = """
        MATCH (s:Entity), (t:Entity)
        WHERE s.name = $start AND t.name = $target
        MATCH path = shortestPath((s)-[*]-(t))
        RETURN [n IN nodes(path) | {
                    id: n.id,
                    name: n.name,
                    type: n.type,
                    description: coalesce(n.description, ''),
                    page: coalesce(n.page, 1),
                    aliases: coalesce(n.aliases, [])
               }] AS nodes,
               [r IN relationships(path) | {
                    id: coalesce(r.id, startNode(r).name + '_' + type(r) + '_' + endNode(r).name),
                    type: type(r),
                    source: startNode(r).name,
                    target: endNode(r).name,
                    description: coalesce(r.description, ''),
                    confidence: coalesce(r.confidence, 1.0),
                    page: coalesce(r.page, 1)
               }] AS edges,
               length(path) AS hops
        """
        with self.driver.session() as session:
            result = session.run(query, start=start_entity, target=target_entity)
            rec = result.single()
            if rec:
                return {
                    "nodes": rec["nodes"],
                    "edges": rec["edges"],
                    "hops": rec["hops"]
                }
        return None

    # FUNCTION: Discovers multi-hop paths of 2 to 3 hops originating from a list of seed entities.
    def discover_multihop_chains(
        self,
        seed_entities: List[str],
        max_hops: int = 3,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        if not seed_entities:
            return []

        query = f"""
        MATCH path = (s:Entity)-[*2..{max_hops}]-(t:Entity)
        WHERE s.name IN $seeds AND s.name <> t.name
        RETURN [n IN nodes(path) | {{
                    id: n.id,
                    name: n.name,
                    type: n.type,
                    description: coalesce(n.description, ''),
                    page: coalesce(n.page, 1),
                    aliases: coalesce(n.aliases, [])
               }}] AS nodes,
               [r IN relationships(path) | {{
                    id: coalesce(r.id, startNode(r).name + '_' + type(r) + '_' + endNode(r).name),
                    type: type(r),
                    source: startNode(r).name,
                    target: endNode(r).name,
                    description: coalesce(r.description, ''),
                    confidence: coalesce(r.confidence, 1.0),
                    page: coalesce(r.page, 1)
               }}] AS edges,
               length(path) AS hops
        ORDER BY hops ASC
        LIMIT $limit
        """
        paths: List[Dict[str, Any]] = []
        with self.driver.session() as session:
            result = session.run(query, seeds=seed_entities, limit=limit)
            for rec in result:
                paths.append({
                    "nodes": rec["nodes"],
                    "edges": rec["edges"],
                    "hops": rec["hops"]
                })
        return paths

    # FUNCTION: Formats an ordered path of nodes and edges into step-by-step human-readable reasoning hops.
    def format_reasoning_chain(self, path: Dict[str, Any]) -> List[str]:
        chain_steps: List[str] = []
        edges = path.get("edges", [])

        for idx, edge in enumerate(edges, 1):
            src = edge["source"]
            tgt = edge["target"]
            rel = edge["type"]
            page = edge.get("page", 1)
            desc = edge.get("description", "")

            step_text = f"Hop {idx}: ({src}) --[{rel} (Page {page})]--> ({tgt})"
            if desc:
                step_text += f" [Fact: {desc}]"
            chain_steps.append(step_text)

        return chain_steps

    # FUNCTION: Executes multi-hop graph reasoning for a user query and synthesizes a grounded answer with Gemini.
    def reason_and_answer(
        self,
        query: str,
        max_hops: int = 3
    ) -> MultiHopReasoningResult:
        print(f"\n🧠 Executing Multi-Hop Graph Reasoning for: '{query}'...")

        # Step 1: Identify all candidate entities in the query
        linked_entities = self.retriever.link_entities(query)
        fulltext_entities = self.retriever.fulltext_search(query, limit=3)
        candidate_entities = list(dict.fromkeys(linked_entities + fulltext_entities))
        print(f"   • Identified Seed Entities: {candidate_entities}")

        chosen_path: Optional[Dict[str, Any]] = None
        all_candidate_paths: List[Dict[str, Any]] = []

        # Step 2: If 2 or more entities are identified, search for connecting paths between them
        if len(candidate_entities) >= 2:
            e1, e2 = candidate_entities[0], candidate_entities[1]
            print(f"   • Searching connecting paths between '{e1}' and '{e2}'...")
            connecting = self.find_connecting_paths(e1, e2, max_hops=max_hops, limit=3)
            if connecting:
                chosen_path = connecting[0]
                all_candidate_paths.extend(connecting)

        # Step 3: If no pairwise path found or only 1 entity, discover multi-hop chains from seed
        if not chosen_path and candidate_entities:
            print(f"   • Discovering multi-hop chains from seeds: {candidate_entities}...")
            chains = self.discover_multihop_chains(candidate_entities, max_hops=max_hops, limit=5)
            if chains:
                chosen_path = chains[0]
                all_candidate_paths.extend(chains)

        # Step 4: Fallback to general 2-hop neighborhood if no linear path found
        if not chosen_path and candidate_entities:
            subgraph = self.retriever.get_expanded_subgraph(candidate_entities, depth=2)
            if subgraph.nodes:
                path_nodes = [n.model_dump() for n in subgraph.nodes]
                path_edges = [e.model_dump() for e in subgraph.edges]
                chosen_path = {
                    "nodes": path_nodes,
                    "edges": path_edges,
                    "hops": len(path_edges)
                }

        # Step 5: Format the Reasoning Chain
        reasoning_chain: List[str] = []
        path_nodes: List[GraphNode] = []
        path_edges: List[GraphEdge] = []
        total_hops = 0

        if chosen_path:
            reasoning_chain = self.format_reasoning_chain(chosen_path)
            total_hops = chosen_path.get("hops", len(chosen_path.get("edges", [])))

            # Convert to Pydantic objects
            for n in chosen_path.get("nodes", []):
                path_nodes.append(GraphNode(
                    id=n.get("id", f"node_{n.get('name', '').lower()}"),
                    name=n.get("name", ""),
                    type=n.get("type", "Concept"),
                    description=n.get("description", ""),
                    page=int(n.get("page", 1)),
                    aliases=n.get("aliases", [])
                ))

            for e in chosen_path.get("edges", []):
                path_edges.append(GraphEdge(
                    id=e.get("id", f"e_{e.get('source')}_{e.get('type')}_{e.get('target')}"),
                    source=e.get("source", ""),
                    target=e.get("target", ""),
                    type=e.get("type", "RELATED_TO"),
                    description=e.get("description", ""),
                    confidence=float(e.get("confidence", 1.0)),
                    page=int(e.get("page", 1))
                ))

        print(f"   • Traversed {total_hops} hops across {len(path_nodes)} nodes")
        for step in reasoning_chain:
            print(f"     {step}")

        # Step 6: Synthesize final answer using Gemini with the multi-hop reasoning chain
        answer = self._synthesize_answer(query, reasoning_chain, chosen_path)

        return MultiHopReasoningResult(
            query=query,
            answer=answer,
            reasoning_chain=reasoning_chain,
            path_nodes=path_nodes,
            path_edges=path_edges,
            total_hops=total_hops
        )

    # FUNCTION: Prompts Gemini to synthesize a fluent answer based strictly on the traversed multi-hop reasoning chain.
    def _synthesize_answer(
        self,
        query: str,
        reasoning_chain: List[str],
        path_data: Optional[Dict[str, Any]]
    ) -> str:
        if not self.client:
            return "Answer synthesis unavailable: GEMINI_API_KEY is not configured."

        if not reasoning_chain:
            return "No connecting relational path was found in the knowledge graph to answer this question."

        nodes_context = []
        if path_data:
            for n in path_data.get("nodes", []):
                nodes_context.append(f"• {n.get('name')} [{n.get('type')}] (Page {n.get('page', 1)}): {n.get('description', '')}")

        system_instruction = (
            "You are an expert GraphRAG Multi-Hop Reasoning Assistant.\n"
            "Your task is to answer the user's question by following the provided step-by-step Knowledge Graph reasoning chain.\n\n"
            "STRICT RULES:\n"
            "1. Answer ONLY using the facts in the provided reasoning chain and entity descriptions.\n"
            "2. Cite the exact Page Numbers provided in the reasoning chain (e.g. '[Page 1]', '[Page 2]').\n"
            "3. State the step-by-step connection clearly so the user understands the multi-hop reasoning.\n"
            "4. Be concise, direct, and factually rigorous. Do not speculate."
        )

        user_content = (
            f"USER QUESTION: {query}\n\n"
            f"MULTI-HOP REASONING CHAIN:\n" + "\n".join(reasoning_chain) + "\n\n"
            f"ENTITY PROVENANCE:\n" + "\n".join(nodes_context) + "\n\n"
            "Provide the final synthesized answer citing exact pages:"
        )

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=user_content,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.0
                )
            )
            return response.text.strip()
        except Exception as e:
            logger.error(f"Failed to synthesize multi-hop answer: {e}")
            return f"Error synthesizing answer: {e}"
