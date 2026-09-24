"""
CampusGrid AI: Regulatory Document Parser & Clause Chunker
Splits structured regulatory text and markdown documents into semantically coherent DocumentClauses.
"""

import re
from typing import List, Dict, Any, Optional
from src.domain.entities.rag import DocumentClause


class RegulatoryDocumentChunker:
    """Parses markdown regulatory documents into granular, citation-ready DocumentClauses."""

    def parse_markdown(self, markdown_content: str, default_source: str = "Regulatory Document") -> List[DocumentClause]:
        """Parses a markdown document with optional YAML frontmatter into DocumentClause entities."""
        source_doc = default_source
        effective_date = "2024-01-01"

        content = markdown_content.strip()

        # 1. Parse YAML Frontmatter if present
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                frontmatter_text = parts[1]
                content = parts[2].strip()

                for line in frontmatter_text.splitlines():
                    if ":" in line:
                        key, val = line.split(":", 1)
                        key = key.strip()
                        val = val.strip().strip('"').strip("'")
                        if key == "source_document":
                            source_doc = val
                        elif key == "effective_date":
                            effective_date = val

        # 2. Split content by sections (e.g. ### Clause X or ### Section Y)
        # Matches headings like '### Clause 4.1: Peak Energy Charges' or '### Section 5.3: ...'
        section_pattern = re.compile(r"^###\s+(.+)$", re.MULTILINE)
        matches = list(section_pattern.finditer(content))

        clauses: List[DocumentClause] = []

        if not matches:
            # Fallback: treat entire document or paragraphs as clauses
            paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
            for idx, p in enumerate(paragraphs, start=1):
                clauses.append(
                    DocumentClause(
                        id=idx,
                        source_document=source_doc,
                        clause_reference=f"Section {idx}",
                        section_title="General Guidance",
                        content=p,
                        effective_date=effective_date
                    )
                )
            return clauses

        for i, match in enumerate(matches):
            header = match.group(1).strip()
            start_pos = match.end()
            end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            body = content[start_pos:end_pos].strip()

            # Parse clause reference vs title from header
            # e.g. "Clause 4.1: Peak Energy Charges" -> clause_ref: "Clause 4.1 - Peak Energy Charges", title: "Peak Energy Charges"
            if ":" in header:
                ref_part, title_part = header.split(":", 1)
                ref_part = ref_part.strip()
                title_part = title_part.strip()
                full_ref = f"{ref_part} - {title_part}"
            elif " - " in header:
                ref_part, title_part = header.split(" - ", 1)
                ref_part = ref_part.strip()
                title_part = title_part.strip()
                full_ref = f"{ref_part} - {title_part}"
            else:
                full_ref = header
                title_part = header

            clauses.append(
                DocumentClause(
                    id=i + 1,
                    source_document=source_doc,
                    clause_reference=full_ref,
                    section_title=title_part,
                    content=body,
                    effective_date=effective_date
                )
            )


        return clauses

    # Headings as they appear in extracted PDF / plain text: "Clause 4.1: Peak ...", "Section 5.3 - ...".
    _PLAIN_HEADING = re.compile(
        r"^\s*((?:Clause|Section|Article|Schedule)\s+\d+(?:\.\d+)*)\s*[:\-–.]?\s*(.*)$",
        re.IGNORECASE | re.MULTILINE,
    )

    def parse_plain_text(self, text: str, source_document: str, effective_date: str = "2024-01-01") -> List[DocumentClause]:
        """Splits extracted PDF / plain text into clauses on 'Clause x.y' / 'Section x.y' headings."""
        content = strip_page_furniture(text)
        matches = list(self._PLAIN_HEADING.finditer(content))
        if not matches:
            return self.parse_markdown(content, default_source=source_document)

        clauses: List[DocumentClause] = []
        for i, match in enumerate(matches):
            ref, title = match.group(1).strip(), match.group(2).strip()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            body = " ".join(line.strip() for line in content[match.end():end].splitlines() if line.strip())
            if not body:
                continue
            clauses.append(DocumentClause(
                id=len(clauses) + 1,
                source_document=source_document,
                clause_reference=f"{ref} - {title}" if title else ref,
                section_title=title or ref,
                content=body,
                effective_date=effective_date,
            ))
        return clauses


def strip_page_furniture(text: str) -> str:
    """Drops page numbers and header/footer lines that repeat on many pages of an extracted PDF."""
    pages = text.split("\f")
    repeated = set()
    if len(pages) >= 3:
        counts: Dict[str, int] = {}
        for page in pages:
            for line in {l.strip() for l in page.splitlines() if l.strip()}:
                counts[line] = counts.get(line, 0) + 1
        repeated = {line for line, n in counts.items() if n >= max(3, len(pages) // 2)}

    page_number = re.compile(r"^(?:page\s*)?\d+(?:\s*(?:of|/)\s*\d+)?$", re.IGNORECASE)
    lines = [line.strip() for line in text.replace("\f", "\n").splitlines()]
    return "\n".join(line for line in lines if line not in repeated and not page_number.match(line))
