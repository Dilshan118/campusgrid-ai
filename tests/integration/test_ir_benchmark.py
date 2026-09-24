"""
Regression guard for retrieval quality: runs the 30-query ground-truth benchmark in
tests/benchmark_ir_quality.py. Run that file directly to print the full report table.
"""

from tests.benchmark_ir_quality import run_benchmark


def test_hybrid_retrieval_quality_on_ground_truth_set(test_container):
    results = run_benchmark()
    assert results["bm25"]["mrr"] >= 0.90
    assert results["hybrid"]["r"] >= 0.95 * results["bm25"]["r"]
    assert results["hybrid"]["mrr"] >= 0.90, "Hybrid fusion must not rank worse than keyword search alone"
