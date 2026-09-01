#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from erpbench100.evaluation import score_episode
task = json.loads((HERE / "task.json").read_text())
evidence_path = Path(os.environ.get("ERPBENCH_EVIDENCE_PATH", "/var/lib/erpbench-evidence/evidence.json"))
if not evidence_path.exists():
    raise SystemExit(f"missing environment evidence: {evidence_path}")
evidence = json.loads(evidence_path.read_text())
verdict = score_episode(task, evidence["baseline"], evidence["snapshot"], evidence["trace"])
logs = Path("/logs/verifier")
logs.mkdir(parents=True, exist_ok=True)
(logs / "reward.txt").write_text(f"{verdict['reward']:.6f}\n")
(logs / "verdict.json").write_text(json.dumps(verdict, indent=2, sort_keys=True) + "\n")
# Keep the provider-native tool trace and the state diff with the trial so model
# trajectories can be published without reconstructing them from agent logs.
(logs / "trace.json").write_text(json.dumps({"task_id": task["task_id"], "trace": evidence["trace"]}, indent=2, sort_keys=True) + "\n")
changed = {table: {"before": evidence["baseline"].get(table, []), "after": evidence["snapshot"].get(table, [])} for table in verdict["state_diff_tables"]}
(logs / "state-diff.json").write_text(json.dumps(changed, indent=2, sort_keys=True) + "\n")
print(json.dumps(verdict, indent=2, sort_keys=True))
