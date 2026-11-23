# PURPOSE: Filters out generic/non-entity noise, validates entity naming, normalizes casing, and removes invalid/orphaned graph relationships — fully document-agnostic.
"""
Noise Filter Service (Dynamic / Document-Agnostic)
----------------------------------------------------
Cleans raw LLM extractions before entity resolution using UNIVERSAL rules
that work on any document, not hardcoded buzzwords:

1. Drops standalone dates, monetary amounts, and pure numbers via regex.
2. Drops all-lowercase generic descriptors (not proper nouns).
3. Drops universal English stop-phrases (pronouns, fillers, meta-words).
4. Drops names that are too short (≤ 2 characters).
5. Normalizes text casing and trims surrounding punctuation.
6. Drops duplicate identical entities across chunks while consolidating descriptions.
7. Prunes orphaned relationships, self-loops, and duplicate edges.
"""

import re
import logging
from typing import List, Tuple, Set, Dict
from collections import defaultdict

# Import domain models
from backend.app.models.graph import ExtractedEntity, ExtractedRelationship

logger = logging.getLogger("graphrag.noise_filter")


# CLASS: Dedicated service to purge noisy entities, non-specific terms, and invalid edges from raw extractions using document-agnostic rules.
class NoiseFilter:
    """
    Sanitizes raw LLM extractions to ensure only specific, high-value nodes
    and edges enter the graph. All rules are universal — no document-specific
    buzzwords or hardcoded terms.
    """

    # FUNCTION: Initializes the NoiseFilter with universal regex patterns and a minimal stop-phrase set.
    def __init__(self):
        # Universal stop-phrases: English pronouns, fillers, and meta-words that should never be entities.
        # This is intentionally tiny and language-universal — no domain-specific terms.
        self.stop_phrases: Set[str] = {
            # Pronouns and determiners
            "it", "they", "he", "she", "we", "them", "this", "that",
            "these", "those", "its", "their", "his", "her", "our",
            # Generic meta-words an LLM might extract as "entities"
            "the company", "company", "the team", "team", "the app", "app",
            "the report", "report", "the service", "service", "the product",
            "product", "the platform", "platform", "the system", "system",
            "the project", "project", "the document", "document",
            "the organization", "organization",
            # Standalone filler nouns
            "facts", "overview", "summary", "introduction", "conclusion",
            "appendix", "section", "chapter", "table", "figure", "note",
        }

        # Regex: Standalone dates in many formats
        # Matches: "January 2023", "Jan 2023", "2025", "Q3 2021", "03/2023",
        #          "2023-01-15", "June 2022", "September 2024", "FY2025", etc.
        self.date_pattern = re.compile(
            r'^(?:'
            r'(?:january|february|march|april|may|june|july|august|september|october|november|december'
            r'|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)'
            r'\s+\d{2,4}'                        # "January 2023", "Sep 24"
            r'|\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}'  # "03/15/2023", "15-01-2023"
            r'|\d{4}[/\-\.]\d{1,2}[/\-\.]\d{1,2}'     # "2023-01-15"
            r'|\d{1,2}[/\-\.]\d{2,4}'                  # "03/2023"
            r'|[qQ][1-4]\s*\d{4}'                      # "Q3 2021"
            r'|[fF][yY]\s*\d{4}'                       # "FY2025"
            r'|\d{4}[sS]?'                             # "2025", "1990s"
            r')$',
            re.IGNORECASE
        )

        # Regex: Monetary amounts and pure numbers
        # Matches: "$40 million", "€10 billion", "$2.5k", "500", "40 million",
        #          "£100,000", "¥500M", "10.5 billion dollars", etc.
        self.money_number_pattern = re.compile(
            r'^(?:'
            r'[\$€£¥₹₩]?\s*\d[\d,\.]*\s*(?:million|billion|trillion|thousand|hundred|[kmbt])?\s*(?:dollars?|euros?|pounds?|yen|rupees?)?'
            r'|\d[\d,\.]*\s*(?:million|billion|trillion|thousand|hundred)\s*(?:[\$€£¥₹]|dollars?|euros?|pounds?|yen|rupees?)?'
            r'|\d[\d,\.]*\s*%'                   # "15%", "99.9%"
            r'|[\$€£¥₹₩]\s*\d[\d,\.]*'           # "$40", "€10"
            r'|\d[\d,\.]*'                        # Pure number "500", "3.14"
            r')$',
            re.IGNORECASE
        )

        # Regex: Ordinals and quantity-only phrases
        # Matches: "1st", "2nd", "3rd", "100th", "first", "second", etc.
        self.ordinal_pattern = re.compile(
            r'^(?:\d+(?:st|nd|rd|th)|first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth)$',
            re.IGNORECASE
        )

    # FUNCTION: Main entry point that filters entities and validates relationships in sequence.
    def clean_and_filter(
        self,
        raw_entities: List[ExtractedEntity],
        raw_relationships: List[ExtractedRelationship]
    ) -> Tuple[List[ExtractedEntity], List[ExtractedRelationship]]:
        print(f"\n🧹 Running NoiseFilter on {len(raw_entities)} raw entities and {len(raw_relationships)} relationships...")

        # Step 1: Filter and deduplicate identical entities
        clean_entities = self.filter_entities(raw_entities)

        # Build lookup set of surviving entity names (lowercased)
        surviving_names = {e.name.lower(): e.name for e in clean_entities}

        # Step 2: Prune orphaned edges, self-loops, and duplicate relationships
        clean_relationships = self.filter_relationships(raw_relationships, surviving_names)

        dropped_entities_count = len(raw_entities) - len(clean_entities)
        dropped_relationships_count = len(raw_relationships) - len(clean_relationships)

        print(f"   • Filtered out {dropped_entities_count} noise/duplicate entities (Remaining: {len(clean_entities)})")
        print(f"   • Filtered out {dropped_relationships_count} invalid/duplicate edges (Remaining: {len(clean_relationships)})\n")

        return clean_entities, clean_relationships

    # FUNCTION: Purges noise entities using universal rules and consolidates exact-duplicate entities across chunks.
    def filter_entities(self, raw_entities: List[ExtractedEntity]) -> List[ExtractedEntity]:
        # Group entities by (canonical_name_lower, type) to merge identical entities from different chunks
        grouped_entities: Dict[Tuple[str, str], List[ExtractedEntity]] = defaultdict(list)

        for ent in raw_entities:
            normalized_name = self._normalize_name(ent.name)

            # Check if entity passes all universal noise rules
            if not self._is_substantive_entity(normalized_name):
                continue

            ent_type = ent.type.strip().capitalize()
            grouped_entities[(normalized_name.lower(), ent_type)].append(ent)

        # Merge exact duplicates into a single canonical entity with the most detailed description
        consolidated_entities: List[ExtractedEntity] = []

        for (name_lower, ent_type), instances in grouped_entities.items():
            # Use the cleanest capitalized name among the instances
            best_name = max(instances, key=lambda x: len(x.name)).name
            # Select the longest, most informative description
            best_description = max(instances, key=lambda x: len(x.description)).description
            # Track the earliest page number and source chunk
            earliest_page = min(instances, key=lambda x: x.page_number).page_number
            primary_section = instances[0].source_section

            consolidated_entities.append(ExtractedEntity(
                name=best_name,
                type=ent_type,
                description=best_description,
                source_section=primary_section,
                page_number=earliest_page
            ))

        return consolidated_entities

    # FUNCTION: Strips self-loops, orphaned edges, and combines duplicate relationships connecting the same nodes.
    def filter_relationships(
        self,
        raw_relationships: List[ExtractedRelationship],
        surviving_names: Dict[str, str]
    ) -> List[ExtractedRelationship]:
        clean_edges: List[ExtractedRelationship] = []
        # Track seen edges by (source_lower, rel_type, target_lower) to prevent duplicates
        seen_edges: Set[Tuple[str, str, str]] = set()

        for rel in raw_relationships:
            src_norm = self._normalize_name(rel.source)
            tgt_norm = self._normalize_name(rel.target)

            src_lower = src_norm.lower()
            tgt_lower = tgt_norm.lower()

            # Rule 1: Reject self-loops (an entity connected to itself)
            if src_lower == tgt_lower:
                continue

            # Rule 2: Reject orphaned edges (source or target was removed by entity filter)
            if src_lower not in surviving_names or tgt_lower not in surviving_names:
                continue

            # Remap source and target to the clean surviving entity names
            canonical_src = surviving_names[src_lower]
            canonical_tgt = surviving_names[tgt_lower]

            rel_type = rel.type.strip().upper().replace(" ", "_").replace("-", "_")
            edge_key = (canonical_src.lower(), rel_type, canonical_tgt.lower())

            # Rule 3: Deduplicate identical relationships
            if edge_key in seen_edges:
                continue

            seen_edges.add(edge_key)
            clean_edges.append(ExtractedRelationship(
                source=canonical_src,
                target=canonical_tgt,
                type=rel_type,
                description=rel.description,
                confidence=rel.confidence,
                source_section=rel.source_section,
                page_number=rel.page_number
            ))

        return clean_edges

    # FUNCTION: Normalizes casing, strips surrounding quotes, and removes trailing punctuation.
    def _normalize_name(self, name: str) -> str:
        cleaned = name.strip().strip("'\"").strip()
        # Remove trailing period unless it's a person initial (e.g. 'D. Kim')
        if cleaned.endswith(".") and len(cleaned) > 3 and not cleaned[-2].isupper():
            cleaned = cleaned[:-1]
        return cleaned

    # FUNCTION: Determines if an entity name represents a concrete, substantive entity using universal algorithmic rules.
    def _is_substantive_entity(self, name: str) -> bool:
        lower = name.lower().strip()

        # Rule 1: Too short — single characters or empty strings are never entities
        if len(lower) < 2:
            return False

        # Rule 2: Universal stop-phrases — pronouns, fillers, meta-words
        if lower in self.stop_phrases:
            return False

        # Rule 3: Pure dates — "January 2023", "2025", "Q3 2021", "FY2025"
        if self.date_pattern.match(lower):
            return False

        # Rule 4: Monetary amounts and pure numbers — "$40 million", "500", "15%"
        if self.money_number_pattern.match(lower):
            return False

        # Rule 5: Ordinals — "1st", "2nd", "third"
        if self.ordinal_pattern.match(lower):
            return False

        # Rule 6: Generic descriptor detection — if the name is entirely lowercase
        # (no capitalization at all in the original), it's likely a generic phrase
        # like "tech startup", "relational database", "consumer mobile app"
        # rather than a proper entity like "Stripe", "John Smith", "PostgreSQL".
        #
        # HOW IT WORKS: We check the ORIGINAL name (not lowered). If every word
        # starts with a lowercase letter, it's a generic descriptor and gets dropped.
        # This catches "web portal", "event streaming", "mobile app", etc.
        # But allows "Stripe", "AWS Mumbai Region", "John Smith", "PostgreSQL".
        if self._is_all_lowercase_phrase(name):
            return False

        return True

    # FUNCTION: Checks whether a name is an all-lowercase generic phrase (no proper nouns).
    def _is_all_lowercase_phrase(self, name: str) -> bool:
        """
        Returns True if the name contains NO capitalized words, meaning it's a
        generic descriptor rather than a proper entity name.

        Examples:
            "tech startup"          → True  (all lowercase → generic → DROP)
            "relational database"   → True  (all lowercase → generic → DROP)
            "consumer mobile app"   → True  (all lowercase → generic → DROP)
            "John Smith"            → False (has uppercase → proper noun → KEEP)
            "Stripe"                → False (has uppercase → proper noun → KEEP)
            "PostgreSQL"            → False (has uppercase → proper noun → KEEP)
            "AWS Mumbai Region"     → False (has uppercase → proper noun → KEEP)
            "Go"                    → False (has uppercase → proper noun → KEEP)
        """
        stripped = name.strip()
        if not stripped:
            return True

        # Split into words and check if ANY word starts with uppercase
        words = stripped.split()
        for word in words:
            # Skip pure punctuation or numbers
            if not word[0].isalpha():
                continue
            # If any word starts with an uppercase letter, it's a proper noun
            if word[0].isupper():
                return False

        # All alphabetic words are lowercase — it's a generic descriptor
        return True
