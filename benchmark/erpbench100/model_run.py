#!/usr/bin/env python3
"""Import a Harbor job into an immutable ERPBench-100 model-run receipt.

A *ranked* run must cover all 100 released tasks in one Harbor job with zero
errors and zero retries, and every trial must bind to the exact published task
digest. A *pilot* run (``--allow-partial``) is recorded with the same trial
receipts but is never admitted to the leaderboard; it only contributes model
trajectories and a disclosed pilot summary.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import statistics
import tomllib
from pathlib import Path
from typing import Any

from .spec import BENCHMARK_NAME, BENCHMARK_VERSION, SCORING_CATEGORIES
from .world import WRITE_TOOLS

PACKAGE_ROOT = Path(__file__).resolve().parent
DEFAULT_RELEASE = PACKAGE_ROOT / "release"
DEFAULT_OUTPUT = PACKAGE_ROOT / "model_runs"
SCHEMA_VERSION = "erpbench.model-run.v1"
TRIAL_SCHEMA_VERSION = "erpbench.model-trial.v1"
EXPECTED_TASKS = 100
TASK_ID_PATTERN = re.compile(r"erpbench-\d{3}")
DIGEST_PATTERN = re.compile(r"sha256:[0-9a-f]{64}")
SOURCE_REPOSITORY = "https://github.com/blobfishai/erp-agent-simulation"


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def _sha256(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


def _task_digests(release_root: Path) -> dict[str, str]:
    dataset = tomllib.loads((release_root / "harbor" / "dataset.toml").read_text(encoding="utf-8"))
    digests = _read_json(release_root / "harbor" / "task-digests.json")
    by_task = {row["task_id"]: row["digest"] for row in digests["tasks"]}
    configured = {row["name"].split("/", 1)[1]: row["digest"] for row in dataset["tasks"]}
    if configured != by_task or len(by_task) != EXPECTED_TASKS:
        raise ValueError("release task digests disagree with dataset.toml")
    return by_task


def _scrub(value: Any) -> Any:
    """Drop secrets-looking strings from arguments before publication."""

    if isinstance(value, dict):
        return {key: ("<redacted>" if re.search(r"token|secret|password|api_key", key, re.I) else _scrub(item)) for key, item in value.items()}
    if isinstance(value, list):
        return [_scrub(item) for item in value]
    if isinstance(value, str) and re.search(r"sk-[A-Za-z0-9]{10,}", value):
        return "<redacted>"
    return value


def _trial_receipt(trial_dir: Path, task_digests: dict[str, str], *, require_trace: bool) -> dict[str, Any]:
    result = _read_json(trial_dir / "result.json")
    config = _read_json(trial_dir / "config.json")
    task_name = str(result.get("task_name") or config["task"]["name"])
    task_id = task_name.split("/", 1)[-1]
    if TASK_ID_PATTERN.fullmatch(task_id) is None:
        raise ValueError(f"unexpected task name {task_name}")
    ref = str(config["task"].get("ref") or "")
    if DIGEST_PATTERN.fullmatch(ref) is None or ref != task_digests[task_id]:
        raise ValueError(f"{task_id}: trial ref {ref} is not the released task digest {task_digests[task_id]}")
    if result.get("exception_info"):
        raise ValueError(f"{task_id}: trial raised {result['exception_info']}")
    verdict_path = trial_dir / "verifier" / "verdict.json"
    if not verdict_path.is_file():
        raise ValueError(f"{task_id}: missing verifier verdict")
    verdict = _read_json(verdict_path)
    if verdict.get("task_id") != task_id or verdict.get("schema_version") != "erpbench.verdict.v1":
        raise ValueError(f"{task_id}: verdict does not belong to the trial")
    reward = (result.get("verifier_result") or {}).get("rewards", {}).get("reward")
    if reward is None or abs(float(reward) - float(verdict["reward"])) > 1e-6:
        raise ValueError(f"{task_id}: Harbor reward {reward} disagrees with verdict {verdict['reward']}")
    trace_path = trial_dir / "verifier" / "trace.json"
    trace = _read_json(trace_path)["trace"] if trace_path.is_file() else None
    if require_trace and trace is None:
        raise ValueError(f"{task_id}: missing provider-native trace")
    agent_result = result.get("agent_result") or {}
    agent_info = result.get("agent_info") or {}
    receipt = {
        "schema_version": TRIAL_SCHEMA_VERSION,
        "task_id": task_id,
        "trial_name": result.get("trial_name") or trial_dir.name,
        "task_digest": ref,
        "agent": {"name": agent_info.get("name"), "version": agent_info.get("version"), "model": (agent_info.get("model_info") or {}).get("name"), "provider": (agent_info.get("model_info") or {}).get("provider")},
        "score": float(verdict["score"]),
        "reward": float(verdict["reward"]),
        "strict_pass": bool(verdict["passed"]),
        "category_scores": verdict["category_scores"],
        "failed_checks": [check["id"] for check in verdict["checks"] if not check["passed"]],
        "tool_calls": int(verdict["tool_calls"]),
        "successful_tool_calls": int(verdict["successful_tool_calls"]),
        "tokens": {"input": agent_result.get("n_input_tokens"), "cached": agent_result.get("n_cache_tokens"), "output": agent_result.get("n_output_tokens")},
        "cost_usd": agent_result.get("cost_usd"),
        "started_at": result.get("started_at"),
        "finished_at": result.get("finished_at"),
        "trace": [_scrub(entry) for entry in trace] if trace is not None else None,
    }
    receipt["receipt_sha256"] = _sha256({key: value for key, value in receipt.items() if key != "trace"})
    return receipt


def build_model_run(job_dir: Path, *, release_root: Path = DEFAULT_RELEASE, output_root: Path = DEFAULT_OUTPUT, slug: str | None = None, allow_partial: bool = False, label: str | None = None) -> dict[str, Any]:
    job_dir = job_dir.resolve()
    job_result = _read_json(job_dir / "result.json")
    job_config = _read_json(job_dir / "config.json")
    stats = job_result["stats"]
    task_digests = _task_digests(release_root)
    trial_dirs = sorted(path for path in job_dir.iterdir() if path.is_dir() and (path / "result.json").is_file())
    receipts = [_trial_receipt(path, task_digests, require_trace=not allow_partial) for path in trial_dirs]
    task_ids = [receipt["task_id"] for receipt in receipts]
    if len(set(task_ids)) != len(task_ids):
        raise ValueError("duplicate task trials in job")
    agents = {json.dumps(receipt["agent"], sort_keys=True) for receipt in receipts}
    if len(agents) != 1:
        raise ValueError(f"trials disagree on agent identity: {agents}")
    complete = len(receipts) == EXPECTED_TASKS and set(task_ids) == set(task_digests)
    if not complete and not allow_partial:
        raise ValueError(f"ranked runs need all {EXPECTED_TASKS} tasks; job has {len(receipts)}")
    if int(stats.get("n_errored_trials") or 0) or int(stats.get("n_retries") or 0):
        raise ValueError("job has errored or retried trials")
    dataset = (job_config.get("datasets") or [{}])[0]
    agent = receipts[0]["agent"]
    scores = [receipt["score"] for receipt in receipts]
    run = {
        "schema_version": SCHEMA_VERSION,
        "benchmark": BENCHMARK_NAME,
        "benchmark_version": BENCHMARK_VERSION,
        "kind": "ranked" if complete else "pilot",
        "slug": slug or job_dir.name,
        "label": label or f"{agent['model']} via {agent['name']} {agent['version']}",
        "job_name": job_result.get("job_name") or job_dir.name,
        "job_id": job_result.get("id"),
        "harbor_dataset": {"name": dataset.get("name"), "ref": dataset.get("ref"), "task_names": dataset.get("task_names")},
        "agent": {**agent, "kwargs": (job_config.get("agents") or [{}])[0].get("kwargs")},
        "execution": {"n_concurrent_trials": job_config.get("n_concurrent_trials"), "n_attempts": 1, "max_retries": 0, "agent_setup_timeout_multiplier": job_config.get("agent_setup_timeout_multiplier")},
        "tasks_attempted": len(receipts),
        "tasks_released": EXPECTED_TASKS,
        "mean_score": round(statistics.fmean(scores), 2),
        "strict_passes": sum(1 for receipt in receipts if receipt["strict_pass"]),
        "category_scores": {category["key"]: round(statistics.fmean(receipt["category_scores"][category["key"]] for receipt in receipts), 2) for category in SCORING_CATEGORIES},
        "score_distribution": {"min": min(scores), "max": max(scores), "median": statistics.median(scores)},
        "average_tool_calls": round(statistics.fmean(receipt["tool_calls"] for receipt in receipts), 1),
        "total_cost_usd": round(sum(float(receipt["cost_usd"] or 0) for receipt in receipts), 4),
        "average_cost_usd": round(statistics.fmean(float(receipt["cost_usd"] or 0) for receipt in receipts), 4),
        "tokens": {"input": sum(int(receipt["tokens"]["input"] or 0) for receipt in receipts), "cached": sum(int(receipt["tokens"]["cached"] or 0) for receipt in receipts), "output": sum(int(receipt["tokens"]["output"] or 0) for receipt in receipts)},
        "started_at": job_result.get("started_at"),
        "finished_at": job_result.get("finished_at"),
        "source_repository": SOURCE_REPOSITORY,
        "trials": [{key: value for key, value in receipt.items() if key != "trace"} for receipt in receipts],
    }
    run["run_sha256"] = _sha256(run)
    output = output_root / run["slug"]
    _write_json(output / "run.json", run)
    for receipt in receipts:
        _write_json(output / "trials" / f"{receipt['task_id']}.json", receipt)
    return run


def load_published_model_runs(output_root: Path = DEFAULT_OUTPUT) -> list[dict[str, Any]]:
    runs = []
    if not output_root.is_dir():
        return runs
    for path in sorted(output_root.glob("*/run.json")):
        run = _read_json(path)
        if run.get("schema_version") != SCHEMA_VERSION or run.get("benchmark_version") != BENCHMARK_VERSION:
            continue
        run["_trials_dir"] = str(path.parent / "trials")
        runs.append(run)
    return runs


def trial_trace(run: dict[str, Any], task_id: str) -> list[dict[str, Any]] | None:
    path = Path(run["_trials_dir"]) / f"{task_id}.json"
    if not path.is_file():
        return None
    return _read_json(path).get("trace")


def write_tool_names() -> set[str]:
    return set(WRITE_TOOLS)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job_dir", type=Path)
    parser.add_argument("--release-root", type=Path, default=DEFAULT_RELEASE)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--slug")
    parser.add_argument("--label")
    parser.add_argument("--allow-partial", action="store_true")
    arguments = parser.parse_args()
    run = build_model_run(arguments.job_dir, release_root=arguments.release_root, output_root=arguments.output_root, slug=arguments.slug, allow_partial=arguments.allow_partial, label=arguments.label)
    print(json.dumps({key: run[key] for key in ("kind", "slug", "tasks_attempted", "mean_score", "strict_passes", "category_scores", "average_cost_usd", "run_sha256")}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
