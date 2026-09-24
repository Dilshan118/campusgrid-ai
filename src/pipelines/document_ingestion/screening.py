"""
CampusGrid AI: Ingestion-Time Clause Screening
Quarantines clauses that look like indirect prompt injection or that state tariff figures
outside the plausible reference ranges, before they ever reach the vector or keyword index.
A quarantined clause is reported back to the uploader with the reason; it is never indexed.
"""

from typing import List, Optional
from src.domain.entities.rag import DocumentClause
from src.agents.policy_rag.rule_extractor import RegulatoryRuleExtractor
from src.shared.security_patterns import detect_prompt_injection

MAX_CLAUSE_CHARS = 8_000


class ClauseScreener:
    """Returns a rejection reason for a suspicious clause, or None if it may be indexed."""

    def __init__(self, extractor: Optional[RegulatoryRuleExtractor] = None):
        self.extractor = extractor or RegulatoryRuleExtractor()

    def rejection_reason(self, clause: DocumentClause) -> Optional[str]:
        text = clause.content or ""
        if not text.strip():
            return "empty clause"
        if len(text) > MAX_CLAUSE_CHARS:
            return f"clause longer than {MAX_CLAUSE_CHARS} characters"
        flags = [f for f in detect_prompt_injection(text) if f != "secret_probe"]
        if flags:
            return f"instruction-like text detected ({', '.join(flags)})"
        rules = self.extractor.extract_tariff_rules(text)
        if rules["validation_warnings"]:
            return "implausible regulatory figures: " + "; ".join(rules["validation_warnings"])
        return None

    def screen(self, clauses: List[DocumentClause]):
        accepted, rejected = [], []
        for clause in clauses:
            reason = self.rejection_reason(clause)
            if reason:
                rejected.append({
                    "source_document": clause.source_document,
                    "clause_reference": clause.clause_reference,
                    "reason": reason,
                })
            else:
                accepted.append(clause)
        return accepted, rejected
