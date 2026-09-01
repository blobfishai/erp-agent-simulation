# ERPBench-100

ERPBench-100 is Blobfish AI's clean-room, executable ERP agent benchmark. It contains 100 high-level employee workflows across ten frozen synthetic Oracle-Fusion-shaped tenants and ten workflow families grounded in production ERP archetypes observed through Nario's dataflywheel: customer order import, shipment verification, receipt application and collections, reorder monitoring and requisitions, receiving and three-way match, worker document compliance, shift work-report rollups, channel-order sync and customer capture, hiring against approved headcount, and effective-dated price batches.

The benchmark exposes 52 provider-shaped tools across six logical MCP servers (ERPBench control, Oracle Fusion, Gmail, Google Drive, Google Sheets, Slack) over task-local SQLite state. Each task includes 28 visible evidence files in eight native formats, fifteen required investigations, controlled ERP writes, post-write readbacks, a reference trajectory, and 34 deterministic criteria. The single metric is ERPScore (0–100): discovery 15, ERP calculation 25, decision 15, committed ERP state 20, register and handoff 10, readback 10, and containment 5. No LLM judge is used.

## Layout

- `spec.py` authors the ten tenants, ten workflow families, 100 prompts, gold outcomes, evidence room, and rubrics.
- `schema.sql` defines the 31-table ERP tenant world.
- `world.py` implements the stateful Oracle-Fusion-shaped MCP tool surface and strict write boundaries.
- `evaluation.py` implements ERPScore, the oracle, deterministic replay, six negative controls, and the pre-satisfied-seed gate.
- `service.py` exposes the isolated tenant as JSON-RPC MCP and health endpoints.
- `release.py` builds the Hugging Face mirror, 100 Harbor task packages, website explorer data, snapshots, trajectories, verifiers, digests, and receipts.
- `release/` is the checked-in v1.0.0 artifact once built (`release/website/erpbench-data.json` is the repo-local page payload; the monorepo copy is synced separately).

## Build and verify

```bash
python3.12 -m benchmark.erpbench100.release
python3.12 -m pytest benchmark/erpbench100/tests/ -q
```

Release qualification executes 800 episodes: 100 oracle runs, 100 exact replays, and 600 adversarial controls, plus a pre-satisfied-seed gate over every task. The v1.0.0 receipt records 100/100 oracle strict passes, 100/100 deterministic matches, zero pre-satisfied seeds, and zero strict false accepts across no-op, answer-only, state-only, wrong-source, wrong-target, and process-as-received controls.

Harbor's CLI discovers task packages only as immediate children. This release keeps them in a dedicated `tasks/` directory, so publish the exact task versions before the dataset manifest:

```bash
harbor publish benchmark/erpbench100/release/harbor/tasks --public -t v1.0.0
harbor publish benchmark/erpbench100/release/harbor --no-tasks --public -t v1.0.0
```

## Public artifacts

- Explorer: https://blobfish.ai/benchmarks/erpbench-100
- Hugging Face: https://huggingface.co/datasets/SamuelChien821/erpbench-100
- Harbor: https://hub.harborframework.com/datasets/blobfishai/erpbench-100-suite/latest

## Clean-room boundary

Workflow archetypes, tool shapes and data shapes were observed through Nario's production dataflywheel traces; no customer content, name, identifier, message or value was reused — every value in ERPBench is synthetic at production shape. The public Enterprise-Bench and ERP-Bench Harbor datasets, APEX, APEX-Accounting, the APEX paper, and Archipelago informed what a reproducible enterprise benchmark should expose. Mercor's gated APEX-Agents dataset was not downloaded or scraped. Every ERPBench tenant, prompt, asset, value, tool, answer, trajectory, and verifier is independently authored and synthetic. See `release/ANCHORS.md` for the complete receipt and source links.
