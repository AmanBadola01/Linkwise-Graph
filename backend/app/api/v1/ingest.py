# PURPOSE: Document ingestion API endpoint parsing uploaded PDFs, extracting graph entities, and indexing vector embeddings.
"""
Document Ingestion API Module
-----------------------------
Provides:
- POST /api/v1/ingest: End-to-end multi-stage pipeline:
  1. Uploads and saves PDF to temporary disk.
  2. DocumentParser extracts layout and filters repetitive headers/footers.
  3. VectorRetriever indexes text sections into ChromaDB (ONNX all-MiniLM-L6-v2).
  4. EntityExtractor parses structured entities & relationships via Gemini.
  5. NoiseFilter eliminates stopwords, temporal labels, and orphan edges.
  6. EntityResolver deduplicates aliases (RapidFuzz, initial resolution).
  7. GraphBuilder ingests canonical nodes/edges into Neo4j and calculates degrees.
"""

import os
import tempfile
import logging
from typing import List
from fastapi import APIRouter, UploadFile, File, Query, HTTPException
from backend.app.schemas.api_schemas import IngestionResponse
from backend.app.models.graph import ExtractedEntity, ExtractedRelationship
from backend.app.services.graph.document_parser import DocumentParser
from backend.app.services.graph.entity_extractor import EntityExtractor
from backend.app.services.graph.noise_filter import NoiseFilter
from backend.app.services.graph.entity_resolver import EntityResolver
from backend.app.services.graph.graph_builder import GraphBuilder
from backend.app.services.vector.vector_retriever import VectorRetriever
from backend.app.services.vector.vector_store import VectorStore

logger = logging.getLogger("graphrag.api.ingest")

router = APIRouter(prefix="/ingest", tags=["Ingest"])


# FUNCTION: Handles PDF upload, layout parsing, entity extraction, deduplication, Neo4j ingestion, and vector indexing.
@router.post("", response_model=IngestionResponse, summary="Upload and Ingest PDF Document")
async def ingest_document(
    file: UploadFile = File(..., description="PDF document file to process and ingest"),
    clear_existing: bool = Query(
        default=False,
        description="Optionally clear existing Graph and Vector databases prior to ingestion"
    )
) -> IngestionResponse:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Only PDF documents (.pdf) are supported for ingestion."
        )

    logger.info(f"Starting ingestion for file: '{file.filename}' (clear_existing={clear_existing})")

    # Step 1: Write uploaded bytes to a temporary file
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            temp_path = tmp.name
            while chunk := await file.read(1024 * 1024):  # 1MB buffer
                tmp.write(chunk)

        # Optional: Reset existing collections if requested
        if clear_existing:
            logger.info("Clearing existing vector and graph collections as requested")
            v_store = VectorStore()
            v_store.clear()
            g_builder = GraphBuilder()
            g_builder.clear_database()
            g_builder.close()

        # Step 2: Document Parsing & Layout Extraction
        parser = DocumentParser()
        parsed_doc = parser.parse_pdf(temp_path)

        if not parsed_doc.sections:
            raise HTTPException(
                status_code=422,
                detail=f"No readable text sections could be extracted from '{file.filename}'."
            )

        # Update section document names to match uploaded original filename
        for s in parsed_doc.sections:
            s.document_name = file.filename

        logger.info(f"Extracted {len(parsed_doc.sections)} sections across {parsed_doc.total_pages} pages")

        # Step 3: Vector Store Ingestion (ChromaDB + ONNX)
        vector_retriever = VectorRetriever()
        chunks_indexed = vector_retriever.index_sections(parsed_doc.sections)
        logger.info(f"Indexed {chunks_indexed} chunks into ChromaDB")

        # Step 4: Structured Entity & Relationship Extraction (Gemini)
        extractor = EntityExtractor()
        raw_entities: List[ExtractedEntity] = []
        raw_relationships: List[ExtractedRelationship] = []

        for section in parsed_doc.sections:
            extraction = extractor.extract_section(section)
            raw_entities.extend(extraction.entities)
            raw_relationships.extend(extraction.relationships)

        logger.info(f"Extracted {len(raw_entities)} raw entities and {len(raw_relationships)} raw relationships")

        # Step 5: Universal Noise Filtering
        filter_service = NoiseFilter()
        clean_entities, clean_relationships = filter_service.clean_and_filter(
            raw_entities,
            raw_relationships
        )

        # Step 6: Entity Resolution & Alias Rewiring
        resolver = EntityResolver()
        canonical_nodes, rewired_edges, _ = resolver.resolve(
            clean_entities,
            clean_relationships,
            source_doc=file.filename
        )

        # Step 7: Knowledge Graph Ingestion (Neo4j)
        graph_builder = GraphBuilder()
        graph_builder.setup_schema()
        nodes_created = graph_builder.ingest_nodes(canonical_nodes)
        edges_created = graph_builder.ingest_edges(rewired_edges)
        graph_builder.compute_degrees()
        graph_builder.close()

        logger.info(f"Successfully ingested {nodes_created} nodes and {edges_created} relationships into Neo4j")

        return IngestionResponse(
            filename=file.filename,
            status="success",
            sections_parsed=len(parsed_doc.sections),
            nodes_created=nodes_created,
            edges_created=edges_created,
            chunks_indexed=chunks_indexed,
            message=f"Successfully parsed and ingested '{file.filename}' into Knowledge Graph and Vector store."
        )

    except HTTPException:
        raise
    except ConnectionError as e:
        logger.error(f"Database connection error during ingestion: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Database unreachable during ingestion: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error during document ingestion: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Document ingestion failed: {str(e)}"
        )
    finally:
        # Clean up temporary file from local filesystem
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception as e:
                logger.warning(f"Failed to remove temporary file {temp_path}: {e}")
