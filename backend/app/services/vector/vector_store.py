# PURPOSE: Dedicated storage service managing ChromaDB persistent vector collections, upserts, and nearest-neighbor vector queries.
"""
Vector Store Service
--------------------
Manages low-level database operations for ChromaDB:
1. Connects to embedded persistent ChromaDB instance at ./chroma_data.
2. Manages collection lifecycle with HNSW cosine distance metric.
3. Upserts pre-computed text embeddings, raw documents, and chunk metadata.
4. Executes nearest-neighbor vector search given a query embedding.
5. Provides database clearing and count management.
"""

import os
import logging
from typing import List, Dict, Any, Optional
import chromadb
from dotenv import load_dotenv

# Load environment configuration
load_dotenv()

# Import domain models
from backend.app.models.document import DocumentSection

logger = logging.getLogger("graphrag.vector.store")


# CLASS: Encapsulates ChromaDB database operations for storing and querying text embeddings.
class VectorStore:
    """
    Manages storage and raw vector similarity querying in ChromaDB.
    Sole responsibility: Database operations (persist, upsert, query, clear).
    """

    # FUNCTION: Initializes the persistent ChromaDB client and creates or loads the target collection.
    def __init__(
        self,
        persist_dir: Optional[str] = None,
        collection_name: str = "document_chunks"
    ):
        self.persist_dir = persist_dir or os.getenv("CHROMA_PERSIST_DIR", "./chroma_data")
        self.collection_name = collection_name

        # Ensure directory exists on local disk
        os.makedirs(self.persist_dir, exist_ok=True)

        # Initialize embedded persistent ChromaDB client
        self.client = chromadb.PersistentClient(path=self.persist_dir)

        # Get or create collection configured for cosine distance
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}
        )
        print(f" VectorStore connected to ChromaDB at '{self.persist_dir}' (Collection: '{self.collection_name}')")

    # FUNCTION: Upserts pre-embedded DocumentSection chunks and their metadata into ChromaDB.
    def add_sections(
        self,
        sections: List[DocumentSection],
        embeddings: List[List[float]]
    ) -> int:
        if not sections or not embeddings:
            return 0

        if len(sections) != len(embeddings):
            raise ValueError(
                f"Mismatch: Received {len(sections)} sections but {len(embeddings)} embeddings."
            )

        ids: List[str] = []
        documents: List[str] = []
        metadatas: List[Dict[str, Any]] = []

        for section in sections:
            ids.append(section.section_id)
            documents.append(section.content)
            metadatas.append({
                "document_name": section.document_name,
                "page_number": section.page_number,
                "section_title": section.section_title,
                "word_count": section.word_count
            })

        # Upsert documents, embeddings, and metadata into collection
        self.collection.upsert(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas
        )

        return len(sections)

    # FUNCTION: Executes a nearest-neighbor vector search against ChromaDB using a query embedding.
    def search(
        self,
        query_embedding: List[float],
        top_k: int = 3
        ) -> Dict[str, Any]:
        current_count = self.collection.count()
        if current_count == 0:
            return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}

        # Query collection with raw embedding vector
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, current_count)
        )
        return results

    # FUNCTION: Resets the collection by deleting and re-creating it cleanly.
    def clear(self) -> int:
        current_count = self.collection.count()
        self.client.delete_collection(name=self.collection_name)
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}
        )
        return current_count

    # FUNCTION: Returns the total number of chunks currently stored in the collection.
    def count(self) -> int:
        return self.collection.count()
