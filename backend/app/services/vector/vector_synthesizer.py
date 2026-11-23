# PURPOSE: Synthesizes factual, page-cited natural language answers using Gemini grounded strictly in retrieved vector document chunks.
"""
Vector Synthesizer Service
--------------------------
Responsible for:
1. Linearizing retrieved MatchedChunk objects into structured context blocks with page citations.
2. Generating grounded prompt templates enforcing strict factual fidelity and page referencing.
3. Prompting Google Gemini (gemini-3.5-flash-lite) to synthesize natural language answers.
4. Packaging responses into strongly-typed VectorRetrievalResult domain models.
"""

import os
import logging
from typing import List, Optional
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

from backend.app.models.vector import MatchedChunk, VectorRetrievalResult

logger = logging.getLogger("graphrag.vector.synthesizer")


# CLASS: Synthesizes grounded natural language answers from retrieved vector chunks using Google Gemini.
class VectorSynthesizer:
    """
    Synthesizes answers for Vector RAG queries:
    - Formats retrieved chunks into structured context with page numbers.
    - Prompts Gemini with strict anti-hallucination and citation instructions.
    - Produces typed VectorRetrievalResult payloads.
    """

    # FUNCTION: Initializes the synthesizer with Gemini API credentials and model configuration.
    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "models/gemini-3.5-flash-lite"
    ):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model_name = model_name
        self.client = None

        if self.api_key:
            try:
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.error(f"Failed to initialize Google GenAI Client: {e}")
        else:
            logger.warning("GEMINI_API_KEY is not set. Synthesis will operate in fallback mode.")

    # FUNCTION: Linearizes a list of MatchedChunk objects into a formatted string with page citations.
    def format_context(self, chunks: List[MatchedChunk]) -> str:
        if not chunks:
            return ""

        context_blocks = []
        for i, chunk in enumerate(chunks, start=1):
            doc_info = f"Document: {chunk.document_name} | " if chunk.document_name else ""
            block = (
                f"--- [Chunk {i}] ({doc_info}Page {chunk.page_number}, Section: \"{chunk.section_title}\") ---\n"
                f"{chunk.content.strip()}"
            )
            context_blocks.append(block)

        return "\n\n".join(context_blocks)

    # FUNCTION: Prompts Gemini to synthesize a factual answer strictly grounded in the retrieved document chunks.
    def synthesize(
        self,
        query: str,
        matched_chunks: List[MatchedChunk],
        top_k: int = 3
    ) -> VectorRetrievalResult:
        if not query or not query.strip():
            return VectorRetrievalResult(
                query=query,
                answer="No query provided.",
                matched_chunks=[],
                top_k=top_k,
                context_text=""
            )

        if not matched_chunks:
            return VectorRetrievalResult(
                query=query,
                answer="No relevant document sections were found in the vector database to answer this question.",
                matched_chunks=[],
                top_k=top_k,
                context_text=""
            )

        context_text = self.format_context(matched_chunks)

        if not self.client:
            fallback_answer = (
                "Answer synthesis unavailable (GEMINI_API_KEY not configured). "
                f"Retrieved {len(matched_chunks)} relevant sections from pages "
                f"{', '.join(str(c.page_number) for c in matched_chunks)}."
            )
            return VectorRetrievalResult(
                query=query,
                answer=fallback_answer,
                matched_chunks=matched_chunks,
                top_k=top_k,
                context_text=context_text
            )

        prompt = f"""You are an accurate, factual AI assistant performing Retrieval-Augmented Generation (RAG).
Answer the user's question using ONLY the provided document context chunks below.

GUIDELINES:
1. Base your answer strictly on the provided context. Do NOT extrapolate, speculate, or introduce external facts.
2. Always cite the relevant page number(s) in brackets, e.g. [Page 2], [Page 4], whenever referencing facts.
3. If the provided context does not contain enough information to answer the question, state: "The provided document sections do not contain sufficient information to answer this question."
4. Keep the answer direct, professional, and well-structured.

DOCUMENT CONTEXT:
{context_text}

USER QUESTION:
{query}

FACTUAL ANSWER:"""

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=1024,
                )
            )
            answer_text = response.text.strip() if response.text else "Unable to generate answer from context."
        except Exception as e:
            logger.error(f"Error calling Gemini for vector synthesis: {e}")
            answer_text = f"Error during answer synthesis: {str(e)}"

        return VectorRetrievalResult(
            query=query,
            answer=answer_text,
            matched_chunks=matched_chunks,
            top_k=top_k,
            context_text=context_text
        )
