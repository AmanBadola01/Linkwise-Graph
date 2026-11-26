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

import hashlib
import os
import re
import logging
from typing import List, Dict, Any, Optional
import chromadb
from dotenv import load_dotenv

# Load environment configuration
# Load the repo-root .env explicitly (no upward search, which can hit unreadable parent dirs)
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..", ".env"))

# Import domain models
from backend.app.models.document import DocumentSection
from backend.app.core.tenant import get_current_account_id

logger = logging.getLogger("graphrag.vector.store")


def collection_name_for_account(account_id: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_-]", "_", account_id)
    return f"chunks_{safe}"


# One embedded Chroma client per persist dir, shared process-wide. Creating a
# PersistentClient per request re-opened the on-disk store every upload/query.
_CLIENTS: Dict[str, Any] = {}


def _shared_client(persist_dir: str):
    client = _CLIENTS.get(persist_dir)
    if client is None:
        client = chromadb.PersistentClient(path=persist_dir)
        _CLIENTS[persist_dir] = client
    return client


def chunk_storage_id(account_id: str, section: DocumentSection) -> str:
    """Storage ID unique per account + document + section.

    Previously the raw section_id ("chunk_1", "chunk_2", ...) was used, which
    restarts at 1 for every PDF — so uploading a second document overwrote
    the first document's chunks in the same account collection.
    """
    doc_key = hashlib.sha1(section.document_name.encode("utf-8")).hexdigest()[:10]
    return f"{account_id}_{doc_key}_{section.section_id}"


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
        collection_name: Optional[str] = None,
        account_id: Optional[str] = None,
    ):
        self.persist_dir = persist_dir or os.getenv("CHROMA_PERSIST_DIR", "./chroma_data")
        if account_id is not None:
            aid = account_id
        elif collection_name is not None:
            # Explicit collection (e.g. health probe) needs no tenant context.
            aid = "shared"
        else:
            aid = get_current_account_id()
        self.account_id = aid
        self.collection_name = collection_name or collection_name_for_account(aid)

        # Ensure directory exists on local disk
        os.makedirs(self.persist_dir, exist_ok=True)

        # Shared embedded ChromaDB client (one per persist dir, process-wide)
        self.client = _shared_client(self.persist_dir)

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
            ids.append(chunk_storage_id(self.account_id, section))
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
            embeddings=embeddings, # type: ignore
            metadatas=metadatas # type: ignore
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
        return results # type: ignore

    # FUNCTION: Deletes one document's chunks (ingest rollback, BUG-03).
    def delete_by_document(self, document_name: str) -> int:
        existing = self.collection.get(where={"document_name": document_name})
        ids = existing.get("ids", []) if existing else []
        if ids:
            self.collection.delete(ids=ids)
        return len(ids)

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
