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
