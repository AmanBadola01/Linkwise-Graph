# PURPOSE: API route delivering knowledge graph nodes, relationships, and subgraph neighborhoods for frontend visualizer.
"""
Graph Visualizer API Router
---------------------------
Provides:
- GET /api/v1/graph: Returns all canonical nodes, directed edges, and entity type breakdowns.
  Supports optional focal entity parameter to fetch targeted subgraph neighborhoods.
"""

import logging
from collections import Counter
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from backend.app.schemas.api_schemas import GraphDataResponse
from backend.app.services.graph.graph_builder import GraphBuilder

logger = logging.getLogger("graphrag.api.graph")

router = APIRouter(prefix="/graph", tags=["Graph"])


# FUNCTION: Fetches the complete knowledge graph or an entity-centered subgraph for the interactive visualizer.
@router.get("", response_model=GraphDataResponse, summary="Fetch Knowledge Graph for Visualizer")
async def get_graph_data(
    entity: Optional[str] = Query(
        default=None,
        description="Optional entity name to retrieve a focused subgraph neighborhood"
    ),
    depth: int = Query(
        default=2,
        ge=1,
        le=4,
        description="Traversal depth for focused subgraph extraction"
    )
) -> GraphDataResponse:
    builder = None
    try:
        builder = GraphBuilder()

        # If a focal entity is requested, extract its local neighborhood
        if entity and entity.strip():
            clean_entity = entity.strip()
            logger.info(f"Retrieving subgraph for entity: '{clean_entity}' with depth {depth}")
            graph_data = builder.get_subgraph(entity_name=clean_entity, depth=depth)
        else:
            logger.info("Retrieving full knowledge graph data")
            graph_data = builder.get_full_graph()

        # Compute dynamic entity type distribution histogram
        type_counts = Counter(node.type for node in graph_data.nodes)

        return GraphDataResponse(
            nodes=graph_data.nodes,
            edges=graph_data.edges,
            total_nodes=graph_data.total_nodes,
            total_edges=graph_data.total_edges,
            entity_types=dict(type_counts)
        )
    except ConnectionError as e:
        logger.error(f"Neo4j connection error while fetching graph data: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Knowledge graph database is unreachable. Ensure Neo4j container is running: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error retrieving graph data: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch graph data: {str(e)}"
        )
    finally:
        if builder:
            builder.close()
