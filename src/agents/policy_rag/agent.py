"""
CampusGrid AI: Agent 3 — Policy and Information Retrieval (IR · NLP · RAG)
Executes hybrid search across PUCSL electricity tariffs and ASHRAE comfort standards.
Emits verified regulatory constraints and citations for Agent 4's MILP solver and XAI explainer.
"""

from typing import Dict, Any, List, Optional
from src.agents.base.agent import BaseAgent
from src.domain.interfaces.policy_extractor import RegulatoryRuleExtractorInterface
from src.agents.policy_rag.rule_extractor import RegulatoryRuleExtractor
from src.domain.entities.rag import DocumentClause, Citation

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

        # 1. Execute hybrid search through retrieval service
        retrieval_result = self.retrieval_service.search(query=query, top_k=top_k)
        citations_list = retrieval_result.get("citations", [])
        matched_passages = retrieval_result.get("passages", [])

        # 2. Extract deterministic numeric rules
        combined_text = " ".join([c.get("content", "") for c in citations_list])
        rules = self.rule_extractor.extract_tariff_rules(combined_text)

        return {
            "query": query,
            "citations": citations_list,
            "matched_passages": matched_passages,
            "extracted_rules": rules,
            "peak_tariff_lkr": rules["rates_lkr_kwh"]["peak"],
            "day_tariff_lkr": rules["rates_lkr_kwh"]["day"],
            "off_peak_tariff_lkr": rules["rates_lkr_kwh"]["off_peak"],
            "max_demand_penalty_lkr_kva": rules["max_demand_penalty_lkr_kva"]
        }
