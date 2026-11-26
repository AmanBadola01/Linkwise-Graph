# PURPOSE: LLM-powered extraction service using Google Gemini to extract structured entities and relationships from document chunks — fully document-agnostic.
"""
Entity & Relationship Extraction Service (Dynamic / Document-Agnostic)
-----------------------------------------------------------------------
Uses Google Gemini with native Pydantic schema validation to:
1. Extract named entities (Person, Team, Product, Technology, Location, Organization).
2. Extract directed relationships (REPORTS_TO, MANAGES, BUILT_BY, DEPENDS_ON, etc.).
3. Enforce anti-noise filters using universal rules (no document-specific terms).
4. Attach document provenance (chunk ID and page number) to every node and edge.
"""

import os
import re
import time
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import List, Tuple, Set, Optional
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Load environment variables
# Load the repo-root .env explicitly (no upward search, which can hit unreadable parent dirs)
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..", ".env"))

# Import Pydantic models
from backend.app.models.document import DocumentSection, ParsedDocument
from backend.app.models.graph import (
    ExtractedEntity,
    ExtractedRelationship,
    SectionExtraction,
)

logger = logging.getLogger("graphrag.extractor")


# CLASS: Extracts entities and relationships from document sections using Google Gemini.
class EntityExtractor:
    """
    LLM Extractor implementing schema-constrained extraction using Google Gemini.
    All noise filtering is universal — no document-specific forbidden words.
    """

    # FUNCTION: Initializes the Gemini client, model parameters, and universal noise filters.
    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "models/gemini-3.5-flash-lite",
    ):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "GEMINI_API_KEY is not set. Please add it to your .env file."
            )

        self.model_name = model_name
        # The lite model periodically returns 503 "high demand"; the full
        # flash model answered in ~1s during the same window, so extraction
        # falls back to it instead of failing sections (GEMINI_FALLBACK_MODEL
        # can override, empty string disables).
        self.fallback_model = os.getenv("GEMINI_FALLBACK_MODEL", "models/gemini-3.5-flash")
        # Set when the primary model fails: later batches in this upload skip
        # straight to the fallback instead of each paying a failed attempt.
        self._primary_down = False
        self.client = genai.Client(api_key=self.api_key)

        # Universal set of forbidden generic words that must never be graph nodes.
        # Only contains English pronouns, determiners, and generic meta-nouns —
        # NO document-specific terms like company names or document titles.
        self.forbidden_entities: Set[str] = {
            # Pronouns and determiners
            "it", "they", "he", "she", "we", "them", "this", "that",
            "these", "those", "its", "their", "his", "her", "our",
            # Generic meta-nouns (with and without "the")
            "the company", "company", "the team", "team", "the app", "app",
            "the report", "report", "the service", "service", "the product",
            "product", "the platform", "platform", "the system", "system",
            "the project", "project", "the document", "document",
            "the organization", "organization",
        }

        # Regex to detect pure numbers, years, currencies, or percentages
        self.numeric_pattern = re.compile(
            r'^(?:[\$€£¥₹]?\s*\d[\d,\.]*\s*(?:million|billion|trillion|thousand|hundred|[kmbt])?\s*(?:dollars?|euros?|pounds?)?'
            r'|\d{4}[sS]?'
            r'|\d[\d,\.]*\s*%'
            r')$',
            re.IGNORECASE
        )

        # System prompt instructing Gemini on precise extraction guidelines
        self.system_instruction = (
            "You are an expert Knowledge Graph Information Extraction system.\n"
            "Your task is to analyze the provided text chunk and extract all specific named entities and relationships.\n\n"
            "EXTRACTION RULES:\n"
            "1. ENTITIES: Extract only specific, named entities. Allowed types: Person, Team, Product, Technology, Location, Organization, Project.\n"
            "2. ANTI-NOISE: NEVER extract generic terms like 'the company', 'the team', 'the app', 'the report', 'the service', 'it', or 'they'.\n"
            "   NEVER extract standalone dates ('January 2023', '2025'), monetary amounts ('$40 million'), or percentages ('15%') as entities.\n"
            "   NEVER extract generic lowercase descriptors (e.g. 'generic platform', 'web service', 'mobile application') — only proper nouns with capitalization.\n"
            "3. ACCURACY: Provide a concise 1-sentence description for each entity based only on the facts in the text.\n"
            "4. RELATIONSHIPS: Extract directed relationships between entities mentioned in the text.\n"
            "   Use standardized UPPERCASE relationship verbs such as:\n"
            "   - REPORTS_TO, MANAGES, MEMBER_OF, LEADS, SUCCEEDED\n"
            "   - BUILT_BY, DEPENDS_ON, USES_TECH, LOCATED_IN, PARTNER_OF, INVESTED_IN, COMPETES_WITH, SPONSORED_BY\n"
            "5. If a person has specific technical skills mentioned, include that in their description (e.g. 'skills: Go, Kafka').\n"
            "6. Assign a confidence score between 0.8 and 1.0 based on how explicitly the relationship is stated."
        )

    # Batching bounds: one Gemini call covers several consecutive sections.
    # This is the main upload-latency lever — previously every paragraph was
    # its own sequential API call (16 calls for a 3-page PDF).
    MAX_SECTIONS_PER_BATCH = 6
    MAX_CHARS_PER_BATCH = 6000

    @classmethod
    def _batches(cls, sections: List[DocumentSection]) -> List[List[DocumentSection]]:
        """Group consecutive sections into batches bounded by count and size.

        Sections are never batched across pages, so every extracted item can
        be stamped with the exact page it came from.
        """
        batches: List[List[DocumentSection]] = []
        current: List[DocumentSection] = []
        chars = 0
        for section in sections:
            crosses_page = bool(current) and section.page_number != current[0].page_number
            if current and (
                crosses_page
                or len(current) >= cls.MAX_SECTIONS_PER_BATCH
                or chars + len(section.content) > cls.MAX_CHARS_PER_BATCH
            ):
                batches.append(current)
                current, chars = [], 0
            current.append(section)
            chars += len(section.content)
        if current:
            batches.append(current)
        return batches

    def _postprocess(self, extraction: SectionExtraction, section: DocumentSection) -> SectionExtraction:
        # Filter out noise and attach provenance (section ID, page)
        valid_entities = []
        for ent in extraction.entities:
            cleaned_name = self._clean_entity_name(ent.name)
            if self._is_valid_entity(cleaned_name):
                ent.name = cleaned_name
                ent.source_section = section.section_id
                ent.page_number = section.page_number
                valid_entities.append(ent)

        valid_relationships = []
        for rel in extraction.relationships:
            rel.source = self._clean_entity_name(rel.source)
            rel.target = self._clean_entity_name(rel.target)
            rel.type = rel.type.strip().upper().replace(" ", "_")
            rel.source_section = section.section_id
            rel.page_number = section.page_number

            # Ensure source and target are not forbidden words
            if (
                self._is_valid_entity(rel.source)
                and self._is_valid_entity(rel.target)
                and rel.source.lower() != rel.target.lower()
            ):
                valid_relationships.append(rel)

        return SectionExtraction(entities=valid_entities, relationships=valid_relationships)

    def _generate(self, prompt: str, max_retries: int = 3) -> SectionExtraction:
        # Try the primary model, then the fallback model, with short backoff.
        # Previously a 503 from the (overloaded) lite model burned 3 attempts
        # + 6s of sleeps per section and then silently dropped the section.
        models = [self.model_name]
        if self.fallback_model and self.fallback_model != self.model_name:
            models.append(self.fallback_model)
        if self._primary_down and len(models) > 1:
            models = models[1:]
        last_error: Exception | None = None
        attempt = 0
        for model_idx, model in enumerate(models):
            # With a fallback available, try the primary once and move on
            # quickly; the last model gets the full retry budget.
            tries = max(1, max_retries - 1) if model_idx == len(models) - 1 else 1
            for _ in range(tries):
                attempt += 1
                try:
                    started = time.monotonic()
                    response = self.client.models.generate_content(
                        model=model,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            system_instruction=self.system_instruction,
                            response_mime_type="application/json",
                            response_schema=SectionExtraction,
                            temperature=0.0,  # Zero temperature for deterministic extraction
                        ),
                    )
                    logger.info(
                        "Gemini extraction call (%s) took %.1fs", model, time.monotonic() - started
                    )
                    return SectionExtraction.model_validate_json(response.text)
                except Exception as e:  # noqa: BLE001 - retry transient API failures
                    last_error = e
                    if model == self.model_name:
                        self._primary_down = True
                    logger.warning("Gemini call via %s failed (attempt %d): %s", model, attempt, str(e)[:200])
                    time.sleep(min(attempt, 3))
        raise RuntimeError(str(last_error)) if last_error else RuntimeError("Gemini extraction failed")

    # FUNCTION: Extracts entities and relationships from a single DocumentSection using structured JSON with retry on server spikes.
    def extract_from_section(self, section: DocumentSection, max_retries: int = 3) -> SectionExtraction:
        prompt = (
            f"Context / Section Title: {section.section_title} (Page {section.page_number})\n\n"
            f"Text to extract:\n\"\"\"\n{section.content}\n\"\"\"\n\n"
            "Extract all named entities and relationships present in this text."
        )
        try:
            return self._postprocess(self._generate(prompt, max_retries), section)
        except Exception as e:  # noqa: BLE001 - one bad section must not fail the upload
            logger.error(f"Error extracting from section {section.section_id} after {max_retries} attempts: {e}")
            return SectionExtraction(entities=[], relationships=[])

    # FUNCTION: Extracts from many sections with one Gemini call per batch.
    def extract_from_sections(
        self, sections: List[DocumentSection]
    ) -> Tuple[List[ExtractedEntity], List[ExtractedRelationship], int]:
        """Returns (entities, relationships, failed_section_count).

        Batches share a page, so provenance stamping stays exact. A failed
        batch is counted and skipped rather than silently dropped, and never
        fails the whole upload.
        """
        batches = self._batches(sections)
        logger.info("Extracting from %d sections in %d Gemini batch(es)", len(sections), len(batches))

        def run_batch(batch: List[DocumentSection]):
            first = batch[0]
            ents: List[ExtractedEntity] = []
            rels: List[ExtractedRelationship] = []
            failed_here = 0
            if len(batch) == 1:
                result = self.extract_from_section(first)
                return result.entities, result.relationships, failed_here

            blocks = "\n\n".join(
                f"[Section {s.section_id} | {s.section_title}]\n{s.content}" for s in batch
            )
            prompt = (
                f"Context: page {first.page_number} of a document, in {len(batch)} consecutive sections.\n\n"
                f"Text to extract:\n\"\"\"\n{blocks}\n\"\"\"\n\n"
                "Extract all named entities and relationships present in this text, across all sections."
            )
            try:
                extraction = self._generate(prompt)
            except Exception as e:  # noqa: BLE001
                # Don't drop the whole batch: retry section-by-section.
                logger.error(
                    "Gemini batch on page %d failed (%s); falling back to per-section extraction",
                    first.page_number, str(e)[:200],
                )
                for s in batch:
                    result = self.extract_from_section(s)
                    if not result.entities and not result.relationships:
                        failed_here += 1
                    ents.extend(result.entities)
                    rels.extend(result.relationships)
                return ents, rels, failed_here
            # All sections in a batch share a page, so page provenance is exact;
            # attribute items to the first section of the batch.
            processed = self._postprocess(extraction, first)
            return processed.entities, processed.relationships, failed_here

        # Batches are independent: run a few concurrently. Kept small (default
        # 3, GEMINI_CONCURRENCY) — fully parallel per-section calls previously
        # triggered free-tier 429s. Sequential batches took ~15s each in
        # series; concurrency makes total time ~= the slowest batch.
        workers = max(1, int(os.getenv("GEMINI_CONCURRENCY", "3")))
        if len(batches) <= 1 or workers == 1:
            results = [run_batch(b) for b in batches]
        else:
            with ThreadPoolExecutor(max_workers=min(workers, len(batches))) as pool:
                results = list(pool.map(run_batch, batches))

        all_entities: List[ExtractedEntity] = []
        all_relationships: List[ExtractedRelationship] = []
        failed = 0
        for ents, rels, failed_here in results:
            all_entities.extend(ents)
            all_relationships.extend(rels)
            failed += failed_here
        return all_entities, all_relationships, failed

    # FUNCTION: Iterates over all sections of a parsed document and extracts all entities and relationships.
    def extract_from_document(
        self, parsed_doc: ParsedDocument
    ) -> Tuple[List[ExtractedEntity], List[ExtractedRelationship]]:
        all_entities: List[ExtractedEntity] = []
        all_relationships: List[ExtractedRelationship] = []

        print(f"\n Starting LLM Extraction across {len(parsed_doc.sections)} chunks...")
        print("=" * 80)

        # Batched extraction (one Gemini call per page-group) — no per-section
        # pacing sleep, which previously added 0.4s x every section.
        all_entities, all_relationships, failed = self.extract_from_sections(parsed_doc.sections)
        if failed:
            print(f"   ⚠️  {failed} section(s) failed extraction and were skipped")

        print("=" * 80)
        print(f" Total Raw Entities Extracted:      {len(all_entities)}")
        print(f" Total Raw Relationships Extracted: {len(all_relationships)}\n")

        return all_entities, all_relationships

    # FUNCTION: Strips trailing punctuation, quotes, and excessive whitespace from an entity name.
    def _clean_entity_name(self, name: str) -> str:
        cleaned = name.strip().strip("'\"").strip()
        # Remove trailing period if not an abbreviation (e.g., 'Google.' -> 'Google', but keep 'D. Kim')
        if cleaned.endswith(".") and len(cleaned) > 3 and not cleaned[-2].isupper():
            cleaned = cleaned[:-1]
        return cleaned

    # FUNCTION: Checks whether an entity name is substantive using universal rules (no hardcoded terms).
    def _is_valid_entity(self, name: str) -> bool:
        lower = name.lower().strip()

        # Rule 1: Too short
        if len(lower) < 2:
            return False

        # Rule 2: Universal forbidden stop-phrases
        if lower in self.forbidden_entities:
            return False

        # Rule 3: Pure numbers, currencies, percentages
        if self.numeric_pattern.match(lower):
            return False

        return True
