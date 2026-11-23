# PURPOSE: Pydantic data models for documents and extracted sections with page-level metadata.
"""
Document Models Module
----------------------
Defines data structures (using Pydantic) for representing documents,
extracted sections, and their source metadata across the GraphRAG pipeline.
"""

from typing import Dict, Any, List
from pydantic import BaseModel, Field


# CLASS: Defines the data schema for a single extracted logical section with metadata and content.
class DocumentSection(BaseModel):
    """
    Represents a single logical section or paragraph extracted from a document.
    """
    section_id: str = Field(
        ...,
        description="Unique identifier for this section, e.g., 'sec_1'"
    )
    document_name: str = Field(
        ...,
        description="Name of the source file, e.g., 'NovaPay Technologies overview.pdf'"
    )
    page_number: int = Field(
        ...,
        description="Page number in the original document where this section appears (1-indexed)"
    )
    section_title: str = Field(
        default="General",
        description="Title or heading of the section (e.g. '2. Leadership')"
    )
    content: str = Field(
        ...,
        description="The actual text content of this section"
    )
    word_count: int = Field(
        default=0,
        description="Number of words in this section"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Optional additional metadata (e.g. byte offset, timestamps)"
    )


# CLASS: Defines the schema for a parsed document holding metadata and its constituent sections.
class ParsedDocument(BaseModel):
    """
    Represents an entire parsed document containing multiple sections.
    """
    document_name: str = Field(
        ...,
        description="Filename of the parsed document"
    )
    total_pages: int = Field(
        ...,
        description="Total number of pages read from the document"
    )
    total_sections: int = Field(
        ...,
        description="Total number of logical sections extracted"
    )
    sections: List[DocumentSection] = Field(
        default_factory=list,
        description="List of all extracted sections ready for entity extraction"
    )
