# PURPOSE: Dedicated hybrid retrieval service that queries Graph RAG and Vector RAG in parallel and fuses their evidence into a structured FusedContext.
"""
Hybrid Retriever Service
------------------------
Responsible for:
1. Executing dual-track retrieval across both Knowledge Graph (Neo4j) and Vector Store (ChromaDB).
2. Coordinating MultiHopReasoner and GraphRetriever to extract active subgraphs and multi-hop reasoning chains.
3. Coordinating VectorRetriever to fetch semantically relevant paragraph chunks.
4. Aligning entities between graph paths and text chunks.
5. Fusing structural relational facts and detailed textual context into a unified, cited FusedContext.
"""

import logging
from typing import List, Dict, Any, Optional, Set
from backend.app.models.graph import GraphNode, GraphEdge
from backend.app.models.vector import MatchedChunk
from backend.app.models.hybrid import FusedContext
from backend.app.services.graph.graph_retriever import GraphRetriever
from backend.app.services.graph.multihop_reasoner import MultiHopReasoner
from backend.app.services.vector.vector_retriever import VectorRetriever

logger = logging.getLogger("graphrag.hybrid.retriever")


# CLASS: Coordinates parallel retrieval across Graph and Vector engines and fuses their evidence into a unified FusedContext.
class HybridRetriever:
    """
    Coordinates hybrid retrieval:
    - Queries Graph RAG (subgraphs, multi-hop chains, centrality).
    - Queries Vector RAG (dense semantic chunk search).
    - Assembles and returns strongly-typed FusedContext.
    """

    # FUNCTION: Initializes the HybridRetriever with Graph and Vector retrieval services.
    def __init__(
        self,
        graph_retriever: Optional[GraphRetriever] = None,
        multihop_reasoner: Optional[MultiHopReasoner] = None,
        vector_retriever: Optional[VectorRetriever] = None
    ):
        self.graph_retriever = graph_retriever
        self.multihop_reasoner = multihop_reasoner
        self.vector_retriever = vector_retriever or VectorRetriever()

    # FUNCTION: Lazily resolves and returns the GraphRetriever instance.
    def get_graph_retriever(self) -> GraphRetriever:
        if not self.graph_retriever:
            self.graph_retriever = GraphRetriever()
        return self.graph_retriever

    # FUNCTION: Lazily resolves and returns the MultiHopReasoner instance.
    def get_multihop_reasoner(self) -> MultiHopReasoner:
        if not self.multihop_reasoner:
            self.multihop_reasoner = MultiHopReasoner(retriever=self.get_graph_retriever())
        return self.multihop_reasoner

    # FUNCTION: Formats dual graph and vector evidence into a structured, linearized context string with citations.
    def format_fused_context(
        self,
        query: str,
        reasoning_chain: List[str],
        subgraph_nodes: List[GraphNode],
        subgraph_edges: List[GraphEdge],
        matched_chunks: List[MatchedChunk]
    ) -> str:
        blocks: List[str] = []

        # Section 1: Graph Relational Facts
        graph_lines: List[str] = []
        if reasoning_chain:
            graph_lines.append("[Relational Reasoning Path]")
            for step in reasoning_chain:
                graph_lines.append(f"  • {step}")
            graph_lines.append("")

        if subgraph_nodes or subgraph_edges:
            graph_lines.append("[Active Knowledge Graph Subgraph]")
            for n in subgraph_nodes:
                page_str = f" [Page {n.page}]" if n.page else ""
                desc_str = f" - {n.description}" if n.description else ""
                graph_lines.append(f"  • Entity: {n.name} (Type: {n.type}{page_str}){desc_str}")

            for e in subgraph_edges:
                page_str = f" [Page {e.page}]" if e.page else ""
                desc_str = f" - {e.description}" if e.description else ""
                graph_lines.append(f"  • Relationship: ({e.source}) --[{e.type}{page_str}]--> ({e.target}){desc_str}")

        if graph_lines:
            blocks.append("============================================================\n"
                          "SECTION 1: KNOWLEDGE GRAPH RELATIONAL FACTS\n"
                          "============================================================\n" +
                          "\n".join(graph_lines))

        # Section 2: Document Text Paragraphs
        vector_lines: List[str] = []
        if matched_chunks:
            for i, chunk in enumerate(matched_chunks, start=1):
                doc_info = f"Document: {chunk.document_name} | " if chunk.document_name else ""
                vector_lines.append(
                    f"--- [Chunk {i}] ({doc_info}Page {chunk.page_number}, Section: \"{chunk.section_title}\", Relevance: {chunk.score:.2f}) ---\n"
                    f"{chunk.content.strip()}"
                )

        if vector_lines:
            blocks.append("============================================================\n"
                          "SECTION 2: SOURCE DOCUMENT TEXT CHUNKS\n"
                          "============================================================\n" +
                          "\n\n".join(vector_lines))

        return "\n\n".join(blocks)

    # FUNCTION: Executes dual retrieval across Graph and Vector engines and compiles a unified FusedContext.
    def retrieve(
        self,
        query: str,
        top_k_vector: int = 3,
        max_hops_graph: int = 3
    ) -> FusedContext:
        if not query or not query.strip():
            return FusedContext(query=query)

        clean_query = query.strip()
        logger.info(f"Executing Hybrid Retrieval for: '{clean_query}'")

        # Step 1: Branch A - Vector Retrieval (ChromaDB)
        matched_chunks: List[MatchedChunk] = []
        try:
            matched_chunks = self.vector_retriever.retrieve_chunks(
                query=clean_query,
                top_k=top_k_vector
            )
            logger.info(f"Vector Retrieval returned {len(matched_chunks)} chunks")
        except Exception as e:
            logger.error(f"Error during vector retrieval in HybridRetriever: {e}")

        # Step 2: Branch B - Graph Retrieval (Neo4j)
        reasoning_chain: List[str] = []
        subgraph_nodes: List[GraphNode] = []
        subgraph_edges: List[GraphEdge] = []

        try:
            reasoner = self.get_multihop_reasoner()
            # Attempt multi-hop reasoning path discovery
            reasoning_result = reasoner.reason_and_answer(query=clean_query, max_hops=max_hops_graph)

            if reasoning_result and reasoning_result.path_nodes:
                reasoning_chain = reasoning_result.reasoning_chain
                subgraph_nodes = reasoning_result.path_nodes
                subgraph_edges = reasoning_result.path_edges
                logger.info(f"Multi-hop Graph reasoning found {len(subgraph_nodes)} nodes, {len(subgraph_edges)} edges")
            else:
                # Fallback to general 1-2 hop neighborhood subgraph expansion
                graph_retriever = self.get_graph_retriever()
                graph_result = graph_retriever.retrieve(query=clean_query, depth=min(2, max_hops_graph))
                if graph_result and graph_result.subgraph:
                    subgraph_nodes = graph_result.subgraph.nodes
                    subgraph_edges = graph_result.subgraph.edges
                    logger.info(f"Fallback Subgraph retrieval found {len(subgraph_nodes)} nodes, {len(subgraph_edges)} edges")
        except Exception as e:
            logger.error(f"Error during graph retrieval in HybridRetriever: {e}")

        # Step 3: Collect and deduplicate all source pages referenced
        source_pages_set: Set[int] = set()
        for chunk in matched_chunks:
            if chunk.page_number and chunk.page_number > 0:
                source_pages_set.add(chunk.page_number)

        for node in subgraph_nodes:
            if node.page and node.page > 0:
                source_pages_set.add(node.page)

        for edge in subgraph_edges:
            if edge.page and edge.page > 0:
                source_pages_set.add(edge.page)

        source_pages = sorted(list(source_pages_set))

        # Step 4: Build linearized unified text context
        linearized_text = self.format_fused_context(
            query=clean_query,
            reasoning_chain=reasoning_chain,
            subgraph_nodes=subgraph_nodes,
            subgraph_edges=subgraph_edges,
            matched_chunks=matched_chunks
        )

        return FusedContext(
            query=clean_query,
            reasoning_chain=reasoning_chain,
            subgraph_nodes=subgraph_nodes,
            subgraph_edges=subgraph_edges,
            matched_chunks=matched_chunks,
            source_pages=source_pages,
            linearized_text=linearized_text
        )
