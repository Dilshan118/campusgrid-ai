"""
CampusGrid AI: Information Retrieval (IR) Benchmark Suite
Evaluates Dense Vector, Sparse BM25, and Hybrid RRF search performance
across a curated ground-truth test collection of Sri Lankan energy regulations & comfort standards.
Computes standard IR metrics: Precision@k, Recall@k, Mean Reciprocal Rank (MRR), and NDCG@k.
"""

import math
from typing import List, Dict, Any, Tuple
from src.application.container import get_container
from src.domain.entities.rag import DocumentClause

# 30 Curated Ground-Truth Regulatory Queries
IR_BENCHMARK_DATASET = [
    # Category 1: Peak Tariffs & Windows
    {"query": "What is the peak electricity tariff rate per kWh under GP-2?", "target_ref": "Clause 4.1"},
    {"query": "Between what hours does the evening peak tariff apply in Sri Lanka?", "target_ref": "Clause 4.1"},
    {"query": "How much does electricity cost during peak hours from 18:00 to 22:30?", "target_ref": "Clause 4.1"},
    {"query": "Peak window surcharge rate in LKR for university microgrid", "target_ref": "Clause 4.1"},
    {"query": "Are we advised to dispatch battery storage during 18:00 to 22:30?", "target_ref": "Clause 4.1"},

    # Category 2: Day & Off-Peak Tariffs
    {"query": "What is the day-time tariff rate between 05:30 and 18:00?", "target_ref": "Clause 4.2"},
    {"query": "Night time off-peak electricity price per unit", "target_ref": "Clause 4.2"},
    {"query": "When should battery storage systems be charged according to tariff windows?", "target_ref": "Clause 4.2"},
    {"query": "Is off-peak power billed at 15 LKR per kilowatt-hour?", "target_ref": "Clause 4.2"},
    {"query": "Day and off peak energy charges schedule PUCSL", "target_ref": "Clause 4.2"},

    # Category 3: Maximum Demand Surcharge
    {"query": "What is the monthly maximum demand charge per kVA?", "target_ref": "Clause 6.3"},
    {"query": "Single highest 15-minute integrated demand penalty in LKR", "target_ref": "Clause 6.3"},
    {"query": "What is the penalty for exceeding contract demand limit?", "target_ref": "Clause 6.3"},
    {"query": "How to eliminate demand charges from simultaneous chiller startup?", "target_ref": "Clause 6.3"},
    {"query": "1100 LKR per kVA tri-vector meter penalty clause", "target_ref": "Clause 6.3"},

    # Category 4: ASHRAE 55 Operative Temperature Bounds
    {"query": "What is the acceptable operative temperature envelope for lecture halls?", "target_ref": "Section 5.3"},
    {"query": "ASHRAE Standard 55 classroom thermal comfort temperature limits", "target_ref": "Section 5.3"},
    {"query": "Between 21.0C and 25.5C indoor temperature range for educational spaces", "target_ref": "Section 5.3"},
    {"query": "Predicted Mean Vote PMV criteria for sedentary student comfort", "target_ref": "Section 5.3"},
    {"query": "Acceptable thermal conditions for sedentary computer laboratory occupancy", "target_ref": "Section 5.3"},

    # Category 5: Precooling & Thermal Drift
    {"query": "What is the minimum temperature allowed during active precooling?", "target_ref": "Section 6.2"},
    {"query": "Precooling guidelines and thermal inertia for campus load shedding", "target_ref": "Section 6.2"},
    {"query": "Can precooling drop indoor classroom temperature below 21 degrees Celsius?", "target_ref": "Section 6.2"},
    {"query": "Maximum rate of operative temperature drift allowed per hour", "target_ref": "Section 6.2"},
    {"query": "1.1 C per hour drift limit during microgrid peak shaving", "target_ref": "Section 6.2"},

    # Category 6: Solar PV Net Metering & Humidity
    {"query": "Does exported solar energy offset the monthly Maximum Demand penalty?", "target_ref": "Clause 7.1"},
    {"query": "Net metering rules for behind-the-meter rooftop solar PV systems", "target_ref": "Clause 7.1"},
    {"query": "Air velocity and draft sensations in air-conditioned lecture spaces", "target_ref": "Section 7.1"},
    {"query": "Relative humidity limits to prevent microbial growth in lecture halls", "target_ref": "Section 7.1"},
    {"query": "Half-hourly net interval solar offsetting rules", "target_ref": "Clause 7.1"},
]


def calculate_dcg(relevance_scores: List[int], k: int) -> float:
    dcg = 0.0
    for i in range(min(k, len(relevance_scores))):
        rel = relevance_scores[i]
        dcg += (2**rel - 1) / math.log2(i + 2)
    return dcg


def evaluate_ranking(retrieved_refs: List[str], target_ref: str, k: int = 2) -> Dict[str, float]:
    """Computes Precision@k, Recall@k, Reciprocal Rank (RR), and NDCG@k."""
    top_k_refs = retrieved_refs[:k]
    matches = [1 if target_ref in ref else 0 for ref in top_k_refs]

    p_at_k = sum(matches) / k
    r_at_k = 1.0 if any(matches) else 0.0

    rr = 0.0
    for rank, ref in enumerate(retrieved_refs, start=1):
        if target_ref in ref:
            rr = 1.0 / rank
            break

    # Ideal DCG for 1 relevant item is 1.0 / log2(2) = 1.0
    idcg = 1.0
    dcg = calculate_dcg(matches, k)
    ndcg = dcg / idcg if idcg > 0 else 0.0

    return {
        "precision_at_k": p_at_k,
        "recall_at_k": r_at_k,
        "reciprocal_rank": rr,
        "ndcg_at_k": ndcg
    }


def run_benchmark():
    container = get_container()
    retrieval_service = container.retrieval_service
    bm25 = retrieval_service.bm25_engine
    vec_store = retrieval_service.vector_store
    embed_provider = retrieval_service.embedding_provider

    dense_metrics = {"p": 0.0, "r": 0.0, "mrr": 0.0, "ndcg": 0.0}
    bm25_metrics = {"p": 0.0, "r": 0.0, "mrr": 0.0, "ndcg": 0.0}
    hybrid_metrics = {"p": 0.0, "r": 0.0, "mrr": 0.0, "ndcg": 0.0}

    total_queries = len(IR_BENCHMARK_DATASET)
    K = 2

    for item in IR_BENCHMARK_DATASET:
        query = item["query"]
        target = item["target_ref"]

        # 1. Dense retrieval alone
        q_vec = embed_provider.embed_text(query)
        dense_hits = vec_store.similarity_search(q_vec, top_k=5)
        dense_refs = [h.clause.clause_reference for h in dense_hits]
        res_dense = evaluate_ranking(dense_refs, target, k=K)

        # 2. Sparse BM25 retrieval alone
        bm25_hits = bm25.search(query, top_k=5)
        bm25_refs = [c.clause_reference for c, _ in bm25_hits]
        res_bm25 = evaluate_ranking(bm25_refs, target, k=K)

        # 3. Hybrid RRF retrieval
        hybrid_hits = retrieval_service.search(query, top_k=5)
        hybrid_refs = [c["section_clause"] for c in hybrid_hits["citations"]]
        res_hybrid = evaluate_ranking(hybrid_refs, target, k=K)

        for m, dest in [(res_dense, dense_metrics), (res_bm25, bm25_metrics), (res_hybrid, hybrid_metrics)]:
            dest["p"] += m["precision_at_k"]
            dest["r"] += m["recall_at_k"]
            dest["mrr"] += m["reciprocal_rank"]
            dest["ndcg"] += m["ndcg_at_k"]

    # Average metrics
    for d in [dense_metrics, bm25_metrics, hybrid_metrics]:
        for k in d:
            d[k] /= total_queries

    print("\n" + "=" * 70)
    print("      CAMPUSGRID AI: INFORMATION RETRIEVAL BENCHMARK REPORT")
    print(f"      Evaluated on {total_queries} Test Queries (Ground-Truth Curated)")
    print("=" * 70)
    print(f"{'Retrieval Strategy':<25} | {'P@2':<8} | {'Recall@2':<10} | {'MRR':<8} | {'NDCG@2':<8}")
    print("-" * 70)
    print(f"{'Dense Vector Search':<25} | {dense_metrics['p']:<8.3f} | {dense_metrics['r']:<10.3f} | {dense_metrics['mrr']:<8.3f} | {dense_metrics['ndcg']:<8.3f}")
    print(f"{'Sparse Okapi BM25':<25} | {bm25_metrics['p']:<8.3f} | {bm25_metrics['r']:<10.3f} | {bm25_metrics['mrr']:<8.3f} | {bm25_metrics['ndcg']:<8.3f}")
    print(f"{'Hybrid Search (BM25+RRF)':<25} | {hybrid_metrics['p']:<8.3f} | {hybrid_metrics['r']:<10.3f} | {hybrid_metrics['mrr']:<8.3f} | {hybrid_metrics['ndcg']:<8.3f}")
    print("=" * 70)

    return {
        "dense": dense_metrics,
        "bm25": bm25_metrics,
        "hybrid": hybrid_metrics
    }


def test_ir_benchmark_evaluation():
    """Pytest validation that the benchmark executes and hybrid search performs reliably."""
    results = run_benchmark()
    assert results["hybrid"]["mrr"] > 0.60, "Hybrid RRF should maintain strong reciprocal rank"
    assert results["hybrid"]["recall_at_k"] > 0.70, "Hybrid RRF should maintain high recall"


if __name__ == "__main__":
    run_benchmark()
