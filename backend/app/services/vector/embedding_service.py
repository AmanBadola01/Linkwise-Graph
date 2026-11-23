# PURPOSE: Dedicated service for generating dense text embeddings using local ONNX all-MiniLM-L6-v2 without external API calls.
"""
Embedding Service
-----------------
Responsible solely for converting text strings into mathematical vector representations:
1. Uses local ONNX-accelerated all-MiniLM-L6-v2 model via ChromaDB utilities.
2. Produces 384-dimensional dense float vectors.
3. Completely local, free, and deterministic (runs on CPU with zero network calls).
4. Supports both single-string and high-throughput batch text embedding.
"""

import os
import logging
from typing import List
from chromadb.utils import embedding_functions

logger = logging.getLogger("graphrag.vector.embedding")


# CLASS: Dedicated service to generate text embeddings locally using the all-MiniLM-L6-v2 ONNX model.
class EmbeddingService:
    """
    Encapsulates text embedding generation.
    Sole responsibility: Text in ➔ 384-dimensional vector out.
    """

    # FUNCTION: Initializes the local ONNX embedding model function and sets vector dimension.
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self.dimension = 384

        # Initialize ChromaDB's default local ONNX all-MiniLM-L6-v2 embedding function
        self._embedding_fn = embedding_functions.DefaultEmbeddingFunction()

    # FUNCTION: Generates a 384-dimensional dense vector for a single string of text.
    def embed_text(self, text: str) -> List[float]:
        if not text or not text.strip():
            # Return zero vector for empty input
            return [0.0] * self.dimension

        vectors = self._embedding_fn([text])
        return [float(v) for v in vectors[0]]

    # FUNCTION: Generates a list of 384-dimensional vectors for a batch of text strings.
    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        # Replace empty strings with a single space to prevent model shape mismatches
        sanitized_texts = [t if t and t.strip() else " " for t in texts]
        vectors = self._embedding_fn(sanitized_texts)
        return [[float(val) for val in vec] for vec in vectors]

    # FUNCTION: Returns the mathematical dimensionality of vectors produced by this service.
    def get_dimension(self) -> int:
        return self.dimension
