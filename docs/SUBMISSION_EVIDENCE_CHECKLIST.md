# Coursework submission evidence checklist

Repository inventory checked on 2026-10-01. This records files present in this checkout; it does not claim that missing files exist elsewhere or that a test suite is a complete written report.

The Individual Assignment Brief requires at least 15 distinct cases per student, with objective, input/attack, expected result, actual result, evidence, observations/conclusion, and a complete individual report. The Group Assignment Brief separately requires its final report/repository, presentation, and recorded video deliverables. Match final upload naming and platform instructions against the actual brief before submission.

| Student | Test functions | Evidence files | Status |
|---|---:|---|---|
| Student 1 | 15 | `tests/red_team_security_audits/evidence/student1/cases/` (15 JSON records) and `pytest-results.xml` | Suite run: 15 passed. Case records plus JUnit evidence now present; complete individual report still not found. |
| Student 2 | 15 | `tests/red_team_security_audits/evidence/student2/cases/` (15 JSON records) and `pytest-results.xml` | Suite run: 15 passed. Case records plus JUnit evidence now present; complete individual report still not found. |
| Student 3 | 17 (minimum 15 met) | `tests/red_team_security_audits/evidence/student3/student3_results.json`, `EVIDENCE.md`, and `pytest-results.xml` | Suite run: 10 passed, 7 xfailed; case evidence records 7 vulnerable findings. Complete individual report still not found. |
| Student 4 | 15 | `tests/red_team_security_audits/evidence/student4/cases/` (15 JSON records) and `pytest-results.xml` | Suite run: 15 passed. Passing tests include assertions that certain attacks succeed; this is not a clean security result. Complete individual report still not found. |

## Group deliverables

| Deliverable | Repository evidence | Status |
|---|---|---|
| Final group report | SRS, architecture, integration review, and implementation-status docs exist; no file identified as the final assessed group report. | Assemble and label the final report; reconcile all target-state claims with `IMPLEMENTATION_STATUS.md`. |
| Presentation | No `.ppt` / `.pptx` found in this repository. | Missing from this checkout. |
| GenAI demonstration video | No `.mp4`, `.mov`, or `.webm` found in this repository. | Missing from this checkout. |
| Source repository / setup instructions | `README.md`, `pyproject.toml`, frontend and backend source are present. | Present; remove secrets, verify clean clone setup, and supply the required repository link in submission. |
| Evaluation evidence | See [`evaluation/RESULTS.md`](evaluation/RESULTS.md). | Generated technical measurements exist; distinguish synthetic fixtures from real campus validation. |

## How to finish the individual evidence bundles

1. The latest run used mock LLM/embedding providers and is captured in the per-student JUnit XML and JSON case records. Re-run after final code changes and capture terminal/API logs needed to establish actual behavior.
2. For every case, include unique input, expected outcome, actual outcome, pass/fail or vulnerable/defended verdict, severity, mitigation, and a log/screenshot filename. Do not copy expected behavior into actual behavior.
3. Add observations and a short conclusion to each student's own report. Student 3 has 17 cases and seven open vulnerable findings; Student 4's 15 passing assertions include attacks that succeed. Keep security verdicts separate from pytest pass counts.
4. Record the commit hash, environment/provider configuration (without secrets), date, and test command in each report.
5. Re-check slide/video and repository submission rules against the assignment briefs; this checklist covers repository presence only.
