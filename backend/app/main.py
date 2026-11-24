# PURPOSE: Primary FastAPI application entry point, CORS middleware, lifespan events, and router registration.
"""FastAPI application entry point for Linkwise-Graph."""

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Dict, Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.v1 import (
    health_router,
    graph_router,
    query_router,
    ingest_router,
)

logger = logging.getLogger(__name__)


# FUNCTION: Handles application startup and shutdown lifecycle events.
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manages application startup checks and graceful shutdown cleanup."""
    logger.info("Initializing Linkwise-Graph FastAPI backend...")
    yield
    logger.info("Shutting down Linkwise-Graph FastAPI backend...")


# FUNCTION: Factory function to create and configure the FastAPI application.
def create_app() -> FastAPI:
    """Instantiates and configures the FastAPI application instance."""
    application = FastAPI(
        title="Linkwise-Graph API",
        description="Hybrid GraphRAG and Vector Document Intelligence Platform",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    cors_origins_env = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
    origins = [origin.strip() for origin in cors_origins_env.split(",") if origin.strip()]

    application.add_middleware(
        CORSMiddleware,
        allow_origins=origins if origins else ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(health_router, prefix="/api/v1")
    application.include_router(graph_router, prefix="/api/v1")
    application.include_router(query_router, prefix="/api/v1")
    application.include_router(ingest_router, prefix="/api/v1")

    # FUNCTION: Root endpoint returning platform metadata and interactive documentation link.
    @application.get("/", tags=["Root"])
    async def root() -> Dict[str, Any]:
        """Provides service status, version metadata, and links to interactive API documentation."""
        return {
            "name": "Linkwise-Graph API",
            "version": "1.0.0",
            "status": "operational",
            "docs_url": "/docs",
            "api_v1_endpoints": {
                "health": "/api/v1/health",
                "graph": "/api/v1/graph",
                "query": "/api/v1/query",
                "ingest": "/api/v1/ingest",
            },
        }

    return application


app = create_app()
