---
license: cc-by-4.0
language:
- en
task_categories:
- question-answering
tags:
- agents
- benchmarking
- erp
- oracle-fusion
- tool-use
- mcp
- harbor
pretty_name: ERPBench-100
---

# ERPBench-100

ERPBench-100 is a 100-task, deterministic ERP agent benchmark over ten synthetic Oracle-Fusion-shaped tenants. It tests customer order import, shipment verification, receipt application and collections, reorder monitoring and requisitions, receiving and three-way match, worker document compliance, shift work-report rollups, channel-order sync, hiring against approved headcount, and effective-dated price batches — each executed end to end across the ERP, mailbox, drive, spreadsheet and chat systems.

## Run

```bash
harbor run -d blobfishai/erpbench-100-suite -a <agent> -m <provider/model>
```

## Metric

The single metric is **ERPScore** (0–100): discovery 15, ERP calculation 25, decision 15, committed ERP state 20, register and handoff 10, readback 10, containment 5. Exact call order is not graded. Every point is executable; no LLM judge is called.

## Release facts

- 100 tasks; 10 synthetic ERP tenants; 10 workflow families grounded in production ERP archetypes observed through Nario's dataflywheel (order import, shipment verification, receipt application and collections, reorder monitoring, receiving and three-way match, worker document compliance, shift work-report rollups, channel-order sync, hiring against approved headcount, and effective-dated price batches)
- 28 agent-visible files per task across 8 native formats
- 52 provider-shaped tools across 6 logical MCP servers (ERPBench control, Oracle Fusion, Gmail, Google Drive, Google Sheets, Slack)
- before/after state snapshots and full tool trajectories
- 100/100 oracle strict passes, exact deterministic replays, six negative-control families with zero false accepts, and a pre-satisfied-seed gate

All tenants, people, customers, suppliers, items, quantities, amounts, documents and messages are synthetic. This dataset is for agent evaluation and research; it is not accounting, tax, employment or operational advice.

# Public design anchors and clean-room boundary

ERPBench-100 is independently authored. These public sources informed its release and evaluation shape:

- Enterprise-Bench l1-l2-bench on Harbor: https://hub.harborframework.com/datasets/Enterprise-Bench/l1-l2-bench/latest
- agentic-labs/erp-bench on Harbor: https://hub.harborframework.com/datasets/agentic-labs/erp-bench/latest
- APEX-Agents leaderboard: https://www.mercor.com/apex/apex-agents-leaderboard/
- APEX-Accounting leaderboard: https://www.mercor.com/apex/apex-accounting-leaderboard/
- Archipelago runner and grading architecture: https://github.com/Mercor-Intelligence/archipelago
- APEX-v1-extended paper: https://arxiv.org/abs/2509.25721
- APEX-Agents dataset card: https://huggingface.co/datasets/mercor/apex-agents

Nario dataflywheel grounding: workflow archetypes, tool shapes and data shapes were observed through Nario's production dataflywheel traces; no customer content, name, identifier, message or value was reused — every value in ERPBench is synthetic at production shape.

The public Harbor ERP datasets (Enterprise-Bench and ERP-Bench) were consulted only for their public task packaging, environment contract and verifier placement; no task, fixture, prompt, seed record or solution from either was copied or adapted. The gated APEX-Agents dataset states that it is for evaluation only and forbids crawling/scraping and training use. It was not downloaded or scraped. No gated task, file, gold output, world snapshot, or trajectory was transformed or copied into ERPBench. We used only the public benchmark descriptions and public illustrative samples to identify general desiderata: realistic professional outcomes, data-rich enterprise worlds, cross-application trajectories, before/after snapshots, and criterion-level grading.

ERPBench differs materially in content and evaluation: ten new synthetic tenants and operating scenarios, new prompts and artifacts, Oracle-Fusion-shaped closed-world tools alongside Gmail, Google Drive, Google Sheets and Slack operations, deterministic source/calculation/state verifiers, explicit collateral-damage checks, a pre-satisfied-seed gate, and no judge model.
