# Reproducible evaluation results

Measurements captured 2026-10-01 in the local Windows virtual environment. They establish behavior on repository fixtures only; none is a real-campus validation.

The complete backend suite finished **326 passed, 7 xfailed** (333 tests total) using mock LLM/embedding providers. Those xfails are known open responsible-AI findings, not passing defenses; see Student 3 evidence. The frontend production build succeeded with Vite 5.4.21.

## Information retrieval

The 30-query labeled fixture reports Hybrid Precision@2 **0.383**, Recall@2 **0.767**, MRR **0.711**, and NDCG@2 **0.668**. BM25 alone scores P@2 **0.500**, Recall@2 **1.000**, MRR **0.950**, and NDCG@2 **0.963**. Dense search with mock embeddings scores Recall@2 **0.533**, MRR **0.495**; these small, curated results do not establish semantic retrieval quality. Labels and limitations are in [`retrieval_metrics.json`](retrieval_metrics.json).

Run with offline providers:

```powershell
$env:EMBEDDING_PROVIDER = 'mock'
$env:LLM_PROVIDER = 'mock'
python -m tests.benchmark_ir_quality
```

## Forecasting

The chronological final-20%-of-days holdout contains **864** synthetic intervals (3,456 training intervals). LightGBM test RMSE was **8.775 kW** and MAE **6.767 kW**. The previous-day same-slot baseline produced RMSE **118.279 kW** and MAE **63.332 kW**. The trainer reports 92.6% RMSE improvement on this synthetic dataset. Full run metadata is in [`forecast_metrics.json`](forecast_metrics.json).

These data are synthetic. Do not present the values as a measured accuracy result on a Sri Lankan campus. A field claim needs an agreed real telemetry period, data quality checks, a chronological holdout, and a retraining/version record.

## Dispatch solver versus reference

On one fixed 48-interval synthetic scenario, both solvers returned `Optimal`; SOC and power limits held. Recomputing both schedules with the same objective gives current solver **LKR 228,590.14**, reference solver **LKR 226,123.86** (reference lower by **LKR 2,466.28**). Both leave peak grid demand at **550 kW**. One local solve took 213.688 ms (current) and 59.410 ms (reference); these are single-run observations only. Detailed output/assumptions are in [`dispatch_metrics.json`](dispatch_metrics.json).

Run:

```powershell
python -m tests.benchmark_dispatch
```

This reveals a comparison gap to investigate in the current solver. The reference result's own `reported_optimized_cost_lkr` uses a different reporting calculation; the common-objective values are the fair comparison shown above.

## Responsible-AI / security evidence

Student 3's checked-in run evidence contains **17 cases: 10 defended and 7 vulnerable** (TC-S3-03, 04, 05, 06, 07, 13, 16). This is evidence of unresolved failure modes, not an overall “responsible AI passed” result. The file is [`student3_results.json`](../../tests/red_team_security_audits/evidence/student3/student3_results.json); rerun the suite and refresh this evidence after fixes.

Student 1, 2, and 4 each have 15 case JSON records and JUnit run results in their evidence folders. Their complete individual reports remain absent. Student 4's cases distinguish defended ingestion/ranking behavior from separate live findings; test pass counts alone do not mean every attack was blocked. See [`SUBMISSION_EVIDENCE_CHECKLIST.md`](../SUBMISSION_EVIDENCE_CHECKLIST.md).

## Retrieval trust status

The bundled GP-2 tariff snapshot is pinned by SHA-256 to the PUCSL general tariff page and is used for the stated GP-2 rates. That pin verifies the local snapshot has not changed; it is not a PUCSL digital signature, and the manifest is maintainer-controlled. ASHRAE fixture clauses remain unverified. The 30-query fixture benchmark and adversarial tests provide initial ranking/trust evidence, but production evaluation still needs independently reviewed labels, source refresh/review procedures, and testing against the full set of customer tariff classes.
