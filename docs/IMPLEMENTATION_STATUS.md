# Implementation status and claim boundaries

This file describes the checked-in system, not the original target design. `Implemented` means code exists; it does not mean production deployment or independent validation. The implementation report should be updated from this table before submission.

| Capability | Status | What can be claimed accurately | Boundary / remaining work |
|---|---|---|---|
| Intent routing | Implemented, conditional | Deterministic rules parse first; if confidence is below a threshold, configured LLM may choose a closed action label. | LLM supplies no room/date/temperature values. Requires provider credentials/network; mock provider is not real model evidence. |
| NER | Partial | Rule-based parser extracts supported entities; room identifiers use configured inventory. | spaCy NER / `en_core_web_sm` is not wired into inference. |
| Hybrid retrieval | Implemented, limited evidence | Dense retrieval (when enabled) plus BM25 and RRF. A curated 30-query fixture benchmark and poison/duplicate regression cases exist. | Ranking metrics are on a small repository fixture. Real embeddings require optional dependencies/provider. |
| Provenance | Defensive control added; one pinned tariff snapshot | Citations expose status, source URL, snapshot SHA-256 and clause hash; raw uploads are unverified. The bundled GP-2 tariff snapshot is pinned to the PUCSL primary-source page; unverified passages cannot set tariff rules. Exact duplicate text is deduplicated across claimed titles. | The SHA pin confirms integrity of this maintained transcription, not a PUCSL digital signature or independent legal authentication. The manifest is maintainer-controlled. ASHRAE fixture clauses remain unverified. No automated official-source refresh/signature verifier is configured. |
| TLS / mTLS | Deployment-dependent / absent in app | HTTPS can be terminated by a configured reverse proxy or managed ingress. | App code does not configure TLS or mutual TLS. Deploy behind TLS, set secure proxy headers, and only claim mTLS after client certificate validation is deployed and tested. |
| Transport | Implemented | JSON REST API and an MCP JSON-RPC HTTP endpoint are available. | No WebSocket streaming. |
| Differential privacy | Narrow mechanism implemented; guarantee needs qualification | Historical telemetry export adds Laplace noise with configured epsilon and sensitivity. | This does not protect all system data. Clamping at zero, repeated releases/composition, occupancy and other fields require a formal privacy accounting/review; do not make a system-wide or person-level epsilon=1 guarantee. |
| Forecast evaluation | Implemented on supplied fixture | Trainer uses a chronological held-out split and compares against previous-day same-slot baseline. | Supplied 90-day data is synthetic. Results are not evidence of real-campus accuracy. |
| Dispatch optimization | Implemented | PuLP/CBC dispatch MILP runs on 48 intervals with battery constraints; a reference baseline implementation is available. | Comparative result must state objective/assumptions and use fixed scenario inputs; no field trial claim. |
| Responsible AI | Partial, tested with known failures | Tier guardrails, XAI/faithfulness checks and Student 3 adversarial test suite exist. | Existing Student 3 evidence records vulnerable cases; do not describe all explanations/fairness claims as verified. Tier load split may be synthetic. |
| Audit storage | Hash-chain implemented; encryption deployment-dependent | Application computes a chained signature; SQL trigger blocks row mutation. | Hash chain is tamper-evident, not encryption. Database-at-rest encryption depends on provider/deployment. |
| Privacy / data handling | Partial | Do not send secrets in prompts; telemetry response has selected transformations. | No blanket privacy guarantee; credentials and real telemetry deployment require separate operational controls. |

## Retrieval handling added in this revision

- A filename, title, effective date, or plausible rate never establishes authority.
- Raw text ingestion forcibly labels clauses `unverified`, clears any source URI, and computes a normalized content digest.
- The bundled GP-2 snapshot is allowlisted only for its exact file SHA-256 and linked to PUCSL's general tariff page. This is a local provenance control around a maintained transcription, not a cryptographic attestation from PUCSL.
- The ASHRAE markdown clauses and public raw uploads remain `unverified`; they cannot set deterministic comfort/tariff rules.
- Public uploads cannot change the trust manifest. Changes to the official snapshot require maintainers to check the source and update the pinned hash and metadata.
- GP-2 is the only tariff schedule represented. Other customer classes (including I-2) must not be answered from this snapshot; deployment tariff values require a current source review.

## Evidence and reproducibility

Measured results and their synthetic-data limits are recorded in [`evaluation/RESULTS.md`](evaluation/RESULTS.md). Submission artifact status is tracked in [`SUBMISSION_EVIDENCE_CHECKLIST.md`](SUBMISSION_EVIDENCE_CHECKLIST.md). Never convert a test pass into a claim of deployment, official-source authentication, or real-campus performance.
