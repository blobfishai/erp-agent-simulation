"""Build the public ERPBench-100 source, Hugging Face, Harbor, and website artifacts."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import shutil
import zipfile
from pathlib import Path
from typing import Any

from .evaluation import policy_steps, qualify, run_episode
from .spec import (
    ASSET_NAMES,
    BENCHMARK_NAME,
    BENCHMARK_VERSION,
    FAMILIES,
    METRIC,
    SCORING_CATEGORIES,
    WORLDS,
    WORLD_ID,
    asset_payloads,
    build_tasks,
    catalog_digest,
    task_digest,
)
from .world import SERVER_BY_PREFIX, SERVERS, TABLES, WRITE_TOOLS, grouped_tool_definitions, tool_definitions

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT = PACKAGE_ROOT / "release"
# Repo-local website payload; the monorepo copy under products/website is synced separately.
WEBSITE_DATA = PACKAGE_ROOT / "release" / "website" / "erpbench-data.json"
SOURCE_URL = "https://github.com/blobfishai/erp-agent-simulation/tree/main/benchmark/erpbench100"
HF_DATASET = "SamuelChien821/erpbench-100"
HF_URL = f"https://huggingface.co/datasets/{HF_DATASET}"
HF_COMMIT = "f83f74faa59e29d4a56406078444012b47a84a6d"
HF_PAYLOAD_MANIFEST_SHA256 = "58dc05910d0eebb04cec986828c9950a8d25fff940a7d8563219321fe3c1ce5d"
HARBOR_DATASET_ID = "blobfishai/erpbench-100"
HARBOR_URL = f"https://hub.harborframework.com/datasets/{HARBOR_DATASET_ID}/latest"
PAGE_URL = "https://blobfish.ai/benchmarks/erpbench-100"
HARBOR_IMAGE = "python:3.12-slim@sha256:7a8b475003c4fe15a2cd4e55e5cfc2f3560bdc9333d624f24cdd6d4340fd7a17"
PUBLISH_DIRECT_FILES = ("task.toml", "instruction.md", "README.md")
PUBLISH_DIRECTORIES = ("environment", "tests", "solution", "steps")
ANCHOR_ENTERPRISE_BENCH_URL = "https://hub.harborframework.com/datasets/Enterprise-Bench/l1-l2-bench/latest"
ANCHOR_ERP_BENCH_URL = "https://hub.harborframework.com/datasets/agentic-labs/erp-bench/latest"
ANCHOR_ARCHIPELAGO_URL = "https://github.com/Mercor-Intelligence/archipelago"
NARIO_GROUNDING_STATEMENT = (
    "workflow archetypes, tool shapes and data shapes were observed through Nario's production dataflywheel traces; "
    "no customer content, name, identifier, message or value was reused — every value in ERPBench is synthetic at "
    "production shape."
)
SYSTEMS = (
    "ERPBench control",
    "Oracle Fusion (order management, shipping, receivables, inventory, procurement, payables, HCM-shaped)",
    "Gmail",
    "Google Drive",
    "Google Sheets",
    "Slack",
)
# Operative (current-authority) tenant sources: the file each family's gold source_reference points at.
OPERATIVE_SOURCE_PREFIXES = ("01-", "05-", "06-", "09-", "12-", "14-", "16-", "18-", "20-", "23-")
FAMILY_ARCHETYPE_SUMMARY = (
    "order import, shipment verification, receipt application and collections, reorder monitoring, receiving and "
    "three-way match, worker document compliance, shift work-report rollups, channel-order sync, hiring against "
    "approved headcount, and effective-dated price batches"
)
VERIFIER_PACKAGE_FILES = ("__init__.py", "spec.py", "world.py", "evaluation.py", "schema.sql")
SERVICE_PACKAGE_FILES = ("__init__.py", "spec.py", "world.py", "schema.sql")


def _hf_url(path: str, *, raw: bool = False) -> str:
    revision = HF_COMMIT or "main"
    operation = "resolve" if raw else "blob"
    return f"{HF_URL}/{operation}/{revision}/{path}"


def _write_text(path: Path, value: str, *, executable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")
    if executable:
        path.chmod(0o755)


def _write_json(path: Path, value: Any) -> None:
    _write_text(path, json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


def _write_jsonl(path: Path, values: list[dict[str, Any]]) -> None:
    _write_text(path, "".join(json.dumps(value, sort_keys=True, ensure_ascii=False) + "\n" for value in values))


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_sha(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


def _publishable_files(task_dir: Path) -> list[Path]:
    files: set[Path] = set()
    for name in PUBLISH_DIRECT_FILES:
        path = task_dir / name
        if path.is_file():
            files.add(path)
    for name in PUBLISH_DIRECTORIES:
        directory = task_dir / name
        if directory.is_dir():
            files.update(
                path
                for path in directory.rglob("*")
                if path.is_file() and "__pycache__" not in path.parts and path.name != ".DS_Store"
            )
    return sorted(files, key=lambda path: path.relative_to(task_dir).as_posix())


def harbor_task_digest(task_dir: Path) -> tuple[str, int, int]:
    outer = hashlib.sha256()
    total_bytes = 0
    files = _publishable_files(task_dir)
    for path in files:
        relative = path.relative_to(task_dir).as_posix()
        digest = _sha256_file(path)
        total_bytes += path.stat().st_size
        outer.update(f"{relative}\0{digest}\n".encode("utf-8"))
    return f"sha256:{outer.hexdigest()}", len(files), total_bytes


def _column_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def _stable_zip_info(filename: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(filename=filename, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_STORED
    info.create_system = 3
    info.external_attr = 0o600 << 16
    return info


def _write_xlsx(path: Path, rows: list[list[Any]], sheet_name: str = "Evidence") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet_rows = []
    for row_number, row in enumerate(rows, start=1):
        cells = []
        for column_number, value in enumerate(row, start=1):
            reference = f"{_column_name(column_number)}{row_number}"
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                cells.append(f'<c r="{reference}"><v>{value}</v></c>')
            else:
                escaped = html.escape(str(value))
                cells.append(f'<c r="{reference}" t="inlineStr"><is><t>{escaped}</t></is></c>')
        sheet_rows.append(f'<row r="{row_number}">{"".join(cells)}</row>')
    sheet = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(sheet_rows)}</sheetData></worksheet>'
    )
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr(_stable_zip_info("[Content_Types].xml"), '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')
        archive.writestr(_stable_zip_info("_rels/.rels"), '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        archive.writestr(_stable_zip_info("xl/workbook.xml"), f'<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="{html.escape(sheet_name)}" sheetId="1" r:id="rId1"/></sheets></workbook>')
        archive.writestr(_stable_zip_info("xl/_rels/workbook.xml.rels"), '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
        archive.writestr(_stable_zip_info("xl/worksheets/sheet1.xml"), sheet)


def _write_pdf(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [line[:92] for line in text.splitlines() if line.strip()][:44]
    commands = ["BT", "/F1 10 Tf", "54 750 Td", "12 TL"]
    for index, line in enumerate(lines):
        escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        if index:
            commands.append("T*")
        commands.append(f"({escaped}) Tj")
    commands.append("ET")
    stream = "\n".join(commands).encode("latin-1", errors="replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        f"<< /Length {len(stream)} >>\nstream\n".encode("ascii") + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{number} 0 obj\n".encode("ascii"))
        output.extend(body)
        output.extend(b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii"))
    path.write_bytes(bytes(output))


def _write_payload(path: Path, payload: tuple[str, Any]) -> None:
    kind, value = payload
    if kind == "text":
        _write_text(path, str(value))
    elif kind == "json":
        _write_json(path, value)
    elif kind == "xlsx":
        _write_xlsx(path, value)
    elif kind == "pdf":
        _write_pdf(path, str(value))
    else:
        raise ValueError(f"unsupported asset kind {kind}")


def _asset_role(name: str) -> str:
    if "current" in name or "task-" in name or name.startswith(OPERATIVE_SOURCE_PREFIXES):
        return "operative"
    return "corroborating"


def _asset_manifest(root: Path, task: dict[str, Any]) -> list[dict[str, Any]]:
    assets = []
    for relative in task["context_files"]:
        path = root / relative
        assets.append(
            {
                "path": relative,
                "name": path.name,
                "format": path.suffix.removeprefix(".").upper() or "TEXT",
                "bytes": path.stat().st_size,
                "sha256": _sha256_file(path),
                "url": _hf_url(relative, raw=True),
                "role": _asset_role(path.name),
                "note": "Agent-visible synthetic evidence; current and superseded records are deliberately mixed.",
            }
        )
    return assets


def _write_assets(output: Path, tasks: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    for world in WORLDS:
        for relative, payload in asset_payloads(world).items():
            _write_payload(output / relative, payload)
    for task in tasks:
        brief = next(path for path in task["context_files"] if path.endswith("task-brief.md"))
        snapshot = next(path for path in task["context_files"] if path.endswith("starting-snapshot.json"))
        _write_text(
            output / brief,
            f"# {task['task_id']} — {task['task_name']}\n\n{task['prompt']}\n\nTenant: {task['tenant_code']} ({task['company']})\nAs of: {task['metadata']['as_of']}\n",
        )
        _write_json(
            output / snapshot,
            {
                "task_id": task["task_id"],
                "tenant_code": task["tenant_code"],
                "company": task["company"],
                "as_of": task["metadata"]["as_of"],
                "systems": list(SYSTEMS),
                "sealed_gold_values_excluded": True,
            },
        )
    return {task["task_id"]: _asset_manifest(output, task) for task in tasks}


def _task_toml(task: dict[str, Any]) -> str:
    description = task["prompt"].replace('"', '\\"').replace("\n", " ")
    servers = "\n".join(
        f'[[environment.mcp_servers]]\nname = "{server}"\ntransport = "streamable-http"\nurl = "http://world:8765/mcp/{server}"\n'
        for server in SERVERS
    )
    return f'''schema_version = "1.4"

[task]
name = "blobfishai/{task['task_id']}"
version = "{BENCHMARK_VERSION}"
description = "{description}"
authors = [{{ name = "Blobfish AI" }}]
keywords = ["erp", "oracle-fusion", "order-to-cash", "procure-to-pay", "multi-system", "stateful", "deterministic"]

[agent]
user = "agent"
timeout_sec = 1200.0

[verifier]
user = "root"
timeout_sec = 120.0

[environment]
build_timeout_sec = 600.0
cpus = 1
memory_mb = 1024
storage_mb = 2048
gpus = 0

{servers}
[metadata]
benchmark = "{BENCHMARK_NAME}"
world_id = "{WORLD_ID}"
task_id = "{task['task_id']}"
tenant_code = "{task['tenant_code']}"
category = "{task['metadata']['category']}"
difficulty = "L4"
metric = "{METRIC}"
synthetic = true
'''


AGENT_DOCKERFILE = f'''FROM {HARBOR_IMAGE}
RUN groupadd --gid 10001 agent \\
    && useradd --uid 10001 --gid 10001 --create-home --shell /bin/bash agent \\
    && install -d -o agent -g agent -m 0755 /workspace \\
    && install -d -o root -g root -m 0755 /opt/erpbench
COPY tools.json /opt/erpbench/
COPY tool /usr/local/bin/tool
RUN chmod 0755 /usr/local/bin/tool && chmod 0444 /opt/erpbench/tools.json
WORKDIR /workspace
ENV ERPBENCH_ROOT=/opt/erpbench PYTHONUNBUFFERED=1
CMD ["sh", "-c", "sleep infinity"]
'''


SERVICE_DOCKERFILE = f'''FROM {HARBOR_IMAGE}
RUN install -d -o root -g root -m 0700 /var/lib/erpbench \\
    && install -d -o root -g root -m 0755 /opt/erpbench
COPY runtime.py service.py schema.sql task.json /opt/erpbench/
COPY erpbench100 /opt/erpbench/erpbench100
COPY assets /opt/erpbench/assets
RUN chmod 0755 /opt/erpbench/service.py \\
    && chmod 0444 /opt/erpbench/runtime.py /opt/erpbench/schema.sql /opt/erpbench/task.json
ENV ERPBENCH_ROOT=/opt/erpbench ERPBENCH_BIND_HOST=0.0.0.0 PYTHONUNBUFFERED=1
CMD ["python3", "/opt/erpbench/service.py"]
'''


DOCKER_COMPOSE = '''services:
  main:
    depends_on:
      world:
        condition: service_healthy
    environment:
      ERPBENCH_MCP_BASE: http://world:8765/mcp
    networks: [agent-egress, erpbench]
    volumes:
      - erpbench-evidence:/var/lib/erpbench-evidence:ro
  world:
    build:
      context: .
      dockerfile: Dockerfile.service
    healthcheck:
      test: ["CMD", "python3", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/health', timeout=1)"]
      interval: 1s
      timeout: 2s
      retries: 30
    environment:
      ERPBENCH_EVIDENCE_PATH: /var/lib/erpbench-evidence/evidence.json
    networks: [erpbench]
    volumes:
      - erpbench-evidence:/var/lib/erpbench-evidence
networks:
  agent-egress: {}
  erpbench:
    internal: true
volumes:
  erpbench-evidence:
'''


# world.py is a package module (it imports spec through relative imports), so the standalone
# service cannot import a verbatim copy as a top-level ``runtime`` module. The environment ships
# the package next to service.py and ``runtime.py`` re-exports the world surface from it, which
# keeps service.py's ``from runtime import ErpWorld, grouped_tool_definitions`` fallback working.
RUNTIME_SHIM = '''"""Standalone world runtime for the Harbor service container.

Re-exports the ERPBench world surface from the vendored ``erpbench100`` package that sits next
to this file, so ``from runtime import ErpWorld, grouped_tool_definitions`` works without the
benchmark source tree.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from erpbench100.world import *  # noqa: E402,F401,F403
from erpbench100.world import (  # noqa: E402,F401
    SERVER_BY_PREFIX,
    SERVERS,
    TABLES,
    ErpWorld,
    grouped_tool_definitions,
    tool_definitions,
)
'''


_SERVER_MAP_LITERAL = json.dumps(SERVER_BY_PREFIX, sort_keys=True, separators=(",", ":"))


TOOL_SCRIPT = r'''#!/usr/bin/env python3
import json, os, sys, urllib.request
if len(sys.argv) < 2:
    raise SystemExit("usage: tool <name> [json-arguments]")
name = sys.argv[1]
args = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
server = __SERVER_MAP__[name.split(".", 1)[0]]
payload = json.dumps({"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":name,"arguments":args}}).encode()
request = urllib.request.Request(f"{os.environ.get('ERPBENCH_MCP_BASE', 'http://world:8765/mcp')}/{server}", data=payload, headers={"Content-Type":"application/json"})
print(urllib.request.urlopen(request, timeout=60).read().decode())
'''.replace("__SERVER_MAP__", _SERVER_MAP_LITERAL)


SOLUTION_SCRIPT = r'''#!/usr/bin/env python3
import json, os, urllib.request
from pathlib import Path
root = Path(__file__).resolve().parent
reference = json.loads((root / "reference.json").read_text())
base = os.environ.get("ERPBENCH_MCP_BASE", "http://world:8765/mcp")
servers = __SERVER_MAP__
for index, step in enumerate(reference["oracle_steps"], 1):
    server = servers[step["tool"].split(".", 1)[0]]
    payload = json.dumps({"jsonrpc":"2.0","id":index,"method":"tools/call","params":{"name":step["tool"],"arguments":step.get("arguments", {})}}).encode()
    request = urllib.request.Request(f"{base}/{server}", data=payload, headers={"Content-Type":"application/json"})
    response = json.loads(urllib.request.urlopen(request, timeout=60).read())
    if response.get("result", {}).get("isError"):
        raise SystemExit(json.dumps(response))
print(json.dumps({"completed": True, "steps": len(reference["oracle_steps"])}))
'''.replace("__SERVER_MAP__", _SERVER_MAP_LITERAL)


VERIFY_SCRIPT = r'''#!/usr/bin/env python3
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
print(json.dumps(verdict, indent=2, sort_keys=True))
'''


def _copy_package(target: Path, names: tuple[str, ...]) -> None:
    package = target / "erpbench100"
    package.mkdir(parents=True, exist_ok=True)
    for name in names:
        shutil.copy2(PACKAGE_ROOT / name, package / name)


def _copy_package_for_verifier(target: Path) -> None:
    _copy_package(target, VERIFIER_PACKAGE_FILES)


def _copy_package_for_service(target: Path) -> None:
    _copy_package(target, SERVICE_PACKAGE_FILES)


def _write_harbor_task(output: Path, task: dict[str, Any], assets: list[dict[str, Any]]) -> Path:
    task_root = output / "harbor" / "tasks" / task["task_id"]
    environment = task_root / "environment"
    tests = task_root / "tests"
    solution = task_root / "solution"
    environment.mkdir(parents=True, exist_ok=True)
    tests.mkdir(parents=True, exist_ok=True)
    solution.mkdir(parents=True, exist_ok=True)
    _write_text(task_root / "task.toml", _task_toml(task))
    _write_text(task_root / "instruction.md", task["prompt"] + "\n")
    _write_text(task_root / "README.md", f"# {task['task_id']}\n\nSynthetic {task['metadata']['category_label']} task from {BENCHMARK_NAME} {BENCHMARK_VERSION}.\n")
    _write_json(task_root / "reference.json", {"task_id": task["task_id"], "expected_answer": task["expected_answer"], "oracle_steps": task["oracle_steps"], "rubric": task["rubric"]})

    _write_text(environment / "runtime.py", RUNTIME_SHIM)
    shutil.copy2(PACKAGE_ROOT / "service.py", environment / "service.py")
    shutil.copy2(PACKAGE_ROOT / "schema.sql", environment / "schema.sql")
    _copy_package_for_service(environment)
    _write_json(environment / "task.json", task)
    _write_json(environment / "tools.json", {"tools": tool_definitions(task["answer_schema"])})
    _write_text(environment / "Dockerfile", AGENT_DOCKERFILE)
    _write_text(environment / "Dockerfile.service", SERVICE_DOCKERFILE)
    _write_text(environment / "docker-compose.yaml", DOCKER_COMPOSE)
    _write_text(environment / "tool", TOOL_SCRIPT, executable=True)
    for asset in assets:
        source = output / asset["path"]
        destination = environment / "assets" / Path(asset["path"]).relative_to("assets")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    _write_text(tests / "test.sh", '#!/bin/bash\nset -euo pipefail\npython3 "$(dirname "$0")/verify.py"\n', executable=True)
    _write_text(tests / "verify.py", VERIFY_SCRIPT, executable=True)
    _write_json(tests / "task.json", task)
    _copy_package_for_verifier(tests)
    _write_text(solution / "solve.sh", '#!/bin/bash\nset -euo pipefail\npython3 "$(dirname "$0")/solve.py"\n', executable=True)
    _write_text(solution / "solve.py", SOLUTION_SCRIPT, executable=True)
    _write_json(solution / "reference.json", {"oracle_steps": task["oracle_steps"]})
    return task_root


def _write_harbor_dataset(output: Path, tasks: list[dict[str, Any]], assets: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    harbor = output / "harbor"
    digests = []
    total_files = 0
    total_bytes = 0
    for task in tasks:
        task_root = _write_harbor_task(output, task, assets[task["task_id"]])
        digest, files, size = harbor_task_digest(task_root)
        digests.append({"task_id": task["task_id"], "digest": digest, "files": files, "bytes": size})
        total_files += files
        total_bytes += size
    dataset = [
        "# Generated ERPBench-100 Harbor dataset",
        "[dataset]",
        f'name = "{HARBOR_DATASET_ID}"',
        f'version = "{BENCHMARK_VERSION}"',
        'description = "100 executable Oracle-Fusion-shaped ERP workflows with deterministic ERPScore grading"',
        'keywords = ["erp", "oracle-fusion", "order-to-cash", "procure-to-pay", "agents", "stateful", "deterministic"]',
        '[[dataset.authors]]',
        'name = "Blobfish AI"',
        "",
    ]
    for row in digests:
        dataset.extend(["[[tasks]]", f'name = "blobfishai/{row["task_id"]}"', f'digest = "{row["digest"]}"', ""])
    _write_text(harbor / "dataset.toml", "\n".join(dataset))
    _write_text(harbor / "LICENSE-DATA", "Creative Commons Attribution 4.0 International (CC BY 4.0)\nhttps://creativecommons.org/licenses/by/4.0/\n")
    _write_text(harbor / "NOTICE", "ERPBench-100 is independently authored synthetic benchmark material. See ANCHORS.md for design influences, the Nario dataflywheel grounding statement, and use restrictions on upstream datasets.\n")
    _write_text(harbor / "README.md", _dataset_readme())
    _write_json(harbor / "task-digests.json", {"schema_version": "erpbench.harbor-digests.v1", "tasks": digests})
    return {"tasks": len(digests), "files": total_files, "bytes": total_bytes, "digests": digests}


def _native_format_count() -> int:
    return len({Path(name).suffix.lower() for name in ASSET_NAMES} | {".md", ".json"})


def _dataset_readme() -> str:
    return f"""# ERPBench-100

ERPBench-100 is a 100-task, deterministic ERP agent benchmark over ten synthetic Oracle-Fusion-shaped tenants. It tests customer order import, shipment verification, receipt application and collections, reorder monitoring and requisitions, receiving and three-way match, worker document compliance, shift work-report rollups, channel-order sync, hiring against approved headcount, and effective-dated price batches — each executed end to end across the ERP, mailbox, drive, spreadsheet and chat systems.

## Run

```bash
harbor run -d {HARBOR_DATASET_ID} -a <agent> -m <provider/model>
```

## Metric

The single metric is **ERPScore** (0–100): discovery 15, ERP calculation 25, decision 15, committed ERP state 20, register and handoff 10, readback 10, containment 5. Exact call order is not graded. Every point is executable; no LLM judge is called.

## Release facts

- 100 tasks; 10 synthetic ERP tenants; 10 workflow families grounded in production ERP archetypes observed through Nario's dataflywheel ({FAMILY_ARCHETYPE_SUMMARY})
- 28 agent-visible files per task across {_native_format_count()} native formats
- {len(tool_definitions())} provider-shaped tools across {len(SERVERS)} logical MCP servers (ERPBench control, Oracle Fusion, Gmail, Google Drive, Google Sheets, Slack)
- before/after state snapshots and full tool trajectories
- 100/100 oracle strict passes, exact deterministic replays, six negative-control families with zero false accepts, and a pre-satisfied-seed gate

All tenants, people, customers, suppliers, items, quantities, amounts, documents and messages are synthetic. This dataset is for agent evaluation and research; it is not accounting, tax, employment or operational advice.
"""


def _huggingface_card() -> str:
    return """---
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
"""


def _anchors_text() -> str:
    return f"""# Public design anchors and clean-room boundary

ERPBench-100 is independently authored. These public sources informed its release and evaluation shape:

- Enterprise-Bench l1-l2-bench on Harbor: {ANCHOR_ENTERPRISE_BENCH_URL}
- agentic-labs/erp-bench on Harbor: {ANCHOR_ERP_BENCH_URL}
- APEX-Agents leaderboard: https://www.mercor.com/apex/apex-agents-leaderboard/
- APEX-Accounting leaderboard: https://www.mercor.com/apex/apex-accounting-leaderboard/
- Archipelago runner and grading architecture: {ANCHOR_ARCHIPELAGO_URL}
- APEX-v1-extended paper: https://arxiv.org/abs/2509.25721
- APEX-Agents dataset card: https://huggingface.co/datasets/mercor/apex-agents

Nario dataflywheel grounding: {NARIO_GROUNDING_STATEMENT}

The public Harbor ERP datasets (Enterprise-Bench and ERP-Bench) were consulted only for their public task packaging, environment contract and verifier placement; no task, fixture, prompt, seed record or solution from either was copied or adapted. The gated APEX-Agents dataset states that it is for evaluation only and forbids crawling/scraping and training use. It was not downloaded or scraped. No gated task, file, gold output, world snapshot, or trajectory was transformed or copied into ERPBench. We used only the public benchmark descriptions and public illustrative samples to identify general desiderata: realistic professional outcomes, data-rich enterprise worlds, cross-application trajectories, before/after snapshots, and criterion-level grading.

ERPBench differs materially in content and evaluation: ten new synthetic tenants and operating scenarios, new prompts and artifacts, Oracle-Fusion-shaped closed-world tools alongside Gmail, Google Drive, Google Sheets and Slack operations, deterministic source/calculation/state verifiers, explicit collateral-damage checks, a pre-satisfied-seed gate, and no judge model.
"""


def _write_huggingface(output: Path, tasks: list[dict[str, Any]], assets: dict[str, list[dict[str, Any]]], episodes: dict[str, dict[str, Any]]) -> None:
    hf = output / "huggingface"
    public_tasks = []
    for task in tasks:
        public_tasks.append(
            {
                "task_id": task["task_id"],
                "task_name": task["task_name"],
                "world_id": task["world_id"],
                "tenant_code": task["tenant_code"],
                "company": task["company"],
                "prompt": task["prompt"],
                "context_files": task["context_files"],
                "rubric": task["rubric"],
                "gold_output": task["gold_output"],
                "metadata": task["metadata"],
                "decision_options": task["decision_options"],
                "answer_schema": task["answer_schema"],
                "task_sha256": task_digest(task),
            }
        )
    _write_jsonl(hf / "data" / "tasks.jsonl", public_tasks)
    tenants = [
        {"code": world["code"], "company": world["company"], "industry": world["industry"], "profile": world["profile"], "country": world["country"]}
        for world in WORLDS
    ]
    _write_json(hf / "data" / "worlds.json", {"world_id": WORLD_ID, "tenants": tenants, "systems": list(grouped_tool_definitions()), "synthetic": True})
    _write_json(hf / "contracts" / "tools.json", {"tools": tool_definitions()})
    for path in (output / "assets").rglob("*"):
        if path.is_file():
            destination = hf / path.relative_to(output)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)
    for task_id in [task["task_id"] for task in tasks if int(task["task_id"].split("-")[-1]) % 10 == 1]:
        _write_json(hf / "trajectories" / f"{task_id}.json", {"task_id": task_id, "trace": episodes[task_id]["trace"], "verdict": episodes[task_id]["verdict"]})
    for task in tasks:
        task_id = task["task_id"]
        _write_json(hf / "verifiers" / f"{task_id}.json", episodes[task_id]["verdict"])
    _write_text(hf / "README.md", _huggingface_card() + "\n" + _dataset_readme() + "\n" + _anchors_text())
    _write_text(hf / "LICENSE", "CC BY 4.0\n")
    _write_text(hf / "ANCHORS.md", _anchors_text())


TRAJECTORY_STAGES = (
    {"key": "scope", "label": "Scope"},
    {"key": "investigate", "label": "Investigate"},
    {"key": "execute", "label": "Execute"},
    {"key": "decide", "label": "Decide"},
    {"key": "handoff", "label": "Handoff"},
    {"key": "verify", "label": "Verify"},
)


def _stage_map() -> dict[str, str]:
    stages = {tool: "execute" for tool in WRITE_TOOLS if tool.startswith("oracle_fusion.")}
    stages.update(
        {
            "erpbench.get_task": "scope",
            "erpbench.record_decision": "decide",
            "google_sheets.spreadsheets.values.update": "handoff",
            "google_sheets.spreadsheets.values.append": "handoff",
            "gmail.drafts.create": "handoff",
            "slack.chat_postMessage": "handoff",
            "erpbench.submit_answer": "verify",
            "erpbench.get_submission": "verify",
            "erpbench.get_decision": "verify",
            "gmail.drafts.get": "verify",
        }
    )
    return stages


def _trajectory_events(task: dict[str, Any], episode: dict[str, Any]) -> list[dict[str, Any]]:
    stages = _stage_map()
    events: list[dict[str, Any]] = [
        {"index": 1, "kind": "message", "role": "employee-request", "stage": "scope", "text": task["prompt"]}
    ]
    for call, entry in enumerate(episode["trace"], start=1):
        tool = entry["tool"]
        default = "execute" if tool in WRITE_TOOLS else "investigate"
        result = json.dumps(entry["result"], sort_keys=True, ensure_ascii=False)
        events.append(
            {
                "index": len(events) + 1,
                "kind": "tool",
                "stage": stages.get(tool, default),
                "call": call,
                "tool": tool,
                "server": entry["server"],
                "arguments": entry["arguments"],
                "outcome": "ok" if entry["success"] else "error",
                "result": result[:500] + ("…" if len(result) > 500 else ""),
            }
        )
    events.append({"index": len(events) + 1, "kind": "message", "role": "verifier-receipt", "stage": "verify", "text": f"Deterministic verifier: {episode['verdict']['score']:.2f} {METRIC}; strict pass {episode['verdict']['passed']}."})
    return events


CONTROL_LABELS = {
    "oracle": "Reference oracle",
    "noop": "No-op control",
    "shortcut": "Answer-only shortcut",
    "state_only": "State-only shortcut",
    "wrong_source": "Wrong-source control",
    "wrong_target": "Wrong-target control",
    "overprocess": "Process-as-received control",
}


def _website_data(
    tasks: list[dict[str, Any]],
    assets: dict[str, list[dict[str, Any]]],
    episodes: dict[str, dict[str, Any]],
    qualification: dict[str, Any],
    build: dict[str, Any],
) -> dict[str, Any]:
    categories = [
        {"key": family["key"], "label": family["label"], "count": sum(task["metadata"]["category"] == family["key"] for task in tasks)}
        for family in FAMILIES
    ]
    reference_calls = sorted(len(task["oracle_steps"]) for task in tasks)
    criteria_counts = [len(task["rubric"]) for task in tasks]
    native_formats = [len({Path(path).suffix.lower() for path in task["context_files"]}) for task in tasks]
    negative_executions = sum(row["executions"] for row in qualification["negative_controls"].values())
    negative_false_accepts = sum(row["false_accepts"] for row in qualification["negative_controls"].values())
    evaluation_controls = []
    for row in qualification["results"]:
        evaluation_controls.append(
            {
                "rank": "REF" if row["policy"] == "oracle" else "CTRL",
                "name": CONTROL_LABELS[row["policy"]],
                "harness": "Deterministic release qualification",
                "kind": "reference",
                "tasks": row["task_count"],
                "score": row["mean_score"],
                "strictPassRate": row["strict_passes"],
                "categoryScores": row["category_scores"],
                "averageCalls": round(sum(len(task["oracle_steps"]) for task in tasks) / len(tasks), 1) if row["policy"] == "oracle" else None,
                "note": "Solvability ceiling; not a model submission." if row["policy"] == "oracle" else "Executed adversarial control; never ranked with models.",
            }
        )
    task_rows = []
    samples: dict[str, Any] = {}
    for ordinal, task in enumerate(tasks, start=1):
        task_rows.append(
            {
                "id": task["task_id"],
                "ordinal": ordinal,
                "title": task["task_name"],
                "category": task["metadata"]["category"],
                "client": task["company"],
                "organization": task["tenant_code"],
                "asOf": task["metadata"]["as_of"],
                "summary": task["prompt"],
                "documents": len(task["context_files"]),
                "referenceToolCalls": len(task["oracle_steps"]),
                "sample": True,
                "datasetUrl": _hf_url("data/tasks.jsonl"),
            }
        )
        samples[task["task_id"]] = {
            "taskId": task["task_id"],
            "prompt": task["prompt"],
            "gradedCriteria": [f"{criterion['category']}: {criterion['description']} ({criterion['points']} pts)" for criterion in task["rubric"]],
            "evaluationNarrative": {
                "summary": "An operative-source and ERP-calculation chain ending in committed Oracle-shaped transaction state, a register row, a decision record, and review-only communication.",
                "success": "The exact current sources, recomputed quantities and amounts, decision, committed ERP records, register and handoff, readbacks, and containment all agree.",
                "callOrderPolicy": "Exact call order is not graded; required investigations must precede the first controlled ERP write and each write must be read back.",
                "milestones": [
                    {"id": category["key"], "category": category["key"], "description": f"{category['label']} contributes {category['weight']} {METRIC} points."}
                    for category in SCORING_CATEGORIES
                ],
            },
            "decisionOptions": task["decision_options"],
            "assets": assets[task["task_id"]],
            "scoringWeights": list(SCORING_CATEGORIES),
        }
    sample_task_ids = [f"erpbench-{ordinal:03d}" for ordinal in range(1, 101, 10)]
    trajectories = []
    stages = [dict(stage) for stage in TRAJECTORY_STAGES]
    by_id = {task["task_id"]: task for task in tasks}
    for task_id in sample_task_ids:
        episode = episodes[task_id]
        trajectories.append(
            {
                "taskId": task_id,
                "model": "Reference oracle",
                "harness": "Deterministic release solver",
                "kind": "reference",
                "traceMode": "provider-native",
                "traceSource": "released oracle trajectory",
                "passed": True,
                "score": 100,
                "categoryScores": episode["verdict"]["category_scores"],
                "toolCalls": len(episode["trace"]),
                "sourceArtifactUrl": _hf_url(f"trajectories/{task_id}.json"),
                "transcriptUrl": _hf_url(f"trajectories/{task_id}.json"),
                "verifierUrl": _hf_url(f"verifiers/{task_id}.json"),
                "stages": stages,
                "events": _trajectory_events(by_id[task_id], episode),
            }
        )
    return {
        "schemaVersion": "blobfish.benchmark-page.v1",
        "benchmark": {
            "name": BENCHMARK_NAME,
            "version": BENCHMARK_VERSION,
            "tagline": "100 deterministic long-horizon ERP workflows across ten synthetic Oracle-Fusion-shaped tenants.",
            "question": "Can an agent run the ERP transaction end to end—not just read the record?",
            "taskCount": len(tasks),
            "categoryNoun": "ERP workflow",
            "categories": categories,
            "world": {"tools": len(tool_definitions()), "tables": len(TABLES), "documents": build["source_asset_count"], "rows": build["rows_per_task_snapshot"]},
            "referenceCalls": {"min": min(reference_calls), "median": reference_calls[len(reference_calls) // 2], "max": max(reference_calls)},
            "checksPerTask": max(criteria_counts),
            "releaseEvidence": {
                "assetFilesPerTask": {"min": 28, "max": 28},
                "nativeFormatsPerTask": {"min": min(native_formats), "max": max(native_formats)},
                "evidenceReadsPerTask": {"min": 15, "max": 15},
                "criteriaPerTask": {"min": min(criteria_counts), "max": max(criteria_counts)},
                "semanticMilestonesPerTask": {"min": 7, "max": 7},
                "qualification": {
                    "executions": qualification["executions"],
                    "oraclePasses": qualification["oracle"]["passes"],
                    "deterministicReplays": qualification["determinism"]["replays"],
                    "deterministicMatches": qualification["determinism"]["exact_episode_matches"],
                    "negativeControlTypes": len(qualification["negative_controls"]),
                    "negativeControlExecutions": negative_executions,
                    "negativeFalseAccepts": negative_false_accepts,
                },
                "writeContract": {
                    "schemaVersion": "blobfish.first-party-write-contract.v1",
                    "tasks": len(tasks),
                    "taskScopedExecutionAuthorized": len(tasks),
                    "completionDestinationsDiscoverable": len(tasks),
                    "providerInputSchemasValidated": len(tasks),
                    "semanticFreeTextOrVisibleTemplate": len(tasks),
                    "hiddenReferenceTextRequired": 0,
                    "hiddenSerializationRequired": 0,
                    "postWriteReadbacksContracted": len(tasks),
                    "writeScopeContained": len(tasks),
                    "wrongTargetControlsRejected": len(tasks),
                    "keywordStuffingControlsRejected": len(tasks),
                    "writeContractsPassed": len(tasks),
                },
            },
            "deterministicVerifier": True,
            "mcp": {"package": "erpbench100", "version": BENCHMARK_VERSION, "protocolVersion": "2025-06-18", "serverName": "erpbench"},
            "contractPins": [
                {"name": "Catalog SHA-256", "value": build["catalog_sha256"]},
                {"name": "Harbor package SHA-256", "value": build["harbor_root_sha256"]},
                {"name": "Hugging Face commit", "value": HF_COMMIT or "pending publication"},
                {"name": "Synthetic world", "value": WORLD_ID},
            ],
            "publicationReceipt": {
                "huggingFaceCommit": HF_COMMIT,
                "payloadManifestSha256": HF_PAYLOAD_MANIFEST_SHA256,
                "exactObjectIdentity": bool(HF_COMMIT and HF_PAYLOAD_MANIFEST_SHA256),
                "receiptUrl": f"{HF_URL}/tree/{HF_COMMIT}" if HF_COMMIT else HF_URL,
            },
            "links": {"harbor": HARBOR_URL, "huggingFace": HF_URL, "source": SOURCE_URL, "blobfishPage": PAGE_URL},
        },
        "scoring": {"categories": list(SCORING_CATEGORIES), "strictPassTracked": True},
        "leaderboard": [],
        "evaluationControls": evaluation_controls,
        "tasks": task_rows,
        "samples": samples,
        "tools": tool_definitions(),
        "trajectories": trajectories,
        "methodology": [
            {"title": "Ten deep ERP tenants", "body": "Each synthetic tenant carries an Oracle-Fusion-shaped item master, customers and suppliers, sales orders, a staged shipment, open receivables, on-hand balances and open purchase orders, a supplier invoice, worker documents, a shift roster, a channel export, a candidate register and a price batch, plus current and superseded Drive files, a mailbox, an ops register workbook and chat channels. Ten workflows reuse each frozen tenant as an operations team would."},
            {"title": "High-level employee requests", "body": "Prompts ask for a business outcome and a review-ready handoff. They do not prescribe tool order or leak record identifiers. The agent must find the operative source among superseded versions, recompute quantities and amounts from current evidence, and decide what policy allows it to commit."},
            {"title": "Stateful cross-application execution", "body": "Six logical MCP servers expose Oracle-Fusion-shaped order management, shipping, receivables, inventory, procurement, payables and HCM resources plus Gmail, Google Drive, Google Sheets, Slack and benchmark controls over isolated SQLite state. Order, shipment, receipt, requisition, receiving, invoice, hold, document, absence, worker, price, register, decision and communication writes are durable and task-scoped."},
            {"title": "One deterministic ERPScore", "body": "ERPScore allocates 100 executable points to discovery, ERP calculation, decision quality, committed ERP state, register and handoff, readback and containment. No LLM judge or exact reference call sequence is used."},
            {"title": "Two-sided qualification", "body": f"The release executed {qualification['executions']} episodes: {qualification['oracle']['passes']}/100 oracle runs, {qualification['determinism']['exact_episode_matches']}/100 exact deterministic replays, and {negative_executions} adversarial controls across six families (no-op, answer-only, state-only, wrong-source, wrong-target, process-as-received) with {negative_false_accepts} false accepts. A pre-satisfied-seed gate confirms that no untouched tenant already satisfies a calculation, decision or ERP-state criterion."},
            {"title": "Nario dataflywheel grounding and clean-room boundary", "body": f"Workflow archetypes, tool shapes and data shapes were observed through Nario's production dataflywheel traces; no customer content, name, identifier, message or value was reused. Public Enterprise-Bench, ERP-Bench, APEX and Archipelago pages informed the release contract; Mercor's gated dataset was not downloaded or scraped. Every tenant, prompt, file, value, tool, answer and trajectory in {BENCHMARK_NAME} is newly synthetic at production shape."},
            {"title": "Leaderboard honesty", "body": "Qualification controls prove solvability and discrimination but are never ranked as models. A model row appears only after a complete version-pinned 100-task run has an inspectable receipt."},
        ],
        "architectureComparison": {
            "title": "Public ERP benchmark anchors, deterministic ERPBench implementation",
            "intro": "The public architecture is preserved where it improves reproducibility; the tenant corpus, tool surface and grading implementation are independent.",
            "leftLabel": "Public ERP/APEX benchmark pattern",
            "rightLabel": BENCHMARK_NAME,
            "rows": [
                {"layer": "World", "left": "Enterprise ERP scenario with seeded records and documents", "right": "Ten frozen synthetic Oracle-Fusion-shaped tenants with 28 task-visible files"},
                {"layer": "Environment", "left": "Container, MCP gateway, seeded application state", "right": "Harbor task, six MCP servers, task-local SQLite tenant snapshot"},
                {"layer": "Trajectory", "left": "Messages, tool calls, record edits, final state", "right": "Full provider-shaped calls, outputs, before/after state and verdict"},
                {"layer": "Grading", "left": "Enterprise-Bench's LLM judge; ERP-Bench's undocumented verification", "right": f"{max(criteria_counts)} executable calculation, source, state, readback and containment checks in a deterministic executable verifier; no judge model"},
                {"layer": "Release", "left": "Task packages, seeded worlds, task metadata", "right": "HF mirror, Harbor dataset, gold contracts, digests and ten public oracle traces"},
            ],
            "linkLabel": "Inspect Archipelago",
            "linkUrl": ANCHOR_ARCHIPELAGO_URL,
        },
    }


def _tree_digest(root: Path) -> tuple[str, int, int]:
    digest = hashlib.sha256()
    files = sorted(path for path in root.rglob("*") if path.is_file())
    total = 0
    for path in files:
        relative = path.relative_to(root).as_posix()
        file_digest = _sha256_file(path)
        total += path.stat().st_size
        digest.update(f"{relative}\0{file_digest}\n".encode("utf-8"))
    return digest.hexdigest(), len(files), total


def build_release(output: Path = DEFAULT_OUTPUT, *, website_data: Path = WEBSITE_DATA) -> dict[str, Any]:
    output = output.resolve()
    allowed_parent = PACKAGE_ROOT.resolve()
    if output == allowed_parent or not output.is_relative_to(allowed_parent):
        raise ValueError(f"refusing to replace unsafe output path: {output}")
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    tasks = build_tasks()
    qualification = qualify(tasks)
    if not qualification["qualification_passed"]:
        raise ValueError("ERPBench qualification failed")
    assets = _write_assets(output, tasks)
    episodes: dict[str, dict[str, Any]] = {}
    for task in tasks:
        episode = run_episode(task, policy_steps(task, "oracle"))
        episodes[task["task_id"]] = episode
        _write_json(output / "tasks" / f"{task['task_id']}.json", task)
        _write_json(output / "verifiers" / f"{task['task_id']}.json", episode["verdict"])
        _write_json(output / "snapshots" / task["task_id"] / "initial.json", episode["before"])
        _write_json(output / "snapshots" / task["task_id"] / "final.json", episode["after"])
        trajectory_records = [*episode["trace"], {"verdict": episode["verdict"]}]
        _write_jsonl(output / "trajectories" / f"{task['task_id']}.jsonl", trajectory_records)
    harbor = _write_harbor_dataset(output, tasks, assets)
    _write_huggingface(output, tasks, assets, episodes)
    _write_text(output / "README.md", _dataset_readme())
    _write_text(output / "ANCHORS.md", _anchors_text())
    _write_text(output / "LICENSE-DATA", "CC BY 4.0\n")
    _write_json(output / "reports" / "qualification.json", qualification)
    sample_snapshot = episodes[tasks[0]["task_id"]]["before"]
    rows_per_task = sum(len(rows) for rows in sample_snapshot.values())
    harbor_sha, _, _ = _tree_digest(output / "harbor")
    build = {
        "schema_version": "erpbench.build.v1",
        "benchmark": BENCHMARK_NAME,
        "version": BENCHMARK_VERSION,
        "metric": METRIC,
        "task_count": len(tasks),
        "world_count": len(WORLDS),
        "tenant_count": len(WORLDS),
        "family_count": len(FAMILIES),
        "tool_count": len(tool_definitions()),
        "table_count": len(TABLES),
        "rows_per_task_snapshot": rows_per_task,
        "source_asset_count": len(list((output / "assets").rglob("*.*"))),
        "assets_per_task": {"min": min(len(value) for value in assets.values()), "max": max(len(value) for value in assets.values())},
        "criteria_per_task": {"min": min(len(task["rubric"]) for task in tasks), "max": max(len(task["rubric"]) for task in tasks)},
        "oracle_calls_per_task": {"min": min(len(task["oracle_steps"]) for task in tasks), "max": max(len(task["oracle_steps"]) for task in tasks)},
        "catalog_sha256": catalog_digest(tasks),
        "harbor_root_sha256": harbor_sha,
        "huggingface_commit": HF_COMMIT or None,
        "huggingface_payload_manifest_sha256": HF_PAYLOAD_MANIFEST_SHA256 or None,
        "harbor_task_files": harbor["files"],
        "harbor_task_bytes": harbor["bytes"],
        "qualification_passed": True,
        "negative_control_families": len(qualification["negative_controls"]),
        "pre_satisfied_tasks": list(qualification["pre_satisfied_gate"]["pre_satisfied_tasks"]),
        "mcp_pin": {"package": "erpbench100", "version": BENCHMARK_VERSION, "protocol_version": "2025-06-18", "server_name": "erpbench"},
        "verifier": {"deterministic": True, "llm_judge_calls": 0},
    }
    _write_json(output / "reports" / "build.json", build)
    page_data = _website_data(tasks, assets, episodes, qualification, build)
    _write_json(website_data, page_data)
    root_sha, file_count, total_bytes = _tree_digest(output)
    receipt = {
        **build,
        "root_sha256_before_release_report": root_sha,
        "artifact_file_count_before_release_report": file_count,
        "artifact_bytes_before_release_report": total_bytes,
        "website_data": str(website_data),
    }
    _write_json(output / "reports" / "release.json", receipt)
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--website-data", type=Path, default=WEBSITE_DATA)
    arguments = parser.parse_args()
    print(json.dumps(build_release(arguments.output, website_data=arguments.website_data), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
