# erp-agent-simulation

> **Simulation only.** Every tenant, company, person, customer, supplier, item,
> quantity, amount, document, approval, and message in this repository is
> synthetic test data.

`erp-agent-simulation` is the executable source repository for
[ERPBench-100](https://blobfish.ai/benchmarks/erpbench-100), Blobfish AI's
clean-room ERP agent benchmark. It models long-horizon operations work across
ten frozen Oracle-Fusion-shaped tenants, six provider-shaped MCP systems, and
100 independently verifiable tasks.

The environment is built for outcome-level evaluation: an agent must identify
the operative evidence among superseded versions, recompute quantities and
amounts from the right sources, make a policy-supported decision, commit
durable ERP state, log the work in the ops register, prepare a review-ready
handoff, and read its writes back. Task prompts do not prescribe a tool
sequence or leak record identifiers.

## What is included

- 100 high-level ERP workflows across ten synthetic tenants and ten workflow
  families grounded in production ERP archetypes observed through Nario's
  dataflywheel: order import, shipment verification, receipt application and
  collections, reorder monitoring, receiving and three-way match, worker
  document compliance, shift work-report rollups, channel-order sync, hiring
  against approved headcount, and effective-dated price batches.
- 28 task-visible evidence files in eight native formats per task.
- 52 tools across Oracle-Fusion-shaped (order management, shipping,
  receivables, inventory, procurement, payables, HCM), Gmail, Google Drive,
  Google Sheets, Slack, and benchmark-control MCP servers.
- Task-local SQLite state with controlled writes and exact before/after
  snapshots.
- One deterministic 100-point metric, ERPScore, with 34 executable checks per
  task and no language-model judge.
- 100 Harbor task packages, a Hugging Face publication mirror, ten complete
  reference trajectories, and immutable release receipts.

## Release facts

The v1.0.0 qualification suite executes 800 episodes: 100 oracle runs, 100
exact deterministic replays, and 600 adversarial controls across six
negative-control families (no-op, answer-only, state-only, wrong-source,
wrong-target, process-as-received), plus a pre-satisfied-seed gate over every
task. A qualified receipt records 100/100 oracle strict passes, 100/100 exact
replay matches, zero pre-satisfied seeds, and zero strict false accepts.

Ranked model results are separate from qualification controls. A leaderboard
row is admitted only when one Harbor job completes all 100 pinned tasks with
zero errors and zero retries, and every public trial receipt reconciles to the
job lock, task digest, native MCP event stream, verifier, token usage, and cost.

## Repository layout

```text
benchmark/erpbench100/
├── spec.py                 tenants, families, prompts, gold outcomes, evidence, and rubrics
├── schema.sql              durable ERP tenant state (31 tables)
├── world.py                Oracle-Fusion-shaped MCP tool surface
├── evaluation.py           ERPScore, oracle, replay, negative controls, pre-satisfied gate
├── service.py              JSON-RPC MCP and health endpoints
├── release.py              source, Hugging Face, Harbor, and site artifacts
├── tests/
└── release/                qualified v1.0.0 artifact tree once built
```

## Verify locally

Requirements: Python 3.12 or newer, standard library only. The deterministic
qualification path does not need a model API key.

```bash
python3.12 -m pytest benchmark/erpbench100/tests/ -q
python3.12 -m benchmark.erpbench100.release
```

Run the published Harbor suite with any supported agent/model pair:

```bash
harbor run -d blobfishai/erpbench-100-suite@v1.0.0 \
  -a <agent> -m <provider/model>
```

See [benchmark/erpbench100/README.md](benchmark/erpbench100/README.md) for the
exact build and publication commands.

## Public artifacts

- Explorer: https://blobfish.ai/benchmarks/erpbench-100
- Hugging Face: https://huggingface.co/datasets/SamuelChien821/erpbench-100
- Harbor: https://hub.harborframework.com/datasets/blobfishai/erpbench-100-suite/latest
- Source: https://github.com/blobfishai/erp-agent-simulation/tree/main/benchmark/erpbench100

## Clean-room boundary

Nario dataflywheel grounding: workflow archetypes, tool shapes and data shapes
were observed through Nario's production dataflywheel traces; no customer
content, name, identifier, message or value was reused — every value in
ERPBench is synthetic at production shape.

The public Harbor ERP datasets
[Enterprise-Bench l1-l2-bench](https://hub.harborframework.com/datasets/Enterprise-Bench/l1-l2-bench/latest)
and [agentic-labs/erp-bench](https://hub.harborframework.com/datasets/agentic-labs/erp-bench/latest),
together with public APEX/APEX-Accounting product pages, Archipelago, and the
APEX paper, informed the inspection and execution contract. Mercor's gated
APEX-Agents corpus was not downloaded or scraped. No upstream prompt, asset,
value, world snapshot, solution, or trajectory was copied. See
[benchmark/erpbench100/release/ANCHORS.md](benchmark/erpbench100/release/ANCHORS.md)
for the complete source receipt.

Source code is released under Apache-2.0 (`LICENSE`); dataset artifacts are
released under CC BY 4.0 as recorded in `LICENSE-DATA` and
`benchmark/erpbench100/release/LICENSE-DATA`.
