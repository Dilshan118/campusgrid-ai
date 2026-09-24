# Documentation Index

> **New here? Start with [`ARCHITECTURE.md`](ARCHITECTURE.md).** It is the complete guide — the
> system, the agents, the technologies, what is built, who does what, and how we work.
> The remaining documents are the formal specification and the coursework requirements.

These documents serve different purposes. Read the one you need.

| Document | What it is | Read it when |
|---|---|---|
| **`ARCHITECTURE.md`** | **The master reference.** How the system works, how each agent behaves, how the technologies (LLM, embeddings, vector database, RAG, ML, solver) fit together and connect in our code, what is built vs missing, and the full four-person plan with build order. | **Start here.** It is the only document you need to begin work. |
| **`CAMPUSGRID_AI_SIMPLIFIED_SRS_AND_SYSTEM_GUIDE.md`** | The working system guide, in seven focused views: the problem, the architecture, the four agents, the tech stack, the offline pipelines, the codebase layout, and team delegation. | You want the formal technical detail behind the plain-English overview. |
| **`CAMPUSGRID_AI_MASTER_ARCHITECTURAL_BLUEPRINT_AND_SRS.md`** | The long-form SRS. Everything in the guide above, plus the mathematical formulations, the commercialization plan with LKR pricing, and an 18-question viva preparation section. | You are writing the final report or preparing for the viva. |
| **`TEAM_LEAD_REVIEW_AND_INTEGRATION_REPORT.md`** | Proposal-vs-code scorecard, what the Lead fixed, open items per member, cross-member integration issues and pending team decisions. | You want to know what is left to do and who owns it. |
| **`SYSTEM_USER_FLOW_AND_UIUX_SPEC.md`** | Roles and permissions, sign-in flow, every dashboard page, user journeys, edge cases and the page-to-API map. | You are building or reviewing the dashboard. |
| **`04_COURSEWORK_SPECIFICATIONS_AND_RUBRICS.md`** | The assignment requirements, mark allocations, the four individual security-audit specialisations, and the mandatory 7-point test case schema. | You want to know what you are graded on. |

---

## Which document wins when they disagree

1. **Code ownership** → [`../TEAM_GUIDES/OWNERSHIP.md`](../TEAM_GUIDES/OWNERSHIP.md) is authoritative,
   always. Ownership tables inside the two SRS documents are earlier drafts retained for the
   coursework record.
2. **How to install and run** → [`../README.md`](../README.md).
3. **What the system actually does today** → the code, then the two SRS documents.

---

## Accuracy note

These documents were written before the `src/` Clean Architecture refactor and have been
corrected against the codebase as of **7 September 2026**. Things that were described but never
built have been either removed or explicitly marked **(planned)**.

Two design decisions are recorded rather than silently dropped, because you will be asked about
them:

- **LangGraph was evaluated and not adopted.** The agent pipeline is a straight line with no
  cycles and no conditional graph state, so a graph framework would add dependency weight and
  vendor coupling without buying anything. The assignment brief lists frameworks as *allowed*,
  not required.
- **Cross-encoder reranking was evaluated and deferred.** Reciprocal Rank Fusion over dense plus
  sparse retrieval already resolves this corpus, and a cross-encoder would add a second model
  download for no measurable gain at this scale.

When you extend the system, update these documents in the same commit. A specification that
describes something the code does not do costs marks in the report and credibility in the viva.
