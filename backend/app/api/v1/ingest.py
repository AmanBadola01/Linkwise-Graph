# PURPOSE: Document ingestion API endpoint parsing uploaded PDFs, extracting graph entities, and indexing vector embeddings.
"""
Document Ingestion API Module
-----------------------------
Pipeline (all synchronous work runs in a worker thread via asyncio.to_thread):
  1. Stream upload to a temp file with a server-side size cap, hashing bytes.
  2. Content-hash dedupe: identical re-uploads return the stored result.
  3. Parse first — corrupt/empty PDFs are 422 and nothing is cleared/indexed.
  4. Optional clear_existing (only after the new file parses successfully).
  5. Gemini extraction (batched), noise filter, entity resolution.
  6. Neo4j ingest, then vector indexing last. Any failure rolls back this
     document's graph nodes + vector chunks, so a failed ingest is truthful:
     it leaves no queryable partial data (BUG-03).
"""

import asyncio
import hashlib
import os
import tempfile
import time
import logging
from typing import Annotated

from fastapi import APIRouter, UploadFile, File, Query, HTTPException, Depends
from pypdf.errors import PdfReadError

from backend.app.api.deps import get_current_user
from backend.app.services.auth.user_store import UserRecord
from backend.app.schemas.api_schemas import IngestionResponse
from backend.app.services.graph.document_parser import DocumentParser
from backend.app.services.graph.entity_extractor import EntityExtractor
from backend.app.services.graph.noise_filter import NoiseFilter
from backend.app.services.graph.entity_resolver import EntityResolver
from backend.app.services.graph.graph_builder import GraphBuilder
from backend.app.services.ingest_registry import clear_ingests, get_ingest_result, record_ingest
from backend.app.services.vector.vector_retriever import VectorRetriever
from backend.app.services.vector.vector_store import VectorStore

logger = logging.getLogger("graphrag.api.ingest")

router = APIRouter(prefix="/ingest", tags=["Ingest"])

MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_MB", "50")) * 1024 * 1024

# SECURITY (malware scan 2026-11-25): uploads previously got no active-content
# check at all - only the .pdf name and byte size. Reject PDFs carrying
# script, embedded files, launch actions, or forms that can phone home;
# pypdf resolves object streams, so walking the parsed object tree also
# sees keys hidden by compression.
_ACTIVE_PDF_KEYS = {"/JavaScript", "/JS", "/EmbeddedFile", "/EmbeddedFiles", "/Launch", "/RichMedia", "/XFA"}


def find_active_pdf_content(temp_path: str) -> list[str]:
    """Return active-content keys found in the PDF object tree ([] = clean)."""
    from pypdf import PdfReader

    try:
        reader = PdfReader(temp_path)
    except Exception:  # noqa: BLE001 - unparseable: the parser step 422s it
        return []
    found: set[str] = set()
    seen: set[int] = set()

    def walk(obj: object) -> None:
        try:
            resolved = obj.get_object()  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            resolved = obj
        if id(resolved) in seen:
            return
        seen.add(id(resolved))
        if isinstance(resolved, dict):
            for key, value in resolved.items():
                if str(key) in _ACTIVE_PDF_KEYS:
                    found.add(str(key))
                walk(value)
        elif isinstance(resolved, (list, tuple)):
            for item in resolved:
                walk(item)

    try:
        walk(reader.trailer["/Root"])
        for page in reader.pages:
            walk(page)
    except Exception:  # noqa: BLE001 - best-effort scan; parse step validates
        pass
    return sorted(found)


def _run_ingestion(
    temp_path: str, filename: str, clear_existing: bool, account_id: str, sha256: str
) -> IngestionResponse:
    """The whole synchronous pipeline. Runs in a worker thread."""
    timings: dict[str, float] = {}

    def stage(name: str, started: float) -> None:
        timings[name] = time.monotonic() - started

    # Dedupe (BUG-14): same bytes from the same account return the prior
    # result — no Gemini re-billing. clear_existing forces a fresh run.
    if not clear_existing:
        cached = get_ingest_result(account_id, sha256)
        if cached:
            logger.info("Ingest dedupe hit for '%s' (sha256=%s…)", filename, sha256[:12])
            return IngestionResponse(**cached)

    # Step 0: Active-content (malware) check before any parsing/indexing.
    active = find_active_pdf_content(temp_path)
    if active:
        logger.warning("Rejected PDF '%s' with active content: %s", filename, ", ".join(active))
        raise HTTPException(
            status_code=422,
            detail="File rejected: PDF contains active or embedded content "
            f"({', '.join(active)}), which is not allowed. Please upload a plain text-based PDF.",
        )

    # Step 1: Parse first. Nothing is cleared or indexed before this succeeds,
    # so clear_existing + a corrupt file cannot destroy existing data (BUG-04)
    # and bad files are a clean 422 without library internals (BUG-10).
    t0 = time.monotonic()
    try:
        parsed_doc = DocumentParser().parse_pdf(temp_path)
    except (PdfReadError, ValueError, OSError) as e:
        logger.warning("Unparseable PDF '%s': %s", filename, e)
        raise HTTPException(
            status_code=422,
            detail="File is not a readable PDF. Please upload a valid, text-based PDF.",
        ) from e
    stage("parse", t0)

    if not parsed_doc.sections:
        raise HTTPException(
            status_code=422,
            detail=f"No readable text could be extracted from '{filename}'. Scanned/image-only PDFs are not supported.",
        )

    for s in parsed_doc.sections:
        s.document_name = filename
    logger.info(f"Extracted {len(parsed_doc.sections)} sections across {parsed_doc.total_pages} pages")

    # Step 2: Optional clear — only after the new document parsed OK.
    if clear_existing:
        logger.info("Clearing existing vector and graph collections as requested")
        VectorStore().clear()
        g_builder = GraphBuilder()
        g_builder.clear_database()
        g_builder.close()
        clear_ingests(account_id)

    graph_builder: GraphBuilder | None = None
    wrote_graph = False
    wrote_vectors = False
    try:
        # Step 3: Gemini extraction (batched, concurrent, model fallback)
        t0 = time.monotonic()
        extractor = EntityExtractor()
        raw_entities, raw_relationships, failed_sections = extractor.extract_from_sections(parsed_doc.sections)
        stage("gemini_extract", t0)
        if failed_sections:
            logger.warning(f"{failed_sections} section(s) failed Gemini extraction and were skipped")
        logger.info(f"Extracted {len(raw_entities)} raw entities and {len(raw_relationships)} raw relationships")

        # Step 4: Noise filtering + entity resolution
        t0 = time.monotonic()
        clean_entities, clean_relationships = NoiseFilter().clean_and_filter(raw_entities, raw_relationships)
        canonical_nodes, rewired_edges, _ = EntityResolver().resolve(
            clean_entities, clean_relationships, source_doc=filename
        )
        stage("filter_resolve", t0)

        # Step 5: Neo4j ingest (bulk UNWIND writes)
        t0 = time.monotonic()
        graph_builder = GraphBuilder()
        graph_builder.setup_schema()
        nodes_created = graph_builder.ingest_nodes(canonical_nodes)
        edges_created = graph_builder.ingest_edges(rewired_edges)
        wrote_graph = True
        graph_builder.compute_degrees()
        graph_builder.close()
        stage("neo4j_ingest", t0)

        # Step 6: Vector indexing LAST (BUG-03). Previously vectors were
        # indexed first, so a later Neo4j failure still left queryable data
        # behind a 500. Now a failure anywhere above leaves nothing behind.
        t0 = time.monotonic()
        chunks_indexed = VectorRetriever().index_sections(parsed_doc.sections)
        wrote_vectors = True
        stage("vector_index", t0)
        logger.info(f"Indexed {chunks_indexed} chunks into ChromaDB")
    except Exception:
        # Roll back this document's partial writes so failure is truthful.
        logger.exception("Ingestion failed for '%s'; rolling back partial writes", filename)
        try:
            if wrote_graph and graph_builder is not None:
                graph_builder.delete_by_source_doc(filename)
        except Exception:  # noqa: BLE001
            logger.exception("Rollback of graph writes failed for '%s'", filename)
        try:
            if wrote_vectors:
                VectorStore().delete_by_document(filename)
        except Exception:  # noqa: BLE001
            logger.exception("Rollback of vector writes failed for '%s'", filename)
        raise

    logger.info(
        "Ingestion timing for '%s': %s",
        filename,
        " ".join(f"{k}={v:.1f}s" for k, v in timings.items()),
    )

    message = f"Successfully parsed and ingested '{filename}' into Knowledge Graph and Vector store."
    if failed_sections:
        message += f" Note: {failed_sections} section(s) could not be extracted and were skipped."

    response = IngestionResponse(
        filename=filename,
        status="success",
        sections_parsed=len(parsed_doc.sections),
        nodes_created=nodes_created,
        edges_created=edges_created,
        chunks_indexed=chunks_indexed,
        message=message,
    )
    record_ingest(account_id, sha256, filename, response.model_dump())
    return response


@router.post("", response_model=IngestionResponse, summary="Upload and Ingest PDF Document")
async def ingest_document(
    user: Annotated[UserRecord, Depends(get_current_user)],
    file: UploadFile = File(..., description="PDF document file to process and ingest"),
    clear_existing: bool = Query(
        default=False,
        description="Optionally clear existing Graph and Vector databases prior to ingestion",
    ),
) -> IngestionResponse:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Only PDF documents (.pdf) are supported for ingestion.",
        )

    logger.info(f"Starting ingestion for file: '{file.filename}' (clear_existing={clear_existing})")

    temp_path = None
    try:
        hasher = hashlib.sha256()
        total = 0
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            temp_path = tmp.name
            while chunk := await file.read(1024 * 1024):  # 1MB buffer
                total += len(chunk)
                # Server-side size cap (BUG-11): the frontend 50MB check is
                # not a security boundary; abort while streaming.
                if total > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File too large. Maximum upload size is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
                    )
                hasher.update(chunk)
                tmp.write(chunk)
        if total == 0:
            raise HTTPException(status_code=422, detail="Uploaded file is empty. Please upload a valid PDF.")

        # Off the event loop; to_thread also propagates the tenant contextvar.
        return await asyncio.to_thread(
            _run_ingestion, temp_path, file.filename, clear_existing, user.id, hasher.hexdigest()
        )

    except HTTPException:
        raise
    except ConnectionError as e:
        logger.error(f"Database connection error during ingestion: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Database unreachable during ingestion: {str(e)}",
        )
    except Exception as e:
        logger.error(f"Unexpected error during document ingestion: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Document ingestion failed: {str(e)}",
        )
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception as e:
                logger.warning(f"Failed to remove temporary file {temp_path}: {e}")
