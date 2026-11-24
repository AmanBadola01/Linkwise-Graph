# PURPOSE: Exports v1 API route modules for FastAPI.
"""API v1 package."""
from backend.app.api.v1.health import router as health_router
from backend.app.api.v1.graph import router as graph_router
from backend.app.api.v1.query import router as query_router
from backend.app.api.v1.ingest import router as ingest_router

__all__ = [
    "health_router",
    "graph_router",
    "query_router",
    "ingest_router",
]
