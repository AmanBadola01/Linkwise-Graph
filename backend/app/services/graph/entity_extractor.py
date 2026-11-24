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
from typing import List, Tuple, Set, Optional
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Load environment variables
load_dotenv()

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

    # FUNCTION: Extracts entities and relationships from a single DocumentSection using structured JSON with retry on server spikes.
    def extract_from_section(self, section: DocumentSection, max_retries: int = 3) -> SectionExtraction:
        prompt = (
            f"Context / Section Title: {section.section_title} (Page {section.page_number})\n\n"
            f"Text to extract:\n\"\"\"\n{section.content}\n\"\"\"\n\n"
            "Extract all named entities and relationships present in this text."
        )

        for attempt in range(max_retries):
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=self.system_instruction,
                        response_mime_type="application/json",
                        response_schema=SectionExtraction,
                        temperature=0.0,  # Zero temperature for deterministic extraction
                    ),
                )

                extraction = SectionExtraction.model_validate_json(response.text)

                # Post-process: Filter out noise and attach provenance (section ID, page)
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

                return SectionExtraction(
                    entities=valid_entities,
                    relationships=valid_relationships,
                )

            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = 2 * (attempt + 1)
                    time.sleep(wait_time)
                else:
                    logger.error(
                        f"Error extracting from section {section.section_id} after {max_retries} attempts: {e}"
                    )
                    return SectionExtraction(entities=[], relationships=[])

    # FUNCTION: Iterates over all sections of a parsed document and extracts all entities and relationships.
    def extract_from_document(
        self, parsed_doc: ParsedDocument
    ) -> Tuple[List[ExtractedEntity], List[ExtractedRelationship]]:
        all_entities: List[ExtractedEntity] = []
        all_relationships: List[ExtractedRelationship] = []

        print(f"\n Starting LLM Extraction across {len(parsed_doc.sections)} chunks...")
        print("=" * 80)

        for idx, section in enumerate(parsed_doc.sections, 1):
            print(
                f"[{idx:02d}/{len(parsed_doc.sections):02d}] Extracting from {section.section_id} "
                f"(Page {section.page_number} | '{section.section_title}')...",
                end="",
                flush=True,
            )

            result = self.extract_from_section(section)
            all_entities.extend(result.entities)
            all_relationships.extend(result.relationships)

            print(
                f" Done! -> Found {len(result.entities)} entities, {len(result.relationships)} relationships."
            )
            # Gentle pacing to avoid free-tier API rate limits
            time.sleep(0.4)

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
