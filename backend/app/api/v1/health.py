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

load_dotenv()

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
            result = session.run("MATCH (n:Entity) RETURN count(n) AS node_count")
            record = result.single()
            node_count = record["node_count"] if record else 0
            neo4j_status.details = f"Connected ({node_count} nodes in knowledge graph)"
    except Exception as e:
        logger.warning(f"Neo4j health check failed: {e}")
        neo4j_status.status = "unreachable"
        neo4j_status.details = f"Connection failed: {str(e)}"
    finally:
        if driver:
            driver.close()

    # 2. Probe ChromaDB Vector Database
    chroma_status = ComponentStatus(status="healthy", details="Storage operational")
    try:
        store = VectorStore()
        chunk_count = store.count()
        chroma_status.details = f"Active collection ({chunk_count} chunks indexed)"
    except Exception as e:
        logger.warning(f"ChromaDB health check failed: {e}")
        chroma_status.status = "degraded"
        chroma_status.details = f"Vector store error: {str(e)}"

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
