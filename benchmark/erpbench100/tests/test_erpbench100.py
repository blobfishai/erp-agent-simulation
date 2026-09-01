from __future__ import annotations

import json
import tempfile
import tomllib
from pathlib import Path

import pytest

from benchmark.erpbench100.evaluation import POLICIES, policy_steps, qualify, run_episode
from benchmark.erpbench100.release import (
    ANCHOR_ARCHIPELAGO_URL,
    ANCHOR_ENTERPRISE_BENCH_URL,
    ANCHOR_ERP_BENCH_URL,
    DEFAULT_OUTPUT,
    HF_COMMIT,
    HF_PAYLOAD_MANIFEST_SHA256,
    HF_URL,
    NARIO_GROUNDING_STATEMENT,
    WEBSITE_DATA,
    _anchors_text,
    harbor_task_digest,
)
from benchmark.erpbench100.service import mcp_response
from benchmark.erpbench100.spec import (
    FAMILIES,
    SCORING_CATEGORIES,
    WORLDS,
    build_tasks,
    catalog_digest,
)
from benchmark.erpbench100.world import SERVERS, ErpWorld, grouped_tool_definitions, tool_definitions

EXPECTED_SERVERS = {"erpbench", "oracle_fusion", "gmail", "google_drive", "google_sheets", "slack"}


def test_catalog_has_100_distinct_grounded_tasks() -> None:
    tasks = build_tasks()
    assert len(tasks) == 100
    assert len({task["task_id"] for task in tasks}) == 100
    assert len({task["prompt"] for task in tasks}) == 100
    assert len({task["tenant_code"] for task in tasks}) == len(WORLDS) == 10
    assert {task["metadata"]["category"] for task in tasks} == {family["key"] for family in FAMILIES}
    assert len(FAMILIES) == 10
    assert all(len(task["context_files"]) == 28 for task in tasks)
    assert all(len(task["required_investigations"]) == 15 for task in tasks)
    assert all(sum(check["points"] for check in task["rubric"]) == 100 for task in tasks)
    assert all(len(task["rubric"]) == 34 for task in tasks)
    assert all("Leave unrelated records and other tenants unchanged" in task["prompt"] for task in tasks)
    assert all("Company=" not in task["prompt"] and "contentId=" not in task["prompt"] for task in tasks)
    assert all(task["metadata"]["nario_grounding"]["archetype"] for task in tasks)
    assert len(catalog_digest(tasks)) == 64


def test_erp_score_is_one_hundred_points_across_seven_categories() -> None:
    assert len(SCORING_CATEGORIES) == 7
    assert sum(category["weight"] for category in SCORING_CATEGORIES) == 100
    categories = {category["key"] for category in SCORING_CATEGORIES}
    for task in build_tasks():
        assert {criterion["category"] for criterion in task["rubric"]} == categories


def test_oracle_and_controls_are_discriminating() -> None:
    report = qualify(build_tasks())
    assert report["qualification_passed"] is True
    assert report["oracle"] == {"passes": 100, "mean_score": 100.0}
    assert report["determinism"] == {"replays": 100, "exact_episode_matches": 100, "mismatches": 0}
    assert report["executions"] == 800
    assert set(report["negative_controls"]) == set(POLICIES[1:])
    assert len(report["negative_controls"]) == 6
    assert all(control["strict_passes"] == 0 for control in report["negative_controls"].values())
    assert all(control["false_accepts"] == 0 for control in report["negative_controls"].values())
    assert all(control["mean_score"] < 100 for control in report["negative_controls"].values())
    assert report["pre_satisfied_gate"]["pre_satisfied_tasks"] == []


def test_task_specific_state_and_readbacks_are_required() -> None:
    tasks = build_tasks()
    for task in (tasks[1], tasks[7], tasks[9]):
        oracle = run_episode(task, policy_steps(task, "oracle"))["verdict"]
        shortcut = run_episode(task, policy_steps(task, "shortcut"))["verdict"]
        state_only = run_episode(task, policy_steps(task, "state_only"))["verdict"]
        assert oracle["passed"] is True and oracle["score"] == 100
        assert shortcut["passed"] is False and shortcut["score"] < 60
        assert state_only["passed"] is False and state_only["category_scores"]["discovery"] == 0


def test_mcp_contract_groups_every_tool_and_persists_state() -> None:
    task = build_tasks()[0]
    definitions = tool_definitions(task["answer_schema"])
    assert len(definitions) == len(tool_definitions()) == 52
    assert all(tool["inputSchema"]["additionalProperties"] is False for tool in definitions)
    grouped = grouped_tool_definitions(task["answer_schema"])
    assert set(grouped) == set(SERVERS) == EXPECTED_SERVERS
    assert sum(len(tools) for tools in grouped.values()) == len(definitions)
    with tempfile.TemporaryDirectory() as temporary:
        world = ErpWorld.create(task, Path(temporary) / "world.sqlite")
        response = mcp_response(
            world,
            grouped,
            "erpbench",
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        )
        assert response is not None
        assert response["result"]["tools"]
        result = world.call_tool("erpbench.get_task", {"task_id": task["task_id"]})
        assert result["tenant_code"] == task["tenant_code"]
        assert "expected_answer" not in result
        world.close()


def test_checked_in_release_is_harbor_and_website_complete() -> None:
    build_path = DEFAULT_OUTPUT / "reports" / "build.json"
    if not build_path.exists():
        pytest.skip("release not built yet; run `python3.12 -m benchmark.erpbench100.release`")
    build = json.loads(build_path.read_text())
    qualification = json.loads((DEFAULT_OUTPUT / "reports" / "qualification.json").read_text())
    assert build["task_count"] == 100
    assert build["tenant_count"] == 10
    assert build["world_count"] == 10
    assert build["family_count"] == 10
    assert build["tool_count"] == 52
    assert build["negative_control_families"] == 6
    assert build["pre_satisfied_tasks"] == []
    assert build["qualification_passed"] is True
    assert qualification["oracle"]["passes"] == 100
    task_dirs = sorted((DEFAULT_OUTPUT / "harbor" / "tasks").iterdir())
    assert len(task_dirs) == 100
    dataset = tomllib.loads((DEFAULT_OUTPUT / "harbor" / "dataset.toml").read_text())
    assert dataset["dataset"]["name"] == "blobfishai/erpbench-100-suite"
    assert len(dataset["tasks"]) == 100
    expected_digests = {entry["name"].split("/", 1)[1]: entry["digest"] for entry in dataset["tasks"]}
    for task_dir in (task_dirs[0], task_dirs[49], task_dirs[-1]):
        digest, files, size = harbor_task_digest(task_dir)
        assert digest == expected_digests[task_dir.name]
        assert files > 20 and size > 10_000
        task_toml = tomllib.loads((task_dir / "task.toml").read_text())
        assert {server["name"] for server in task_toml["environment"]["mcp_servers"]} == EXPECTED_SERVERS
        assert task_toml["metadata"]["metric"] == "ERPScore"
    page = json.loads(WEBSITE_DATA.read_text())
    assert page["benchmark"]["taskCount"] == 100
    assert len(page["tasks"]) == 100
    assert len(page["samples"]) == 100
    assert sum(1 for trajectory in page["trajectories"] if trajectory["kind"] == "reference") == 10
    assert all(trajectory["kind"] in {"reference", "model"} for trajectory in page["trajectories"])
    assert page["leaderboard"] == []
    assert page["evaluationControls"][0]["score"] == 100
    assert len(page["evaluationControls"]) == 7
    assert page["benchmark"]["releaseEvidence"]["qualification"]["negativeControlTypes"] == 6
    assert page["benchmark"]["publicationReceipt"] == {
        "huggingFaceCommit": HF_COMMIT,
        "payloadManifestSha256": HF_PAYLOAD_MANIFEST_SHA256,
        "exactObjectIdentity": bool(HF_COMMIT and HF_PAYLOAD_MANIFEST_SHA256),
        "receiptUrl": f"{HF_URL}/tree/{HF_COMMIT}" if HF_COMMIT else HF_URL,
    }
    assert len(list((DEFAULT_OUTPUT / "huggingface" / "verifiers").glob("*.json"))) == 100
    assert len(list((DEFAULT_OUTPUT / "huggingface" / "trajectories").glob("*.json"))) == 10
    revision = HF_COMMIT or "main"
    assert all(f"/blob/{revision}/" in task["datasetUrl"] for task in page["tasks"])
    assert all(
        f"/resolve/{revision}/" in asset["url"]
        for sample in page["samples"].values()
        for asset in sample["assets"]
    )
    assert all(f"/blob/{revision}/" in trajectory["transcriptUrl"] for trajectory in page["trajectories"] if trajectory["kind"] == "reference")
    assert all(f"/blob/{revision}/" in trajectory["verifierUrl"] for trajectory in page["trajectories"] if trajectory["kind"] == "reference")


def test_clean_room_anchor_receipt_is_explicit() -> None:
    anchors = _anchors_text()
    checked_in = DEFAULT_OUTPUT / "ANCHORS.md"
    if checked_in.exists():
        assert checked_in.read_text() == anchors
    for url in (
        ANCHOR_ENTERPRISE_BENCH_URL,
        ANCHOR_ERP_BENCH_URL,
        "https://www.mercor.com/apex/apex-agents-leaderboard/",
        "https://www.mercor.com/apex/apex-accounting-leaderboard/",
        ANCHOR_ARCHIPELAGO_URL,
        "https://arxiv.org/abs/2509.25721",
        "https://huggingface.co/datasets/mercor/apex-agents",
    ):
        assert url in anchors
    assert NARIO_GROUNDING_STATEMENT in anchors
    assert "No gated task" in anchors
    assert "not downloaded or scraped" in anchors
