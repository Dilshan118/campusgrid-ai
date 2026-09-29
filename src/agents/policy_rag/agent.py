"""
CampusGrid AI: Agent 3 — Policy and Information Retrieval (IR · NLP · RAG)
Executes hybrid search across PUCSL electricity tariffs and ASHRAE comfort standards.
Emits verified regulatory constraints and citations for Agent 4's MILP solver and XAI explainer.
"""

from typing import Dict, Any, List, Optional
from src.agents.base.agent import BaseAgent
from src.domain.interfaces.policy_extractor import RegulatoryRuleExtractorInterface
from src.agents.policy_rag.rule_extractor import RegulatoryRuleExtractor

# Targeted queries that retrieve the clauses the solver needs, whatever the operator asked.
# Without them, a question like "precool LH-1 to 23.5 C" retrieves comfort clauses only and
# the tariff figures silently fall back to defaults instead of coming from the documents.
CONSTRAINT_QUERIES = [
    "peak window billed at unit rate LKR per kilowatt-hour",
    "day-time and off-peak energy consumption billed at LKR per kWh",
    "monthly maximum demand charge LKR per kVA",
    "ASHRAE operative temperature envelope ranges between",
]


def _citation_key(citation: Dict[str, Any]) -> str:
    return f"{citation.get('document_title')}|{citation.get('section_clause')}"


class PolicyRAGAgent(BaseAgent):
    """Agent 3: Regulatory Information Retrieval and Constraint Extraction."""

    def __init__(
        self,
        retrieval_service: Any,
        rule_extractor: Optional[RegulatoryRuleExtractorInterface] = None
    ):
        super().__init__(
            name="Agent 3: Policy & Information Retrieval",
            description="Searches PUCSL tariffs and ASHRAE comfort standards using hybrid RAG."
        )
        self.retrieval_service = retrieval_service
        self.rule_extractor = rule_extractor or RegulatoryRuleExtractor()

    def _run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        query = input_data.get("query", "What are the PUCSL GP-2 peak tariff rates and demand charge penalty?")
        top_k = int(input_data.get("top_k", 2))
        include_constraints = bool(input_data.get("include_tariff_constraints", False))

        # 1. Hybrid search for the operator's own question (what the dashboard shows as sources)
        retrieval_result = self.retrieval_service.search(query=query, top_k=top_k)
        citations_list: List[Dict[str, Any]] = retrieval_result.get("citations", [])

        # 2. When feeding the solver, also retrieve the clauses that define the tariff constraints
        constraint_citations: List[Dict[str, Any]] = []
        if include_constraints:
            seen = set()
            for constraint_query in CONSTRAINT_QUERIES:
                for c in self.retrieval_service.search(query=constraint_query, top_k=2).get("citations", []):
                    if _citation_key(c) not in seen:
                        seen.add(_citation_key(c))
                        constraint_citations.append({**c, "retrieved_for": "tariff_constraints"})

        # 3. Deterministic rule extraction, with the clause each figure came from
        rule_sources = constraint_citations + citations_list
        if hasattr(self.rule_extractor, "extract_from_passages"):
            rules = self.rule_extractor.extract_from_passages(rule_sources)
        else:
            rules = self.rule_extractor.extract_tariff_rules(" ".join(c.get("content", "") for c in rule_sources))

        # Citations handed downstream: the operator's sources first, then any constraint clause not already listed.
        listed = {_citation_key(c) for c in citations_list}
        all_citations = citations_list + [c for c in constraint_citations if _citation_key(c) not in listed]

        return {
            "query": query,
            "citations": citations_list,
            "constraint_citations": constraint_citations,
            "all_citations": all_citations,
            "extracted_rules": rules,
            "peak_tariff_lkr": rules["rates_lkr_kwh"]["peak"],
            "day_tariff_lkr": rules["rates_lkr_kwh"]["day"],
            "off_peak_tariff_lkr": rules["rates_lkr_kwh"]["off_peak"],
            "max_demand_penalty_lkr_kva": rules["max_demand_penalty_lkr_kva"]
        }
