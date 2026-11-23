# PURPOSE: Pydantic domain models for vector retrieval, matched document chunks, and pure Vector RAG query responses.
"""
Vector Domain Models Module
----------------------------
Defines data structures for:
1. Matched text chunks retrieved from ChromaDB with similarity scores and metadata.
2. Complete VectorRetrievalResult payloads returned by VectorRetriever.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


# CLASS: Represents an individual document paragraph chunk retrieved from the vector database by semantic similarity.
class MatchedChunk(BaseModel):
    chunk_id: str = Field(
        ...,
        description="Unique identifier of the chunk, e.g. 'chunk_3'"
    )
    document_name: str = Field(
        default="",
        description="Source document filename"
    )
    page_number: int = Field(
        default=1,
        description="Page number in original document where this paragraph appears"
    )
    section_title: str = Field(
        default="General",
        description="Title or section heading under which this paragraph belongs"
    )
    content: str = Field(
        ...,
        description="Actual text content of the retrieved paragraph"
    )
    score: float = Field(
        default=0.0,
        description="Cosine similarity score (higher is more relevant, range 0.0 to 1.0)"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional chunk metadata"
    )


# CLASS: Encapsulates the complete result of a pure Vector RAG retrieval and answer synthesis.
class VectorRetrievalResult(BaseModel):
    query: str = Field(
        ...,
        description="The user's original query string"
    )
    answer: str = Field(
        default="",
        description="Synthesized natural language answer produced strictly from retrieved text chunks"
    )
    matched_chunks: List[MatchedChunk] = Field(
        default_factory=list,
        description="Ordered list of top-K most semantically relevant paragraph chunks"
    )
    top_k: int = Field(
        default=3,
        description="Number of chunks requested"
    )
    context_text: str = Field(
        default="",
        description="Linearized text context fed to the LLM for answer synthesis"
    )
