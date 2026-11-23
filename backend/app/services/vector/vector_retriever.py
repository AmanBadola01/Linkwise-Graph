# PURPOSE: Coordinates semantic vector retrieval by embedding natural language queries and querying the VectorStore for matched chunks.
"""
Vector Retriever Service
------------------------
Responsible for:
1. Orchestrating EmbeddingService and VectorStore.
2. Converting natural language search queries into embedding vectors.
3. Querying ChromaDB for nearest neighbor document chunks.
4. Parsing raw vector database outputs into strongly-typed MatchedChunk domain models with similarity scores.
5. Providing document ingestion indexing for DocumentSection collections.
"""

import logging
from typing import List, Optional
from backend.app.models.document import DocumentSection
from backend.app.models.vector import MatchedChunk
from backend.app.services.vector.embedding_service import EmbeddingService
from backend.app.services.vector.vector_store import VectorStore

logger = logging.getLogger("graphrag.vector.retriever")


# CLASS: Orchestrates query embedding and vector search to retrieve relevant document chunks.
class VectorRetriever:
    """
    Coordinates semantic vector search:
    - Encodes queries into embedding vectors via EmbeddingService.
    - Searches VectorStore for nearest neighbor chunks.
    - Converts raw database matches into typed MatchedChunk instances.
    """

    # FUNCTION: Initializes retriever with embedding service and vector store instances.
    def __init__(
        self,
        embedding_service: Optional[EmbeddingService] = None,
        vector_store: Optional[VectorStore] = None
    ):
        self.embedder = embedding_service or EmbeddingService()
        self.store = vector_store or VectorStore()
        logger.info("VectorRetriever initialized with EmbeddingService and VectorStore")

    # FUNCTION: Embeds a list of DocumentSection chunks and indexes them into VectorStore.
    def index_sections(self, sections: List[DocumentSection]) -> int:
        if not sections:
            return 0

        # Extract text content from each section
        texts = [section.content for section in sections]

        # Generate embeddings in batch via EmbeddingService
        embeddings = self.embedder.embed_texts(texts)

        # Upsert sections and pre-computed vectors into VectorStore
        added_count = self.store.add_sections(sections, embeddings)
        logger.info(f"Successfully indexed {added_count} sections into vector store")
        return added_count

    # FUNCTION: Performs semantic vector retrieval for a natural language query and returns ranked MatchedChunks.
    def retrieve_chunks(self, query: str, top_k: int = 3) -> List[MatchedChunk]:
        if not query or not query.strip():
            return []

        # Step 1: Embed query string to vector
        query_vector = self.embedder.embed_text(query.strip())

        # Step 2: Query vector store for nearest neighbors
        raw_results = self.store.search(query_embedding=query_vector, top_k=top_k)

        # Step 3: Unpack raw ChromaDB dictionary into MatchedChunk objects
        matched_chunks: List[MatchedChunk] = []

        ids_list = raw_results.get("ids", [[]])
        docs_list = raw_results.get("documents", [[]])
        metas_list = raw_results.get("metadatas", [[]])
        dists_list = raw_results.get("distances", [[]])

        if not ids_list or not ids_list[0]:
            return []

        chunk_ids = ids_list[0]
        documents = docs_list[0]
        metadatas = metas_list[0]
        distances = dists_list[0]

        for i in range(len(chunk_ids)):
            raw_dist = distances[i] if i < len(distances) else 1.0
            # Convert cosine distance [0, 2] to similarity score [0, 1]
            similarity_score = max(0.0, min(1.0, 1.0 - float(raw_dist)))

            meta = metadatas[i] if i < len(metadatas) and metadatas[i] else {}
            content = documents[i] if i < len(documents) else ""
            chunk_id = chunk_ids[i]

            chunk = MatchedChunk(
                chunk_id=chunk_id,
                document_name=meta.get("document_name", ""),
                page_number=int(meta.get("page_number", 1)),
                section_title=meta.get("section_title", "General"),
                content=content,
                score=round(similarity_score, 4),
                metadata=meta
            )
            matched_chunks.append(chunk)

        # Rank by similarity score descending
        matched_chunks.sort(key=lambda c: c.score, reverse=True)
        return matched_chunks
