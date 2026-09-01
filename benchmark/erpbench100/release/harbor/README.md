# ERPBench-100

ERPBench-100 is a 100-task, deterministic ERP agent benchmark over ten synthetic Oracle-Fusion-shaped tenants. It tests customer order import, shipment verification, receipt application and collections, reorder monitoring and requisitions, receiving and three-way match, worker document compliance, shift work-report rollups, channel-order sync, hiring against approved headcount, and effective-dated price batches — each executed end to end across the ERP, mailbox, drive, spreadsheet and chat systems.

## Run

```bash
harbor run -d blobfishai/erpbench-100 -a <agent> -m <provider/model>
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
