# PURPOSE: Loads PDF/text documents, extracts text using layout mode, and chunks by semantic paragraphs while preserving section headers — fully document-agnostic.
"""
Document Parser Service (Dynamic / Document-Agnostic)
------------------------------------------------------
Responsible for:
1. Loading documents (PDF, TXT, Markdown).
2. Using pypdf layout extraction to naturally preserve visual paragraphs.
3. Automatically detecting and filtering recurring page headers/footers via
   multi-page frequency analysis (lines appearing on >50% of pages = noise).
4. Detecting section headings in multiple formats:
   - Numbered:   "1. Company Background", "2.1 Leadership"
   - Markdown:   "# Heading", "## Subheading"
   - ALL-CAPS:   "COMPANY BACKGROUND", "LEADERSHIP TEAM"
   - Short title: Standalone short lines (≤8 words, title-cased, no sentence punctuation)
5. Chunking text into focused, section-aware paragraphs with exact page numbers.
6. Returning structured DocumentSection objects ready for LLM Entity Extraction.
"""

import re
from pathlib import Path
from typing import List, Set, Dict
from collections import Counter
from pypdf import PdfReader

# Import the Pydantic data models
from backend.app.models.document import DocumentSection, ParsedDocument


class DocumentParser:
    """
    Parses documents into structured, metadata-rich paragraph chunks for GraphRAG.
    All detection rules are document-agnostic — no hardcoded company names or formats.
    """

    # FUNCTION: Initializes the DocumentParser with configurable thresholds and universal regex patterns.
    def __init__(self, min_paragraph_length: int = 30, header_footer_threshold: float = 0.5):
        self.min_paragraph_length = min_paragraph_length
        # Fraction of total pages a line must appear on to be classified as a header/footer
        self.header_footer_threshold = header_footer_threshold

        # Universal footer pattern: matches only common pagination like "Page 1 of 3"
        self.universal_footer_pattern = re.compile(
            r'^\s*(?:Page\s+\d+\s+(?:of|/)\s+\d+|[-–—]\s*\d+\s*[-–—])\s*$',
            re.IGNORECASE
        )

        # Heading pattern 1: Numbered headings — "1. Title", "2.1 Sub Title", "3.2.1 Deep"
        self.numbered_heading_pattern = re.compile(
            r'^\s*(\d+(?:\.\d+)*\.?\s+[A-Za-z0-9\s,&/\-:]+)$'
        )

        # Heading pattern 2: Markdown headings — "# Title", "## Sub Title", "### Deep"
        self.markdown_heading_pattern = re.compile(
            r'^\s*(#{1,4})\s+(.+)$'
        )

        # Heading pattern 3: ALL-CAPS titles — "COMPANY BACKGROUND", "LEADERSHIP TEAM"
        # Must be ≤ 8 words, all uppercase letters (allows &, -, numbers)
        self.allcaps_heading_pattern = re.compile(
            r'^[A-Z][A-Z0-9\s&,/\-:]{2,80}$'
        )

    # FUNCTION: First-pass scan to identify recurring header/footer lines across pages via frequency analysis.
    def _detect_header_footer_lines(self, page_texts: List[str]) -> Set[str]:
        """
        Scans the first and last 3 lines of every page. Any normalized line
        appearing on more than `header_footer_threshold` fraction of pages
        is classified as a repeating header or footer.
        """
        total_pages = len(page_texts)
        if total_pages < 2:
            return set()

        line_counter: Counter = Counter()

        for raw_text in page_texts:
            lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
            if not lines:
                continue

            # Take first 3 and last 3 lines (the typical header/footer zones)
            candidates = set()
            for line in lines[:3] + lines[-3:]:
                # Normalize: strip page numbers so "Page 1" and "Page 2" collapse
                normalized = re.sub(r'\d+', '#', line.strip())
                candidates.add(normalized)

            for c in candidates:
                line_counter[c] += 1

        # Lines appearing on > threshold fraction of pages are headers/footers
        min_appearances = max(2, int(total_pages * self.header_footer_threshold))
        recurring_patterns: Set[str] = set()
        for pattern, count in line_counter.items():
            if count >= min_appearances:
                recurring_patterns.add(pattern)

        return recurring_patterns

    # FUNCTION: Checks if a line matches any detected recurring header/footer pattern.
    def _is_header_footer(self, line: str, recurring_patterns: Set[str]) -> bool:
        # Check universal pagination patterns
        if self.universal_footer_pattern.match(line):
            return True

        # Check against dynamically detected recurring patterns
        normalized = re.sub(r'\d+', '#', line.strip())
        if normalized in recurring_patterns:
            return True

        return False

    # FUNCTION: Detects if a line is a section heading using multiple universal patterns.
    def _detect_heading(self, text: str) -> str | None:
        """
        Returns the heading text if the line is a heading, or None otherwise.
        Checks numbered headings, markdown headings, ALL-CAPS titles,
        and short title-cased standalone lines.
        """
        stripped = text.strip()

        # Pattern 1: Numbered heading — "1. Company Background"
        m = self.numbered_heading_pattern.match(stripped)
        if m:
            return m.group(1).strip()

        # Pattern 2: Markdown heading — "## Leadership"
        m = self.markdown_heading_pattern.match(stripped)
        if m:
            return m.group(2).strip()

        # Pattern 3: ALL-CAPS title — "COMPANY BACKGROUND"
        # Must be short (≤ 8 words) and all uppercase alphabetic characters
        words = stripped.split()
        if (1 <= len(words) <= 8
                and self.allcaps_heading_pattern.match(stripped)
                and not stripped.endswith(('.', ',', ';', ':', '?', '!'))):
            # Verify it's truly all-caps (not an acronym like "AWS")
            alpha_chars = [c for c in stripped if c.isalpha()]
            if len(alpha_chars) >= 4 and all(c.isupper() for c in alpha_chars):
                return stripped.title()

        # Pattern 4: Short title-cased line (≤ 8 words, no ending sentence punctuation)
        # e.g. "Leadership Team", "Products and Services"
        if (2 <= len(words) <= 8
                and stripped[0].isupper()
                and not stripped.endswith(('.', ',', ';', '?', '!'))
                and not any(c in stripped for c in '()[]{}')
                and len(stripped) < 60):
            # Check if it looks like a title (most words capitalized, no verbs/sentences)
            capitalized_words = sum(1 for w in words if w[0].isupper() or w.lower() in ('and', 'or', 'of', 'the', 'in', 'for', 'to', 'a', '&'))
            if capitalized_words == len(words):
                return stripped

        return None

    # FUNCTION: Reads and parses a PDF into section-aware paragraph chunks with exact page citations.
    def parse_pdf(self, file_path: str) -> ParsedDocument:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Document file not found at: {file_path}")

        document_name = path.name
        reader = PdfReader(str(path))
        total_pages = len(reader.pages)

        # Extract every page exactly once (layout mode preserves paragraph
        # gaps). Previously each page was extracted twice — once for the
        # header/footer scan and once for chunking — doubling parse time.
        page_texts: List[str] = []
        for page in reader.pages:
            try:
                page_texts.append(page.extract_text(extraction_mode="layout") or "")
            except Exception:
                page_texts.append(page.extract_text() or "")

        # First pass: detect recurring headers/footers across all pages
        recurring_patterns = self._detect_header_footer_lines(page_texts)
        if recurring_patterns:
            print(f"   📋 Detected {len(recurring_patterns)} recurring header/footer pattern(s) to filter")

        sections: List[DocumentSection] = []
        current_section_title = "Overview & Introduction"
        chunk_counter = 1

        # Second pass: chunk the already-extracted text
        for page_idx, raw_text in enumerate(page_texts):
            page_num = page_idx + 1

            # Split text into paragraphs separated by double newlines
            raw_paragraphs = re.split(r'\n\s*\n', raw_text)

            for para in raw_paragraphs:
                # Clean intra-sentence soft line wraps into continuous lines
                cleaned_para = " ".join(line.strip() for line in para.splitlines() if line.strip())
                cleaned_para = cleaned_para.strip()

                if not cleaned_para:
                    continue

                # Skip dynamically detected headers/footers and universal pagination
                if self._is_header_footer(cleaned_para, recurring_patterns):
                    continue

                # Check if this paragraph is a section heading
                heading = self._detect_heading(cleaned_para)
                if heading:
                    current_section_title = heading
                    continue

                # Skip tiny stray fragments that don't constitute a real paragraph
                if len(cleaned_para) < self.min_paragraph_length:
                    continue

                # Create structured DocumentSection
                section = DocumentSection(
                    section_id=f"chunk_{chunk_counter}",
                    document_name=document_name,
                    page_number=page_num,
                    section_title=current_section_title,
                    content=cleaned_para,
                    word_count=len(cleaned_para.split()),
                    metadata={
                        "char_length": len(cleaned_para),
                        "parent_section": current_section_title
                    }
                )
                sections.append(section)
                chunk_counter += 1

        return ParsedDocument(
            document_name=document_name,
            total_pages=total_pages,
            total_sections=len(sections),
            sections=sections
        )

    # FUNCTION: Parses plain text or Markdown strings into paragraph chunks using headings.
    def parse_text(self, text: str, document_name: str = "raw_document.txt") -> ParsedDocument:
        paragraphs = re.split(r'\n\s*\n', text)
        sections: List[DocumentSection] = []
        current_section_title = "General"
        chunk_counter = 1

        for para in paragraphs:
            cleaned_para = " ".join(line.strip() for line in para.splitlines() if line.strip())
            cleaned_para = cleaned_para.strip()

            if not cleaned_para:
                continue

            heading = self._detect_heading(cleaned_para)
            if heading:
                current_section_title = heading
                continue

            if len(cleaned_para) < self.min_paragraph_length:
                continue

            sections.append(DocumentSection(
                section_id=f"chunk_{chunk_counter}",
                document_name=document_name,
                page_number=1,
                section_title=current_section_title,
                content=cleaned_para,
                word_count=len(cleaned_para.split()),
                metadata={"parent_section": current_section_title}
            ))
            chunk_counter += 1

        return ParsedDocument(
            document_name=document_name,
            total_pages=1,
            total_sections=len(sections),
            sections=sections
        )

    # FUNCTION: Normalizes wrapped lines within paragraphs while keeping distinct paragraphs separated.
    def _normalize_paragraphs(self, text: str) -> str:
        paragraphs = re.split(r'\n\s*\n', text)
        cleaned_paras = []
        for p in paragraphs:
            p_single_line = " ".join(line.strip() for line in p.splitlines() if line.strip())
            if p_single_line:
                cleaned_paras.append(p_single_line)
        return "\n\n".join(cleaned_paras)
