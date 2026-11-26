# PURPOSE: Health check and diagnostic API endpoint monitoring Neo4j, ChromaDB, and Gemini dependencies.
"""
Health Diagnostic Router
------------------------
Provides:
- GET /api/v1/health: Real-time probes for Neo4j, ChromaDB, and Gemini API services.
"""

import os
import logging
from fastapi import APIRouter
from neo4j import GraphDatabase
from dotenv import load_dotenv

# Load the repo-root .env explicitly (no upward search, which can hit unreadable parent dirs)
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..", ".env"))

from backend.app.schemas.api_schemas import HealthResponse, ComponentStatus
from backend.app.services.vector.vector_store import VectorStore

logger = logging.getLogger("graphrag.api.health")

router = APIRouter(prefix="/health", tags=["Health"])


# FUNCTION: Probes Neo4j, ChromaDB, and Gemini API services and returns a structured health status report.
@router.get("", response_model=HealthResponse, summary="Infrastructure Health Check")
async def check_health() -> HealthResponse:
    # 1. Probe Neo4j Graph Database
    neo4j_status = ComponentStatus(status="healthy", details="Connected")
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "password")

    driver = None
    try:
        driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        driver.verify_connectivity()
        with driver.session() as session:
            # Anonymous probe: no tenant data or global counts (BUG-05/22).
            session.run("RETURN 1 AS ok").single()
            neo4j_status.details = "Connected"
    except Exception as e:
        logger.warning(f"Neo4j health check failed: {e}")
        neo4j_status.status = "unreachable"
        # Unauthenticated endpoint: never echo driver errors (hosts/URIs).
        neo4j_status.details = "Connection failed"
    finally:
        if driver:
            driver.close()

    # 2. Probe ChromaDB Vector Database
    chroma_status = ComponentStatus(status="healthy", details="Storage operational")
    try:
        # Explicit collection: VectorStore() without one requires an
        # authenticated tenant context, which a health probe does not have —
        # that made this check report "degraded" permanently.
        store = VectorStore(collection_name="document_chunks")
        store.count()
        chroma_status.details = "Storage operational"
    except Exception as e:
        logger.warning(f"ChromaDB health check failed: {e}")
        chroma_status.status = "degraded"
        chroma_status.details = "Vector store error"

    # 3. Probe Google Gemini API Credentials
    gemini_status = ComponentStatus(status="healthy", details="API key configured")
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        gemini_status.status = "degraded"
        gemini_status.details = "GEMINI_API_KEY environment variable not configured"

    # 4. Overall status aggregation
    overall_status = "healthy"
    if neo4j_status.status != "healthy" or chroma_status.status != "healthy" or gemini_status.status != "healthy":
        overall_status = "degraded"

    return HealthResponse(
        status=overall_status,
        neo4j=neo4j_status,
        chromadb=chroma_status,
        gemini=gemini_status
    )
