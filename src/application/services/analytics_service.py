"""
CampusGrid AI: Web Analytics Service
Computes the four web-analytics modules from recorded interaction events:

1. Query intent clustering  — what operators ask about, grouped by the parsed NLP intent,
                              with the characteristic keywords of each group.
2. Decision acceptance funnel — Recommendation shown -> Explanation opened ->
                              Citation clicked -> Decision (approved / rejected).
3. XAI A/B test             — concise vs cited explanation, compared on approval rate with a
                              two-proportion z-test.
4. Citation click-through   — Mean Reciprocal Rank of the first citation clicked.

Every figure is derived from stored events; nothing here is a hard-coded placeholder.
"""

import hashlib
import math
import re
from collections import Counter, defaultdict
from typing import Dict, Any, List
from src.domain.interfaces.repositories import AnalyticsEventRepository
from src.domain.entities.analytics import (
    AnalyticsEvent,
    AB_VARIANT_CONCISE,
    AB_VARIANT_CITED,
    EVENT_QUERY_SUBMITTED,
    EVENT_SEARCH_PERFORMED,
    EVENT_RECOMMENDATION_SHOWN,
    EVENT_EXPLANATION_OPENED,
    EVENT_CITATION_CLICKED,
    EVENT_SEARCH_RESULT_CLICKED,
    EVENT_DECISION_APPROVED,
    EVENT_DECISION_REJECTED,
)

# Below this many decisions per arm, a significance result is not meaningful.
AB_MIN_DECISIONS_PER_VARIANT = 30

_STOPWORDS = {
    "a", "an", "and", "are", "at", "be", "by", "can", "do", "does", "for", "from", "how", "i", "in",
    "is", "it", "me", "of", "on", "or", "our", "please", "show", "the", "this", "to", "we", "what",
    "when", "which", "will", "with", "you", "should", "would", "tomorrow", "today", "c",
}


class AnalyticsService:
    """Records interaction events and derives the analytics dashboards from them."""

    def __init__(self, event_repo: AnalyticsEventRepository):
        self.event_repo = event_repo

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    @staticmethod
    def assign_variant(user_id: str) -> str:
        """Deterministic 50/50 split: a user always sees the same explanation style."""
        digest = hashlib.sha256(f"xai-ab-v1:{user_id}".encode("utf-8")).digest()
        return AB_VARIANT_CONCISE if digest[0] % 2 == 0 else AB_VARIANT_CITED

    def track(self, event: AnalyticsEvent) -> int:
        if event.ab_variant is None:
            event.ab_variant = self.assign_variant(event.user_id)
        return self.event_repo.record(event)

    # ------------------------------------------------------------------
    # 1. Query intent clustering
    # ------------------------------------------------------------------

    def query_clusters(self, top_keywords: int = 5) -> Dict[str, Any]:
        events = self.event_repo.list_events([EVENT_QUERY_SUBMITTED, EVENT_SEARCH_PERFORMED])
        groups: Dict[str, List[str]] = defaultdict(list)
        for e in events:
            label = e.intent or ("knowledge_search" if e.event_type == EVENT_SEARCH_PERFORMED else "unclassified")
            groups[label].append(e.query_text or "")

        total = sum(len(q) for q in groups.values())
        clusters = []
        for label, queries in sorted(groups.items(), key=lambda kv: len(kv[1]), reverse=True):
            terms = Counter(
                tok for q in queries for tok in re.findall(r"[a-z][a-z0-9\-]+", q.lower())
                if tok not in _STOPWORDS and len(tok) > 2
            )
            clusters.append({
                "intent": label,
                "query_count": len(queries),
                "share": round(len(queries) / total, 3) if total else 0.0,
                "top_keywords": [t for t, _ in terms.most_common(top_keywords)],
                "example_queries": queries[-3:],
            })
        return {"total_queries": total, "clusters": clusters, "method": "nlp_intent_grouping"}

    # ------------------------------------------------------------------
    # 2. Decision acceptance funnel
    # ------------------------------------------------------------------

    def acceptance_funnel(self) -> Dict[str, Any]:
        events = self.event_repo.list_events([
            EVENT_RECOMMENDATION_SHOWN, EVENT_EXPLANATION_OPENED, EVENT_CITATION_CLICKED,
            EVENT_DECISION_APPROVED, EVENT_DECISION_REJECTED,
        ])
        reached: Dict[str, set] = defaultdict(set)
        for e in events:
            if e.audit_log_id is not None:
                reached[e.event_type].add(e.audit_log_id)

        shown = reached[EVENT_RECOMMENDATION_SHOWN]
        opened = reached[EVENT_EXPLANATION_OPENED] & shown
        clicked = reached[EVENT_CITATION_CLICKED] & shown
        approved = reached[EVENT_DECISION_APPROVED] & shown
        rejected = reached[EVENT_DECISION_REJECTED] & shown
        decided = approved | rejected

        def rate(n: int) -> float:
            return round(n / len(shown), 3) if shown else 0.0

        stages = [
            {"stage": "1_recommendation_shown", "count": len(shown), "rate_from_shown": 1.0 if shown else 0.0},
            {"stage": "2_explanation_opened", "count": len(opened), "rate_from_shown": rate(len(opened))},
            {"stage": "3_citation_clicked", "count": len(clicked), "rate_from_shown": rate(len(clicked))},
            {"stage": "4_decision_made", "count": len(decided), "rate_from_shown": rate(len(decided))},
        ]
        return {
            "stages": stages,
            "approved": len(approved),
            "rejected": len(rejected),
            "approval_rate_of_decided": round(len(approved) / len(decided), 3) if decided else None,
            "decided_without_opening_explanation": len(decided - opened),
        }

    # ------------------------------------------------------------------
    # 3. XAI explanation A/B test
    # ------------------------------------------------------------------

    def ab_test(self) -> Dict[str, Any]:
        events = self.event_repo.list_events([
            EVENT_RECOMMENDATION_SHOWN, EVENT_DECISION_APPROVED, EVENT_DECISION_REJECTED,
        ])
        arms: Dict[str, Dict[str, set]] = {
            v: {"shown": set(), "approved": set(), "rejected": set()}
            for v in (AB_VARIANT_CONCISE, AB_VARIANT_CITED)
        }
        for e in events:
            if e.ab_variant not in arms or e.audit_log_id is None:
                continue
            key = {
                EVENT_RECOMMENDATION_SHOWN: "shown",
                EVENT_DECISION_APPROVED: "approved",
                EVENT_DECISION_REJECTED: "rejected",
            }[e.event_type]
            arms[e.ab_variant][key].add(e.audit_log_id)

        results = {}
        for variant, sets in arms.items():
            decided = len(sets["approved"]) + len(sets["rejected"])
            results[variant] = {
                "recommendations_shown": len(sets["shown"]),
                "approved": len(sets["approved"]),
                "rejected": len(sets["rejected"]),
                "approval_rate": round(len(sets["approved"]) / decided, 3) if decided else None,
            }

        a, b = results[AB_VARIANT_CONCISE], results[AB_VARIANT_CITED]
        n_a, n_b = a["approved"] + a["rejected"], b["approved"] + b["rejected"]
        z, p = self._two_proportion_z_test(a["approved"], n_a, b["approved"], n_b)
        enough_data = min(n_a, n_b) >= AB_MIN_DECISIONS_PER_VARIANT
        return {
            "hypothesis": "Cited long-form explanations earn a different approval rate than concise summaries.",
            "variants": results,
            "z_statistic": z,
            "p_value": p,
            "significant_at_0_05": bool(enough_data and p is not None and p < 0.05),
            "sufficient_sample": enough_data,
            "min_decisions_per_variant": AB_MIN_DECISIONS_PER_VARIANT,
        }

    @staticmethod
    def _two_proportion_z_test(x1: int, n1: int, x2: int, n2: int):
        if n1 == 0 or n2 == 0:
            return None, None
        pooled = (x1 + x2) / (n1 + n2)
        se = math.sqrt(pooled * (1 - pooled) * (1 / n1 + 1 / n2))
        if se == 0:
            return 0.0, 1.0
        z = (x1 / n1 - x2 / n2) / se
        p = math.erfc(abs(z) / math.sqrt(2))  # two-sided
        return round(z, 4), round(p, 4)

    # ------------------------------------------------------------------
    # 4. Citation click-through relevance
    # ------------------------------------------------------------------

    def citation_click_through(self) -> Dict[str, Any]:
        events = self.event_repo.list_events([EVENT_CITATION_CLICKED, EVENT_SEARCH_RESULT_CLICKED])
        first_click_rank: Dict[str, int] = {}
        clicks_by_rank: Counter = Counter()
        for e in events:
            if e.rank is None:
                continue
            clicks_by_rank[e.rank] += 1
            key = f"log:{e.audit_log_id}" if e.audit_log_id is not None else f"search:{e.session_id}:{e.query_text}"
            first_click_rank[key] = min(e.rank, first_click_rank.get(key, e.rank))

        mrr = (sum(1.0 / r for r in first_click_rank.values()) / len(first_click_rank)) if first_click_rank else None
        return {
            "result_sets_with_clicks": len(first_click_rank),
            "mean_reciprocal_rank": round(mrr, 4) if mrr is not None else None,
            "clicks_by_rank": {str(r): c for r, c in sorted(clicks_by_rank.items())},
        }

    # ------------------------------------------------------------------

    def summary(self) -> Dict[str, Any]:
        clusters = self.query_clusters()
        funnel = self.acceptance_funnel()
        return {
            "total_queries_logged": clusters["total_queries"],
            "top_intent_cluster": clusters["clusters"][0]["intent"] if clusters["clusters"] else None,
            "funnel_decision_rate": funnel["stages"][3]["rate_from_shown"],
            "approval_rate_of_decided": funnel["approval_rate_of_decided"],
            "query_clusters": clusters,
            "acceptance_funnel": funnel,
            "ab_test": self.ab_test(),
            "citation_click_through": self.citation_click_through(),
        }
