# PURPOSE: Primary FastAPI application entry point, CORS middleware, lifespan events, and router registration.
"""FastAPI application entry point for Linkwise-Graph."""

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Dict, Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.v1 import (
    auth_router,
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
    # Pre-warm the local embedding model in a thread: its first call loads the
    # ONNX runtime (~6s), which otherwise lands inside the first upload.
    import asyncio

    def _warmup() -> None:
        try:
            from backend.app.services.vector.embedding_service import get_embedding_service

            get_embedding_service().embed_text("warmup")
            logger.info("Embedding model pre-warmed")
        except Exception as e:  # noqa: BLE001 - warmup must never block startup
            logger.warning(f"Embedding warmup skipped: {e}")

    warmup_task = asyncio.create_task(asyncio.to_thread(_warmup))
    yield
    warmup_task.cancel()
    logger.info("Shutting down Linkwise-Graph FastAPI backend...")


# FUNCTION: Factory function to create and configure the FastAPI application.
def create_app() -> FastAPI:
    """Instantiates and configures the FastAPI application instance."""
    # Interactive docs fingerprint the stack: disable them when
    # ENVIRONMENT=production (BUG-22).
    production = os.getenv("ENVIRONMENT", "").lower() == "production"
    application = FastAPI(
        title="Linkwise-Graph API",
        description="Hybrid GraphRAG and Vector Document Intelligence Platform",
        version="1.0.0",
        docs_url=None if production else "/docs",
        redoc_url=None if production else "/redoc",
        openapi_url=None if production else "/openapi.json",
        lifespan=lifespan,
    )

    cors_origins_env = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
    origins = [origin.strip() for origin in cors_origins_env.split(",") if origin.strip()]

    # Fail closed (BUG-21): an empty CORS_ORIGINS must never become a
    # credentialed wildcard. No origins configured -> no CORS headers.
    application.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Any 401 clears the session cookie so the browser stops presenting a
    # dead session to the frontend middleware (BUG-09 loop).
    @application.middleware("http")
    async def clear_session_on_401(request, call_next):
        response = await call_next(request)
        if response.status_code == 401:
            response.delete_cookie(key="lw_session", path="/")
        return response

    application.include_router(health_router, prefix="/api/v1")
    application.include_router(auth_router, prefix="/api/v1")
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
                "auth_signup": "/api/v1/auth/signup",
                "auth_login": "/api/v1/auth/login",
                "auth_logout": "/api/v1/auth/logout",
                "auth_me": "/api/v1/auth/me",
                "auth_change_password": "/api/v1/auth/change-password",
                "graph": "/api/v1/graph",
                "query": "/api/v1/query",
                "ingest": "/api/v1/ingest",
            },
        }

    return application


app = create_app()
