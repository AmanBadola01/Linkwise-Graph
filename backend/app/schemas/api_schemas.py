# PURPOSE: Defines Pydantic request and response schemas for all FastAPI REST API endpoints.
"""
API Schemas Module
------------------
Defines HTTP request and response models for:
1. POST /api/v1/query (QueryRequest, QueryResponse, QueryMode)
2. GET /api/v1/graph (GraphDataResponse)
3. POST /api/v1/ingest (IngestionResponse)
4. GET /api/v1/health (HealthResponse, ComponentStatus)
"""

from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from backend.app.models.graph import GraphNode, GraphEdge
from backend.app.models.vector import MatchedChunk


# CLASS: Enumeration of supported RAG query execution modes.
class QueryMode(str, Enum):
    VECTOR = "vector"
    GRAPH = "graph"
    HYBRID = "hybrid"


# CLASS: Request payload schema for natural language query execution across RAG engines.
class QueryRequest(BaseModel):
    query: str = Field(
        ...,
        min_length=1,
        description="The natural language question or search query",
        examples=["What are the primary operational responsibilities and system dependencies?"]
    )
    mode: QueryMode = Field(
        default=QueryMode.HYBRID,
        description="RAG retrieval mode to execute: 'vector', 'graph', or 'hybrid'"
    )
    top_k: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Number of relevant document text chunks to retrieve"
    )
    max_hops: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Maximum graph traversal hop depth for multi-hop relational reasoning"
    )


# CLASS: Unified response payload containing cited answer, source pages, and active subgraph for visualizer.
class QueryResponse(BaseModel):
    query: str = Field(
        ...,
        description="Original query submitted by the user"
    )
    mode: QueryMode = Field(
        ...,
        description="Execution mode used to generate this response"
    )
    answer: str = Field(
        ...,
        description="Synthesized natural language answer with bracketed [Page X] citations"
    )
    reasoning_chain: List[str] = Field(
        default_factory=list,
        description="Step-by-step relational hops discovered from the knowledge graph"
    )
    subgraph_nodes: List[GraphNode] = Field(
        default_factory=list,
        description="Nodes in the active subgraph to illuminate on the frontend 2D visualizer canvas"
    )
    subgraph_edges: List[GraphEdge] = Field(
        default_factory=list,
        description="Directed relationships in the active subgraph to highlight and animate"
    )
    matched_chunks: List[MatchedChunk] = Field(
        default_factory=list,
        description="Top-K vector text chunks supporting the response"
    )
    source_pages: List[int] = Field(
        default_factory=list,
        description="Sorted list of unique page numbers cited in the response"
    )


# CLASS: Response payload delivering full knowledge graph data for the frontend force-directed visualizer.
class GraphDataResponse(BaseModel):
    nodes: List[GraphNode] = Field(
        default_factory=list,
        description="All canonical graph entities in the knowledge graph"
    )
    edges: List[GraphEdge] = Field(
        default_factory=list,
        description="All directed relationships connecting canonical entities"
    )
    total_nodes: int = Field(
        default=0,
        description="Total node count"
    )
    total_edges: int = Field(
        default=0,
        description="Total edge count"
    )
    entity_types: Dict[str, int] = Field(
        default_factory=dict,
        description="Breakdown of entity counts by category type (e.g. Person, Service, Team)"
    )


# CLASS: Response payload detailing the outcome and metrics of a document ingestion pipeline run.
class IngestionResponse(BaseModel):
    filename: str = Field(
        ...,
        description="Name of the processed document file"
    )
    status: str = Field(
        ...,
        description="Ingestion execution status: 'success' or 'error'"
    )
    sections_parsed: int = Field(
        default=0,
        description="Total document sections extracted by DocumentParser"
    )
    nodes_created: int = Field(
        default=0,
        description="Canonical entities ingested into Neo4j"
    )
    edges_created: int = Field(
        default=0,
        description="Directed relationships ingested into Neo4j"
    )
    chunks_indexed: int = Field(
        default=0,
        description="Vector chunks embedded and indexed into ChromaDB"
    )
    message: str = Field(
        default="",
        description="Human-readable result summary message"
    )


# CLASS: Health status report for an individual system dependency.
class ComponentStatus(BaseModel):
    status: str = Field(
        ...,
        description="Component status: 'healthy', 'degraded', or 'unreachable'"
    )
    details: Optional[str] = Field(
        default=None,
        description="Diagnostic details, metrics, or error message"
    )


# CLASS: Global application health report checking Neo4j, ChromaDB, and Gemini API services.
class HealthResponse(BaseModel):
    status: str = Field(
        ...,
        description="Overall platform status: 'healthy' or 'degraded'"
    )
    neo4j: ComponentStatus = Field(
        ...,
        description="Neo4j graph database connectivity status"
    )
    chromadb: ComponentStatus = Field(
        ...,
        description="ChromaDB persistent vector store status"
    )
    gemini: ComponentStatus = Field(
        ...,
        description="Google Gemini LLM API client status"
    )
