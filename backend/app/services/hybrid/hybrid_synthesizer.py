# PURPOSE: Synthesizes grounded, page-cited natural language answers using Gemini from fused Graph and Vector RAG context.
"""
Hybrid Synthesizer Service
--------------------------
Responsible for:
1. Constructing grounded prompt instructions combining Knowledge Graph relational paths and Document text chunks.
2. Prompting Google Gemini (gemini-3.5-flash-lite) with strict anti-hallucination and citation guidelines.
3. Packaging the final cited response, visualizer subgraphs, and source pages into a HybridRetrievalResult.
"""

import os
import logging
from typing import Optional
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

from backend.app.models.hybrid import FusedContext, HybridRetrievalResult

logger = logging.getLogger("graphrag.hybrid.synthesizer")


# CLASS: Synthesizes factual answers with page citations from a FusedContext using Google Gemini.
class HybridSynthesizer:
    """
    Synthesizes answers for Hybrid RAG queries:
    - Ingests FusedContext containing both graph paths and text chunks.
    - Prompts Gemini with strict citation and structural grounding instructions.
    - Returns complete HybridRetrievalResult with frontend visualizer payloads.
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
            logger.warning("GEMINI_API_KEY is not set. HybridSynthesizer operating in fallback mode.")

    # FUNCTION: Prompts Gemini to synthesize a cited answer from a FusedContext and builds the HybridRetrievalResult.
    def synthesize(self, fused_context: FusedContext) -> HybridRetrievalResult:
        if not fused_context or not fused_context.query or not fused_context.query.strip():
            return HybridRetrievalResult(
                query="",
                answer="No query provided."
            )

        query = fused_context.query.strip()

        # Handle empty context gracefully
        if not fused_context.linearized_text.strip():
            return HybridRetrievalResult(
                query=query,
                answer="No relevant graph entities or document sections were found to answer this question.",
                reasoning_chain=fused_context.reasoning_chain,
                subgraph_nodes=fused_context.subgraph_nodes,
                subgraph_edges=fused_context.subgraph_edges,
                matched_chunks=fused_context.matched_chunks,
                source_pages=fused_context.source_pages,
                fused_context=""
            )

        # Handle missing API key fallback
        if not self.client:
            fallback_answer = (
                "Answer synthesis unavailable (GEMINI_API_KEY not configured). "
                f"Retrieved {len(fused_context.subgraph_nodes)} graph entities and "
                f"{len(fused_context.matched_chunks)} document chunks across pages "
                f"{', '.join(str(p) for p in fused_context.source_pages)}."
            )
            return HybridRetrievalResult(
                query=query,
                answer=fallback_answer,
                reasoning_chain=fused_context.reasoning_chain,
                subgraph_nodes=fused_context.subgraph_nodes,
                subgraph_edges=fused_context.subgraph_edges,
                matched_chunks=fused_context.matched_chunks,
                source_pages=fused_context.source_pages,
                fused_context=fused_context.linearized_text
            )

        prompt = f"""You are an accurate, highly capable AI assistant specializing in Hybrid Retrieval-Augmented Generation (Hybrid RAG).
Your goal is to answer the user's question by combining Knowledge Graph relational connections with detailed document text chunks.

GUIDELINES:
1. Base your answer strictly on the provided context below. Do NOT extrapolate, speculate, or introduce external facts.
2. Use SECTION 1 (Knowledge Graph) to accurately trace how entities, people, teams, and systems relate to one another.
3. Use SECTION 2 (Document Chunks) to provide rich textual details, quantitative numbers, and narrative explanations.
4. Always cite the exact source page number(s) in brackets, e.g. [Page 2], [Page 4], whenever referencing facts.
5. If the provided context does not contain enough information to answer the question, state: "The provided context does not contain sufficient information to answer this question."
6. Provide a cohesive, well-structured, and direct response.

EVIDENCE CONTEXT:
{fused_context.linearized_text}

USER QUESTION:
{query}

FACTUAL HYBRID ANSWER:"""

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=1024,
                )
            )
            answer_text = response.text.strip() if response.text else "Unable to generate answer from hybrid context."
        except Exception as e:
            logger.error(f"Error calling Gemini for hybrid synthesis: {e}")
            answer_text = f"Error during answer synthesis: {str(e)}"

        return HybridRetrievalResult(
            query=query,
            answer=answer_text,
            reasoning_chain=fused_context.reasoning_chain,
            subgraph_nodes=fused_context.subgraph_nodes,
            subgraph_edges=fused_context.subgraph_edges,
            matched_chunks=fused_context.matched_chunks,
            source_pages=fused_context.source_pages,
            fused_context=fused_context.linearized_text
        )
