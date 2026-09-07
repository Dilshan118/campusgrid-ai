# 04. Coursework Specifications, Rubrics & Agent Development Rules

**Document Identifier:** CG-RUBRICS-SPEC-2026-V3.0  
**Course Code:** IT 3041 – Information Retrieval and Web Analytics (IRWA)  
**Academic Lead:** Mr. Samadhi Chathuranga Rathnayake  
**Document Focus:** Official Syllabus Requirements, Mark Allocations, 80-Mark Report Rubric, 4 Student Security Audit Specializations & Operational Directives for AI Coding Agents.

---

## Table of Contents
1. [Group Assignment Specification (100 Marks)](#1-group-assignment-specification-100-marks)
2. [Individual AI Security Audit Specification (80M Report + 20M Viva)](#2-individual-ai-security-audit-specification-80m-report--20m-viva)
3. [The Four Individual Audit Specializations (Student 1 to 4)](#3-the-four-individual-audit-specializations-student-1-to-4)
4. [Report Evaluation Rubric Breakdown (80 Marks)](#4-report-evaluation-rubric-breakdown-80-marks)
5. [Operational Directives for Autonomous AI Agents & Subagents](#5-operational-directives-for-autonomous-ai-agents--subagents)

---

# 1. Group Assignment Specification (100 Marks)

### Assignment Title:
**Design and Implementation of an Agentic AI System Integrating LLMs, NLP, Security, Information Retrieval, and Web Analytics**

### Evaluation Breakdown:

```
+───────────────────────────────────────────────────────────────────────────────────────+
|                        GROUP ASSIGNMENT EVALUATION BREAKDOWN                          |
+───────────────────────────────────┬──────────┬────────────────────────────────────────+
| Component                         | Marks    | Submission Milestone                   |
+───────────────────────────────────┼──────────┼────────────────────────────────────────+
| Mid Evaluation Presentation       | 20 Marks | Week 6 (August 24th, 2026)             |
| Gen AI-Based Video Submission     | 25 Marks | Week 10 (3–5 min video via Synthesia)  |
| Final Technical Report            | 30 Marks | Week 10 (Prescribed format)            |
| GitHub Codebase Repository        | 5 Marks  | Week 10 (Clean code + README)          |
| Final Viva Voce Defense           | 20 Marks | Week 11 (Oral defense)                 |
+───────────────────────────────────┴──────────┴────────────────────────────────────────+
| TOTAL                             | 100 Marks|                                        |
+───────────────────────────────────┴──────────┴────────────────────────────────────────+
```

### Core Mandatory Requirements:
1. **Selected Real-World Domain:** Energy Management System & Smart Campus Microgrid.
2. **Multi-Agent Architecture:** At least two (2) interacting intelligent agents exhibiting autonomous goal-driven behavior.
3. **Core Technologies:** One or more LLMs, named NLP techniques (spaCy NER, summarization), Information Retrieval module (Hybrid RAG: pgvector dense + BM25 sparse + RRF), Web Analytics module (Query clustering, acceptance funnel, A/B testing), Security features (JWT, sanitization, mTLS), and defined communication protocols (MCP, WebSockets).
4. **Responsible AI:** Proportional fairness, explainability (XAI), transparency, differential privacy ($\epsilon=1.0$), and automated faithfulness checking.
5. **Commercialization Plan:** Realistic pricing model in Sri Lankan Rupees (LKR) with target market analysis and payback period calculations.

---

# 2. Individual AI Security Audit Specification (80M Report + 20M Viva)

### Assignment Overview & Red Teaming Mandate:
Each student within the group acts as an **AI Security Analyst (Red Team Member)** and conducts an independent vulnerability assessment of the system within their assigned specialization.

> **Objective:** Critically assess system robustness under normal and adversarial conditions by identifying vulnerabilities, evaluating risks, and recommending production-ready mitigations.

### Mandatory 7-Point Test Case Schema:
Every student must execute and document **at least 15 independent test cases** using this exact format:
1. **Test ID:** (e.g. `TC-S1-01`, `TC-S2-05`, `TC-S3-10`, `TC-S4-14`).
2. **Test Objective:** Explicit statement of the vulnerability or boundary being evaluated.
3. **Input / Attack Scenario:** Exact prompt, payload, corrupted document, or network packet used.
4. **Expected Behaviour:** Secure, ideal system response adhering to safety protocols.
5. **Actual Behaviour:** Real observed system behavior during Red Team execution.
6. **Evidence (Screenshots or Logs):** Execution log snippets or UI responses demonstrating the outcome.
7. **Severity & Mitigation Strategy:** CVSS-aligned risk classification and code-level patch.

---

# 3. The Four Individual Audit Specializations (Student 1 to 4)

```
+───────────────────────────────────────────────────────────────────────────────────────+
|                           THE 4 INDIVIDUAL AUDIT SPECIALIZATIONS                      |
+───────────────────────────────────────────────────────────────────────────────────────+
|  STUDENT 1: Prompt Injection and Jailbreak Analysis                                   |
|  - Direct & Indirect Prompt Injection         - Jailbreak Attempts & Roleplay Attacks|
|  - System Prompt Leakage                      - Instruction Overrides                 |
|  - Delimiter Collisions & Suffix Injections   - Multilingual Token Smuggling          |
+───────────────────────────────────────────────────────────────────────────────────────+
|  STUDENT 2: Privacy and Data Leakage Assessment                                       |
|  - Sensitive Information Leakage              - PII Exposure & Student Schedule Leaks|
|  - Sub-Meter Energy Disaggregation Attacks    - Cross-Tenant Multi-Campus Isolation   |
|  - Differential Privacy Noise Verification    - Markdown Image Exfiltration Vectors   |
+───────────────────────────────────────────────────────────────────────────────────────+
|  STUDENT 3: Responsible AI and Bias Assessment                                        |
|  - Hallucinated Tariff Rates & Standards      - Systematic Load-Shedding Bias         |
|  - Comfort Disparities in Student Dorms       - Explainability (XAI) Faithfulness     |
|  - Screen-Reader Accessibility & Bias         - Legacy Equipment Optimization Bias    |
+───────────────────────────────────────────────────────────────────────────────────────+
|  STUDENT 4: Information Retrieval and Security Assessment                             |
|  - RAG Document Index Poisoning               - Vector Embedding Cluster Manipulation |
|  - Unencrypted MCP Interception (mTLS)        - OpenADR Payload Tampering             |
|  - Vector Store Denial of Service             - Tool Parameter Spoofing & Replays     |
+───────────────────────────────────────────────────────────────────────────────────────+
```

---

# 4. Report Evaluation Rubric Breakdown (80 Marks)

```
+───────────────────────────────────────────────────────────────────────────────────────+
|                     INDIVIDUAL REPORT EVALUATION RUBRIC (80 MARKS)                    |
+───────────────────────────────────────────────────────────────────┬───────────────────+
| Assessment Criteria                                               | Marks Allocated   |
+───────────────────────────────────────────────────────────────────┼───────────────────+
| 1. Testing Methodology and Coverage                               | 20 Marks          |
|    - Threat modeling rigor, diversity of 15 attack test cases,    |                   |
|      systematic coverage of assigned specialization.              |                   |
+───────────────────────────────────────────────────────────────────┼───────────────────+
| 2. Quality of Vulnerability Analysis                              | 25 Marks          |
|    - Technical depth, clarity of root-cause analysis, quality of  |                   |
|      evidence (logs/payloads), accuracy of actual vs expected.    |                   |
+───────────────────────────────────────────────────────────────────┼───────────────────+
| 3. Risk Assessment and Severity Classification                    | 15 Marks          |
|    - CVSS/likelihood-impact alignment, logical severity ratings,  |                   |
|      comprehensive risk matrix synthesis.                         |                   |
+───────────────────────────────────────────────────────────────────┼───────────────────+
| 4. Mitigation Strategies                                          | 10 Marks          |
|    - Practicality, architectural feasibility, and engineering     |                   |
|      effectiveness of proposed countermeasures.                   |                   |
+───────────────────────────────────────────────────────────────────┼───────────────────+
| 5. Report Quality, Evidence, and Technical Writing                | 10 Marks          |
|    - Professional formatting, structure adherence, clarity of    |                   |
|      language, completeness of logs and citations.                |                   |
+───────────────────────────────────────────────────────────────────┼───────────────────+
| TOTAL REPORT MARKS                                                | 80 Marks          |
+───────────────────────────────────────────────────────────────────┼───────────────────+
| INDIVIDUAL VIVA VOCE EXAMINATION                                  | 20 Marks          |
+───────────────────────────────────────────────────────────────────┼───────────────────+
| TOTAL INDIVIDUAL MARKS                                            | 100 Marks         |
+───────────────────────────────────────────────────────────────────┴───────────────────+
```

---

# 5. Operational Directives for Autonomous AI Agents & Subagents

1. **Role Separation:** The LLM only parses intent and explains results. The MILP solver calculates all setpoints. **No LLM may ever write to physical switches or actuator registers directly.**
2. **Deterministic Safety Guardrails:** Hard limits enforced in middleware:
   $$21.0^\circ\text{C} \le T_{\text{setpoint}} \le 25.5^\circ\text{C}, \quad 20\% \le SOC_{\text{bess}} \le 90\%$$
3. **Protocol Standards:** Agent-to-tool calls must adhere to **Model Context Protocol (MCP)** schemas. Client-to-orchestrator and orchestrator-to-agent traffic uses **REST + JSON over HTTPS**, with each agent exposed on its own endpoint.
4. **Automated Faithfulness Check:** Every numerical claim in an LLM-generated explanation must match the solver execution log or a retrieved RAG citation; otherwise, it is rejected.
