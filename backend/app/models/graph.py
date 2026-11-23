# PURPOSE: Pydantic domain models for graph entities, relationships, and full graph visualization payloads.
"""
Graph Domain Models Module
--------------------------
Defines data structures for:
1. Raw entities & relationships extracted by LLM from text chunks.
2. Canonical nodes & edges stored in Neo4j.
3. Graph payloads sent to the Next.js visualizer.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# CLASS: Represents an individual entity extracted from a text chunk by the LLM.
class ExtractedEntity(BaseModel):
    name: str = Field(
        ...,
        description="Canonical or mentioned name of the entity, e.g., 'Anita Rao', 'PayCore'"
    )
    type: str = Field(
        ...,
        description="Category of the entity, e.g., 'Person', 'Team', 'Product', 'Technology', 'Location', 'Organization'"
    )
    description: str = Field(
        default="",
        description="1-2 sentence description explaining who or what this entity is based on the text"
    )
    source_section: str = Field(
        default="",
        description="ID of the chunk where this entity was found, e.g., 'chunk_3'"
    )
    page_number: int = Field(
        default=1,
        description="PDF page number where this entity was mentioned"
    )


# CLASS: Represents a directed relationship connecting two entities extracted by the LLM.
class ExtractedRelationship(BaseModel):
    source: str = Field(
        ...,
        description="Name of the originating entity, e.g., 'Daniel Kim'"
    )
    target: str = Field(
        ...,
        description="Name of the destination entity, e.g., 'Anita Rao'"
    )
    type: str = Field(
        ...,
        description="Relationship verb in UPPERCASE, e.g., 'REPORTS_TO', 'BUILT_BY', 'DEPENDS_ON'"
    )
    description: str = Field(
        default="",
        description="Brief context explaining the relationship"
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence score between 0.0 and 1.0"
    )
    source_section: str = Field(
        default="",
        description="ID of the chunk where this relationship was stated"
    )
    page_number: int = Field(
        default=1,
        description="PDF page number where this relationship was found"
    )


# CLASS: Container schema for the LLM extraction output of a single text section.
class SectionExtraction(BaseModel):
    entities: List[ExtractedEntity] = Field(
        default_factory=list,
        description="List of all entities discovered in the section"
    )
    relationships: List[ExtractedRelationship] = Field(
        default_factory=list,
        description="List of all relationships discovered in the section"
    )


# CLASS: Represents a canonical graph node stored in Neo4j and rendered on the frontend.
class GraphNode(BaseModel):
    id: str = Field(
        ...,
        description="Unique identifier for the node (usually sanitized lowercase name)"
    )
    name: str = Field(
        ...,
        description="Human-readable display name of the entity"
    )
    type: str = Field(
        ...,
        description="Entity type: Person, Team, Product, Technology, Location, Organization"
    )
    description: str = Field(
        default="",
        description="Summary description of the entity"
    )
    source_doc: str = Field(
        default="",
        description="Filename of the source document"
    )
    page: int = Field(
        default=1,
        description="Page number where entity was introduced"
    )
    degree: int = Field(
        default=0,
        description="Number of connections (used for visual sizing on the frontend canvas)"
    )
    aliases: List[str] = Field(
        default_factory=list,
        description="Known alternative names or aliases resolved to this entity (e.g. ['D. Kim'])"
    )
    community_id: Optional[int] = Field(
        default=None,
        description="Cluster ID assigned by the Louvain community detection algorithm"
    )


# CLASS: Represents a canonical graph edge connecting two nodes in Neo4j and the frontend.
class GraphEdge(BaseModel):
    id: str = Field(
        ...,
        description="Unique edge identifier, e.g., 'e_daniel_reports_to_anita'"
    )
    source: str = Field(
        ...,
        description="Source node ID"
    )
    target: str = Field(
        ...,
        description="Target node ID"
    )
    type: str = Field(
        ...,
        description="Relationship type, e.g., 'REPORTS_TO', 'BUILT_BY'"
    )
    description: str = Field(
        default="",
        description="Human-readable explanation of this connection"
    )
    confidence: float = Field(
        default=1.0,
        description="Confidence score of this relationship"
    )
    source_doc: str = Field(
        default="",
        description="Source document name"
    )
    page: int = Field(
        default=1,
        description="Source page number"
    )


# CLASS: Complete knowledge graph payload ready for frontend visualization.
class FullGraphData(BaseModel):
    nodes: List[GraphNode] = Field(
        default_factory=list,
        description="All canonical nodes in the graph"
    )
    edges: List[GraphEdge] = Field(
        default_factory=list,
        description="All canonical directed edges in the graph"
    )
    total_nodes: int = Field(default=0)
    total_edges: int = Field(default=0)


# CLASS: Encapsulates the complete retrieved graph context and visualization data for a user query.
class GraphRetrievalResult(BaseModel):
    query: str = Field(
        ...,
        description="The user's original query string"
    )
    context_text: str = Field(
        default="",
        description="Linearized facts and relationships formatted with citations for LLM prompt synthesis"
    )
    subgraph: FullGraphData = Field(
        default_factory=FullGraphData,
        description="Active subgraph nodes and edges for dynamic frontend visualizer highlighting"
    )
    seed_entities: List[str] = Field(
        default_factory=list,
        description="Canonical entity names linked from the query"
    )
    cypher_query: Optional[str] = Field(
        default=None,
        description="Cypher query executed during Text2Cypher traversal"
    )
    cypher_results: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Tabular rows returned by Cypher query execution"
    )


# CLASS: Encapsulates the output of multi-hop graph reasoning including paths, reasoning chain, and synthesized answer.
class MultiHopReasoningResult(BaseModel):
    query: str = Field(
        ...,
        description="The user's original query string"
    )
    answer: str = Field(
        default="",
        description="Grounded natural language answer synthesized by the LLM from the traversed reasoning chain"
    )
    reasoning_chain: List[str] = Field(
        default_factory=list,
        description="Ordered step-by-step reasoning statements showing each hop taken across the graph"
    )
    path_nodes: List[GraphNode] = Field(
        default_factory=list,
        description="Ordered sequence of canonical nodes traversed along the reasoning path"
    )
    path_edges: List[GraphEdge] = Field(
        default_factory=list,
        description="Ordered sequence of directed edges traversed along the reasoning path"
    )
    total_hops: int = Field(
        default=0,
        description="Number of graph edges traversed in the primary reasoning path"
    )
