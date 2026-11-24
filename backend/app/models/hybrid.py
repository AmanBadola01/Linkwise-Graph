# PURPOSE: Pydantic domain models for hybrid retrieval, fused graph-vector context, and full Hybrid RAG query responses.
"""
Hybrid Domain Models Module
----------------------------
Defines data structures for:
1. FusedContext: Intermediate unified payload combining Graph RAG paths and Vector RAG chunks.
2. HybridRetrievalResult: Complete end-to-end response containing cited natural language answer,
   active subgraph nodes/edges for the frontend visualizer, and source page references.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from backend.app.models.graph import GraphNode, GraphEdge
from backend.app.models.vector import MatchedChunk


# CLASS: Encapsulates the fused retrieval data from both Graph and Vector engines prior to LLM synthesis.
class FusedContext(BaseModel):
    query: str = Field(
        ...,
        description="The user's search query string"
    )
    reasoning_chain: List[str] = Field(
        default_factory=list,
        description="Ordered multi-hop reasoning steps discovered from the knowledge graph"
    )
    subgraph_nodes: List[GraphNode] = Field(
        default_factory=list,
        description="Nodes in the active subgraph connecting the focal entities"
    )
    subgraph_edges: List[GraphEdge] = Field(
        default_factory=list,
        description="Directed edges in the active subgraph connecting the focal entities"
    )
    matched_chunks: List[MatchedChunk] = Field(
        default_factory=list,
        description="Top-K semantically relevant document text chunks retrieved from ChromaDB"
    )
    source_pages: List[int] = Field(
        default_factory=list,
        description="Sorted, deduplicated list of page numbers referenced across graph and vector evidence"
    )
    linearized_text: str = Field(
        default="",
        description="Structured textual representation combining graph facts and paragraph chunks for LLM prompting"
    )


# CLASS: Encapsulates the complete result of a Hybrid RAG query including cited synthesis and visualizer subgraphs.
class HybridRetrievalResult(BaseModel):
    query: str = Field(
        ...,
        description="The user's original query string"
    )
    answer: str = Field(
        default="",
        description="Synthesized natural language answer with [Page X] citations grounded in graph and vector context"
    )
    reasoning_chain: List[str] = Field(
        default_factory=list,
        description="Step-by-step reasoning chain traversed across the knowledge graph"
    )
    subgraph_nodes: List[GraphNode] = Field(
        default_factory=list,
        description="Nodes to illuminate and highlight on the frontend interactive 2D graph visualizer"
    )
    subgraph_edges: List[GraphEdge] = Field(
        default_factory=list,
        description="Directed edges to illuminate and animate on the frontend interactive 2D graph visualizer"
    )
    matched_chunks: List[MatchedChunk] = Field(
        default_factory=list,
        description="Top-K vector chunks supporting the textual details of the response"
    )
    source_pages: List[int] = Field(
        default_factory=list,
        description="Sorted, deduplicated list of source page numbers supporting the answer"
    )
    fused_context: str = Field(
        default="",
        description="The linearized context block fed to the LLM for answer synthesis"
    )
