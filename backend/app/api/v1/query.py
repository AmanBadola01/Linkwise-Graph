# PURPOSE: Query API endpoint dynamically routing user questions to Vector RAG, Graph RAG, or Hybrid RAG engines.
"""
Query Router API Module
-----------------------
Provides:
- POST /api/v1/query: Dispatches natural language queries to Vector, Graph, or Hybrid engines,
  returning factual cited answers, active subgraph nodes/edges, and source page numbers.
"""

import asyncio
import logging
from typing import List, Set
from typing import Annotated

from fastapi import APIRouter, HTTPException, Depends

from backend.app.api.deps import get_current_user
from backend.app.services.auth.user_store import UserRecord
from backend.app.schemas.api_schemas import QueryRequest, QueryResponse, QueryMode
from backend.app.services.vector import VectorRetriever, VectorSynthesizer
from backend.app.services.graph import MultiHopReasoner, GraphRetriever
from backend.app.services.hybrid import HybridRetriever, HybridSynthesizer
from backend.app.services.llm_errors import SynthesisUnavailableError

logger = logging.getLogger("graphrag.api.query")

router = APIRouter(prefix="/query", tags=["Query"])


def _execute_query_sync(request: QueryRequest) -> QueryResponse:
    """Synchronous dispatch (embedding + Neo4j + Gemini are blocking calls)."""
    clean_query = request.query.strip()
    try:
        # Route 1: Pure Vector RAG Mode
        if request.mode == QueryMode.VECTOR:
            retriever = VectorRetriever()
            synthesizer = VectorSynthesizer()

            matched_chunks = retriever.retrieve_chunks(clean_query, top_k=request.top_k)
            vector_result = synthesizer.synthesize(clean_query, matched_chunks, top_k=request.top_k)

            source_pages = sorted(list({c.page_number for c in matched_chunks if c.page_number and c.page_number > 0}))

            return QueryResponse(
                query=clean_query,
                mode=QueryMode.VECTOR,
                answer=vector_result.answer,
                reasoning_chain=[],
                subgraph_nodes=[],
                subgraph_edges=[],
                matched_chunks=vector_result.matched_chunks,
                source_pages=source_pages,
                effective_top_k=request.top_k,
                effective_max_hops=None,
            )

        # Route 2: Pure Graph RAG Mode
        elif request.mode == QueryMode.GRAPH:
            reasoner = MultiHopReasoner()
            graph_result = reasoner.reason_and_answer(clean_query, max_hops=request.max_hops)

            subgraph_nodes = graph_result.path_nodes
            subgraph_edges = graph_result.path_edges
            reasoning_chain = graph_result.reasoning_chain
            answer = graph_result.answer

            # If no linear path was found, fallback to 1-2 hop neighborhood retrieval
            if not subgraph_nodes:
                graph_retriever = GraphRetriever()
                fallback_result = graph_retriever.retrieve(clean_query, depth=min(2, request.max_hops))
                if fallback_result and fallback_result.subgraph:
                    subgraph_nodes = fallback_result.subgraph.nodes
                    subgraph_edges = fallback_result.subgraph.edges
                    # GraphRetrievalResult has no synthesized answer; keep the reasoner's answer.

            source_pages_set: Set[int] = set()
            for n in subgraph_nodes:
                if n.page and n.page > 0:
                    source_pages_set.add(n.page)
            for e in subgraph_edges:
                if e.page and e.page > 0:
                    source_pages_set.add(e.page)

            return QueryResponse(
                query=clean_query,
                mode=QueryMode.GRAPH,
                answer=answer,
                reasoning_chain=reasoning_chain,
                subgraph_nodes=subgraph_nodes,
                subgraph_edges=subgraph_edges,
                matched_chunks=[],
                source_pages=sorted(list(source_pages_set)),
                effective_top_k=None,
                effective_max_hops=request.max_hops,
            )

        # Route 3: Hybrid RAG Mode (Graph + Vector Combined)
        else:
            hybrid_retriever = HybridRetriever()
            hybrid_synthesizer = HybridSynthesizer()

            fused_context = hybrid_retriever.retrieve(
                query=clean_query,
                top_k_vector=request.top_k,
                max_hops_graph=request.max_hops
            )
            hybrid_result = hybrid_synthesizer.synthesize(fused_context)

            return QueryResponse(
                query=clean_query,
                mode=QueryMode.HYBRID,
                answer=hybrid_result.answer,
                reasoning_chain=hybrid_result.reasoning_chain,
                subgraph_nodes=hybrid_result.subgraph_nodes,
                subgraph_edges=hybrid_result.subgraph_edges,
                matched_chunks=hybrid_result.matched_chunks,
                source_pages=hybrid_result.source_pages,
                effective_top_k=request.top_k,
                effective_max_hops=request.max_hops,
            )

    except SynthesisUnavailableError as e:
        # Friendly, retryable — never a raw provider payload (QA residual).
        logger.error(f"Answer synthesis unavailable: {e}")
        raise HTTPException(
            status_code=503,
            detail=str(e),
            headers={"Retry-After": "15"},
        )
    except ConnectionError as e:
        logger.error(f"Database connection error during query execution: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Underlying database connection failed: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unhandled error during query execution: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Query execution error: {str(e)}"
        )


# FUNCTION: Dispatches a natural language query to the appropriate RAG engine based on requested mode.
@router.post("", response_model=QueryResponse, summary="Execute RAG Query")
async def execute_query(
    request: QueryRequest,
    _user: Annotated[UserRecord, Depends(get_current_user)],
) -> QueryResponse:
    logger.info(f"Received query request: mode='{request.mode}', query='{request.query.strip()}'")
    # Run off the event loop so a slow query does not freeze other endpoints.
    return await asyncio.to_thread(_execute_query_sync, request)
