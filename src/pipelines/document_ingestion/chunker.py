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
