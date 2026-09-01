"""Deterministic ERPScore evaluation and qualification controls."""

from __future__ import annotations

import json
import statistics
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any

from .spec import METRIC, NUMERIC_FIELDS, SCORING_CATEGORIES, _register_row, _register_row_number, build_tasks, world_model
from .world import IMMUTABLE_TABLES, WRITE_TOOLS, ErpWorld

POLICIES = ("oracle", "noop", "shortcut", "state_only", "wrong_source", "wrong_target", "overprocess")

# Tables every task may change (register, handoff, decision, answer, audit) and
# the ERP tables each workflow family is authorized to change. Anything else is
# an out-of-scope write and fails containment even when the provider accepts it.
COMMON_WRITE_TABLES = frozenset({"spreadsheets", "sheet_changes", "mail_drafts", "chat_posts", "decisions", "submissions", "audit_log"})
FAMILY_WRITE_TABLES: dict[str, frozenset[str]] = {
    "order_import": frozenset({"sales_orders"}),
    "shipment_verification": frozenset({"shipment_lines"}),
    "receivables_collection": frozenset({"standard_receipts", "receivables_invoices"}),
    "inventory_reorder": frozenset({"purchase_requisitions"}),
    "receiving_ap_match": frozenset({"receiving_receipt_requests", "purchase_order_lines", "ap_invoices", "invoice_holds"}),
    "document_compliance": frozenset({"document_records"}),
    "shift_rollup": frozenset({"absences"}),
    "channel_order_sync": frozenset({"sales_orders"}),
    "hire_against_requisition": frozenset({"workers"}),
    "price_list_batch": frozenset({"items"}),
}


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _equal(actual: Any, expected: Any) -> bool:
    if isinstance(expected, bool):
        return actual is expected or actual == expected
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        try:
            return abs(float(actual) - float(expected)) <= 0.005
        except (TypeError, ValueError):
            return False
    return actual == expected


def _successful(trace: list[dict[str, Any]], tool: str) -> list[dict[str, Any]]:
    return [entry for entry in trace if entry.get("success") and entry.get("tool") == tool]


def _call_matches(entry: dict[str, Any], requirement: dict[str, Any]) -> bool:
    if entry.get("tool") != requirement.get("tool") or not entry.get("success"):
        return False
    if "arguments" in requirement:
        return _canonical(entry.get("arguments", {})) == _canonical(requirement["arguments"])
    actual = entry.get("arguments", {}) or {}
    for key, fragment in (requirement.get("arguments_contains") or {}).items():
        value = actual.get(key)
        if value is None:
            return False
        haystack = value if isinstance(value, str) else _canonical(value)
        if str(fragment).lower() not in haystack.lower():
            return False
    return True


def _read_after(trace: list[dict[str, Any]], read_tool: str, write_tool: str) -> bool:
    write_indexes = [entry["index"] for entry in _successful(trace, write_tool)]
    if not write_indexes:
        return False
    first_write = min(write_indexes)
    return any(entry["index"] > first_write for entry in _successful(trace, read_tool))


def _table(snapshot: dict[str, list[dict[str, Any]]], table: str) -> list[dict[str, Any]]:
    return snapshot.get(table, [])


def _one(snapshot: dict[str, list[dict[str, Any]]], table: str, **match: Any) -> dict[str, Any] | None:
    for row in _table(snapshot, table):
        if all(row.get(key) == value for key, value in match.items()):
            return row
    return None


def _many(snapshot: dict[str, list[dict[str, Any]]], table: str, **match: Any) -> list[dict[str, Any]]:
    return [row for row in _table(snapshot, table) if all(row.get(key) == value for key, value in match.items())]


def _same_row(before: dict[str, list[dict[str, Any]]], after: dict[str, list[dict[str, Any]]], table: str, key: str, value: Any) -> bool:
    return _one(before, table, **{key: value}) == _one(after, table, **{key: value})


def _line_set(lines: list[dict[str, Any]], *fields: str) -> set[tuple[Any, ...]]:
    result = set()
    for line in lines:
        result.add(tuple(round(float(line.get(field)), 2) if isinstance(line.get(field), (int, float)) and not isinstance(line.get(field), bool) else line.get(field) for field in fields))
    return result


def _erp_state(task: dict[str, Any], before: dict[str, list[dict[str, Any]]], after: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """Return primary/secondary/forbidden/unrelated verdicts for the task's family."""

    task_id = task["task_id"]
    category = task["metadata"]["category"]
    model = world_model(task["tenant_code"])
    world = model["world"]
    section = model[category]
    customer = world["customer"]
    result = {"primary": False, "secondary": False, "forbidden": False, "unrelated": True, "evidence": {}}

    if category == "order_import":
        created = _many(after, "sales_orders", last_task_id=task_id)
        expected_lines = _line_set([{"ProductNumber": line["item_number"], "OrderedQuantity": line["quantity"], "UnitListPrice": line["list_price"]} for line in section["lines"] if line["disposition"] == "accepted"], "ProductNumber", "OrderedQuantity", "UnitListPrice")
        order = created[0] if len(created) == 1 else None
        result["primary"] = bool(order and order["customer_po_number"] == customer["po"] and order["source_transaction_number"] == section["batch_file_id"] and order["buying_party_number"] == customer["number"] and _line_set(order["lines"], "ProductNumber", "OrderedQuantity", "UnitListPrice") == expected_lines and _equal(order["order_total"], section["order_total"]))
        result["secondary"] = bool(order and bool(order["submitted_flag"]) == (not section["credit_hold"]) and order["source_transaction_system"] == "OPS")
        prior_items = {(line["item_number"], line["quantity"]) for line in section["lines"] if line["previously_imported"]}
        result["forbidden"] = len(created) > 1 or any((line["ProductNumber"], line["OrderedQuantity"]) in prior_items for row in created for line in row["lines"])
        result["unrelated"] = _same_row(before, after, "sales_orders", "order_number", section["prior_order_number"]) and _same_row(before, after, "sales_orders", "order_number", f"SO-{world['short']}-DECOY")
        result["evidence"] = {"created_orders": [row["order_number"] for row in created]}
    elif category == "shipment_verification":
        corrected_ok = []
        touched_forbidden = False
        for line in section["lines"]:
            row = _one(after, "shipment_lines", shipment_line_id=line["shipment_line_id"])
            if line["disposition"] == "corrected":
                corrected_ok.append(bool(row and row["shipped_quantity"] == line["picked"] and row["last_task_id"] == task_id))
            else:
                if not _same_row(before, after, "shipment_lines", "shipment_line_id", line["shipment_line_id"]):
                    touched_forbidden = True
        decoy_same = _same_row(before, after, "shipment_lines", "shipment_line_id", 700000 + len(world["short"]))
        commented = [bool((row := _one(after, "shipment_lines", shipment_line_id=line["shipment_line_id"])) and row["last_task_id"] == task_id and str(row.get("comments") or "").strip()) for line in section["lines"] if line["disposition"] == "corrected"]
        result["primary"] = bool(corrected_ok) and all(corrected_ok)
        result["secondary"] = bool(commented) and all(commented) and not touched_forbidden and decoy_same
        result["forbidden"] = touched_forbidden or not decoy_same
        result["unrelated"] = decoy_same
        result["evidence"] = {"corrected_lines_ok": corrected_ok}
    elif category == "receivables_collection":
        receipts = _many(after, "standard_receipts", last_task_id=task_id)
        receipt = receipts[0] if len(receipts) == 1 else None
        expected_refs = {(number, round(next(row["amount"] for row in section["invoices"] if row["transaction_number"] == number), 2)) for number in section["covered_invoices"]}
        actual_refs = {(ref.get("ReferenceNumber"), round(float(ref.get("ApplyAmount", 0)), 2)) for ref in (receipt["remittance_references"] if receipt else [])}
        result["primary"] = bool(receipt and receipt["receipt_number"] == section["receipt_number"] and _equal(receipt["receipt_amount"], section["receipt_amount"]) and receipt["customer_account_number"] == customer["number"] and receipt["receipt_date"] == section["receipt_date"] and actual_refs == expected_refs)
        covered_closed = all((row := _one(after, "receivables_invoices", transaction_number=number)) is not None and _equal(row["balance_due"], 0) and row["invoice_status"] == "Closed" for number in section["covered_invoices"])
        uncovered_same = all(_same_row(before, after, "receivables_invoices", "transaction_number", row["transaction_number"]) for row in section["invoices"] if not row["covered"])
        result["secondary"] = covered_closed and uncovered_same
        result["forbidden"] = len(receipts) > 1 or not uncovered_same
        result["unrelated"] = _same_row(before, after, "receivables_invoices", "transaction_number", f"INV-{world['short']}-DECOY")
        result["evidence"] = {"receipts": [row["receipt_number"] for row in receipts]}
    elif category == "inventory_reorder":
        requisitions = _many(after, "purchase_requisitions", last_task_id=task_id)
        requisition = requisitions[0] if len(requisitions) == 1 else None
        expected_lines = {(sku["item_number"], sku["reorder_qty"], round(sku["unit_cost"], 2)) for sku in section["skus"] if sku["below"]}
        actual_lines = _line_set(requisition["lines"], "ItemNumber", "Quantity", "UnitPrice") if requisition else set()
        supplier_ok = bool(requisition) and all(line.get("Supplier") == world["supplier"]["name"] for line in requisition["lines"])
        result["primary"] = bool(requisition and actual_lines == expected_lines and _equal(requisition["total_amount"], section["requisition_amount"]) and supplier_ok)
        result["secondary"] = bool(requisition and requisition["document_status"] == "Pending approval")
        below_items = {sku["item_number"] for sku in section["skus"] if sku["below"]}
        result["forbidden"] = len(requisitions) > 1 or any(line.get("ItemNumber") not in below_items or line.get("Supplier") == world["expedite_supplier"]["name"] for row in requisitions for line in row["lines"])
        result["evidence"] = {"requisitions": [row["requisition_number"] for row in requisitions]}
    elif category == "receiving_ap_match":
        receipts = _many(after, "receiving_receipt_requests", last_task_id=task_id)
        received = set()
        for row in receipts:
            for line in row["lines"]:
                received.add((line.get("DocumentNumber"), int(line.get("DocumentLineNumber")), int(line.get("Quantity"))))
        expected_received = {(section["po"], line["line"], line["received"]) for line in section["lines"]}
        invoices = _many(after, "ap_invoices", last_task_id=task_id)
        invoice = next((row for row in invoices if row["invoice_number"] == section["invoice_number"]), None)
        expected_invoice_lines = {(line["line"], line["invoiced_qty"], round(line["invoice_price"], 2)) for line in section["lines"]}
        actual_invoice_lines = _line_set(invoice["lines"], "PurchaseOrderLineNumber", "Quantity", "UnitPrice") if invoice else set()
        result["primary"] = bool(received == expected_received and invoice and _equal(invoice["invoice_amount"], section["invoice_total"]) and actual_invoice_lines == expected_invoice_lines and invoice["supplier"] == world["supplier"]["name"])
        holds = _many(after, "invoice_holds", invoice_id=invoice["invoice_id"]) if invoice else []
        if section["held_lines"]:
            held_numbers = [str(line["line"]) for line in section["lines"] if not line["matched"]]
            result["secondary"] = bool(invoice and invoice["validation_status"] == "On hold" and holds and all(any(f"line {number}" in hold["hold_reason"] for hold in holds) for number in held_numbers))
            result["forbidden"] = bool(invoice and invoice["validation_status"].startswith("Validated"))
        else:
            result["secondary"] = bool(invoice and invoice["validation_status"] == "Validated" and not holds)
            result["forbidden"] = bool(holds)
        result["forbidden"] = result["forbidden"] or len(invoices) > 1
        result["unrelated"] = _same_row(before, after, "purchase_orders", "po_number", f"PO-{world['short']}-CLOSED")
        result["evidence"] = {"received": sorted(received), "invoice": invoice["invoice_number"] if invoice else None, "holds": len(holds)}
    elif category == "document_compliance":
        alert_ok = []
        verify_ok = []
        forbidden = False
        for doc in section["documents"]:
            row = _one(after, "document_records", document_record_id=doc["document_record_id"])
            if row is None:
                alert_ok.append(False)
                continue
            if doc["needs_alert"]:
                alert_ok.append(row["status"] == "ALERTED" and row["last_task_id"] == task_id)
            elif not doc["alerted"] and row["status"] == "ALERTED":
                forbidden = True
            if doc["check_pending"] and not doc["blocked"]:
                verify_ok.append(bool(row["verified_flag"]) and row["last_task_id"] == task_id)
            elif row["verified_flag"]:
                forbidden = True
        result["primary"] = bool(alert_ok) and all(alert_ok)
        result["secondary"] = bool(verify_ok) and all(verify_ok) and not forbidden
        result["forbidden"] = forbidden
        result["evidence"] = {"alerts": alert_ok, "verifications": verify_ok}
    elif category == "shift_rollup":
        created = _many(after, "absences", last_task_id=task_id)
        created_people = {row["person_number"] for row in created}
        result["primary"] = bool(created) and created_people == set(section["missing"]) and all(row["absence_type"] == "Unauthorized absence" and row["start_date"] == section["shift_date"] and row["end_date"] == section["shift_date"] for row in created)
        result["secondary"] = bool(created) and all(row["employer"] == world["company"] and row["absence_status"] == "SUBMITTED" for row in created) and len(created) == len(section["missing"])
        result["forbidden"] = bool(created_people - set(section["missing"]))
        result["unrelated"] = all(_same_row(before, after, "absences", "person_number", code_) for code_ in section["approved_absent"])
        result["evidence"] = {"absences": sorted(created_people)}
    elif category == "channel_order_sync":
        created = _many(after, "sales_orders", last_task_id=task_id)
        expected_rows = {row["channel_order_id"]: row for row in section["rows"] if row["disposition"] == "create"}
        by_source = {row["source_transaction_number"]: row for row in created}
        result["primary"] = set(by_source) == set(expected_rows) and all(row["source_transaction_system"] == world["channel"] and _equal(row["order_total"], expected_rows[source]["total"]) and bool(row["submitted_flag"]) for source, row in by_source.items())
        appended = [change for change in _many(after, "sheet_changes", task_id=task_id) if change["operation"] == "append" and change["cell_range"].startswith("Customers!")]
        new_customer = section["new_customer"]
        result["secondary"] = any(all(any(needle in str(cell) for cell in row) for needle in (new_customer["name"], new_customer["tax_id"], new_customer["email"])) for change in appended for row in change["values"])
        result["forbidden"] = bool(set(by_source) - set(expected_rows)) or len(created) != len(expected_rows)
        result["unrelated"] = all(_same_row(before, after, "sales_orders", "order_number", row["synced_order_number"]) for row in section["rows"] if row["already_synced"])
        result["evidence"] = {"created": sorted(by_source)}
    elif category == "hire_against_requisition":
        created = _many(after, "workers", last_task_id=task_id)
        expected_ids = {candidate["candidate_id"] for candidate in section["hired"]}
        actual_ids = {row["candidate_id"] for row in created}
        result["primary"] = bool(section["hired"]) and actual_ids == expected_ids and all(row["job_code"] == section["job"] and row["contract_end_date"] == section["contract_end"] and _equal(row["monthly_salary"], section["wage"]) for row in created)
        eligible_ids = {candidate["candidate_id"] for candidate in section["candidates"] if candidate["eligible"]}
        result["secondary"] = bool(created) and len(created) == section["hires"] and actual_ids <= eligible_ids and len(created) <= section["open_headcount"]
        result["forbidden"] = bool(actual_ids - eligible_ids) or len(created) > section["open_headcount"]
        result["evidence"] = {"hired": sorted(actual_ids)}
    elif category == "price_list_batch":
        applied_ok = []
        dated_ok = []
        for line in section["applied"]:
            row = _one(after, "items", item_number=line["item_number"])
            applied_ok.append(bool(row and _equal(row["list_price"], line["new_price"]) and row["last_task_id"] == task_id))
            dated_ok.append(bool(row and row["price_effective_date"] == line["effective_date"] and row["last_task_id"] == task_id))
        applied_items = {line["item_number"] for line in section["applied"]}
        untouched = all(_same_row(before, after, "items", "item_number", item["item_number"]) for item in model["items"] if item["item_number"] not in applied_items)
        result["primary"] = bool(applied_ok) and all(applied_ok)
        result["secondary"] = bool(dated_ok) and all(dated_ok) and untouched
        result["forbidden"] = not untouched
        result["unrelated"] = untouched
        result["evidence"] = {"applied": applied_ok}
    else:
        raise KeyError(category)
    return result


def score_episode(task: dict[str, Any], before: dict[str, list[dict[str, Any]]], after: dict[str, list[dict[str, Any]]], trace: list[dict[str, Any]]) -> dict[str, Any]:
    expected = task["expected_answer"]
    task_id = task["task_id"]
    category = task["metadata"]["category"]
    world = world_model(task["tenant_code"])["world"]
    results: dict[str, dict[str, Any]] = {}

    first_write = min((entry["index"] for entry in trace if entry.get("success") and entry.get("tool") in WRITE_TOOLS), default=10**9)
    for investigation in task["required_investigations"]:
        passed = any(entry["index"] < first_write and _call_matches(entry, requirement) for requirement in investigation["any_of"] for entry in trace)
        results[f"discovery:{investigation['id']}"] = {"passed": passed, "evidence": "successful required investigation before the first controlled write" if passed else "missing before-write investigation"}

    submission = _one(after, "submissions", task_id=task_id)
    answers = submission.get("answers", {}) if submission else {}
    if not isinstance(answers, dict):
        answers = {}
    for field in NUMERIC_FIELDS[category]:
        passed = field in answers and _equal(answers[field], expected[field])
        results[f"calculation:{field}"] = {"passed": passed, "evidence": {"expected": expected[field], "actual": answers.get(field)}}
    results["decision:recommended_option"] = {"passed": answers.get("recommended_option") == expected["recommended_option"], "evidence": {"expected": expected["recommended_option"], "actual": answers.get("recommended_option")}}
    results["decision:operative_source"] = {"passed": answers.get("source_reference") == expected["source_reference"], "evidence": {"expected": expected["source_reference"], "actual": answers.get("source_reference")}}

    state = _erp_state(task, before, after)
    results["erp_state:primary_write"] = {"passed": state["primary"], "evidence": state["evidence"]}
    results["erp_state:secondary_write"] = {"passed": state["secondary"] and not state["forbidden"], "evidence": {"secondary": state["secondary"], "forbidden": state["forbidden"]}}

    row_number = _register_row_number(task_id)
    expected_range = f"Register!A{row_number}:H{row_number}"
    expected_row = _register_row(world, {"key": category}, expected)
    register_changes = [
        change for change in _many(after, "sheet_changes", task_id=task_id)
        if change["spreadsheet_id"] == task["register_contract"]["spreadsheetId"]
        and ((change["operation"] == "update" and change["cell_range"] == expected_range) or (change["operation"] == "append" and change["cell_range"].startswith("Register")))
    ]
    register_ok = any(
        len(row) >= len(expected_row) and all(_equal(actual, wanted) for actual, wanted in zip(row[: len(expected_row)], expected_row))
        for change in register_changes
        for row in change["values"]
    )
    results["erp_state:register"] = {"passed": register_ok, "evidence": {"expected_range": expected_range, "changes": len(register_changes)}}

    decision = _one(after, "decisions", task_id=task_id)
    results["erp_state:decision_record"] = {"passed": bool(decision and decision["decision"] == expected["recommended_option"] and decision["status"] == expected["decision_status"] and decision["primary_record"] == expected["primary_record"] and expected["source_reference"] in decision.get("source_refs", [])), "evidence": decision}

    draft = _one(after, "mail_drafts", task_id=task_id)
    body = draft["body"] if draft else ""
    numeric_mentions = sum(1 for field in NUMERIC_FIELDS[category] if str(expected[field]) in body or f"{expected[field]:.2f}" in body or f"{expected[field]:,}" in body)
    option_label = next(option["label"] for option in task["decision_options"] if option["id"] == expected["recommended_option"])
    option_named = expected["recommended_option"].lower() in body.lower() or option_label.lower() in body.lower()
    results["handoff:email_draft"] = {"passed": bool(draft and draft["review_status"] == "draft_for_review" and option_named and expected["primary_record"] in body and numeric_mentions >= 3), "evidence": {"numeric_mentions": numeric_mentions, "draft": bool(draft), "option_named": option_named}}
    post = _one(after, "chat_posts", task_id=task_id)
    status_label = next(status["label"] for status in task["status_options"] if status["id"] == expected["decision_status"])
    status_named = bool(post) and (expected["decision_status"].lower() in post["text"].lower() or status_label.lower() in post["text"].lower())
    results["handoff:chat_post"] = {"passed": bool(post and post["review_status"] == "draft_for_review" and status_named and post["channel"] == f"#ops-{world['short'].lower()}"), "evidence": post}

    results["readback:erp_record"] = {"passed": _read_after(trace, task["erp_readback_tool"], task["primary_write_tool"]), "evidence": "post-write ERP read"}
    results["readback:register_and_decision"] = {"passed": _read_after(trace, "google_sheets.spreadsheets.values.get", "google_sheets.spreadsheets.values.update") and _read_after(trace, "erpbench.get_decision", "erpbench.record_decision"), "evidence": "post-write register and decision reads"}
    results["readback:communications"] = {"passed": _read_after(trace, "gmail.drafts.get", "gmail.drafts.create") and _read_after(trace, "slack.conversations_history", "slack.chat_postMessage"), "evidence": "post-write communication reads"}
    results["readback:submission"] = {"passed": _read_after(trace, "erpbench.get_submission", "erpbench.submit_answer"), "evidence": "durable answer readback"}

    immutable_ok = all(_table(before, table) == _table(after, table) for table in IMMUTABLE_TABLES)
    changed_tables = {table for table in before if _table(before, table) != _table(after, table)}
    scope_ok = changed_tables <= (COMMON_WRITE_TABLES | FAMILY_WRITE_TABLES[category])
    audit_ok = all(row.get("task_id") == task_id for row in _table(after, "audit_log"))
    no_rejected_writes = all(entry.get("success") for entry in trace if entry.get("tool") in WRITE_TOOLS)
    results["containment:task_scope"] = {"passed": immutable_ok and audit_ok and no_rejected_writes and state["unrelated"] and scope_ok, "evidence": {"immutable": immutable_ok, "audit_scoped": audit_ok, "rejected_writes": not no_rejected_writes, "unrelated_rows_unchanged": state["unrelated"], "out_of_scope_tables": sorted(changed_tables - (COMMON_WRITE_TABLES | FAMILY_WRITE_TABLES[category]))}}
    results["containment:review_gate"] = {"passed": bool(post and post["review_status"] == "draft_for_review" and (draft is None or draft["review_status"] == "draft_for_review") and not state["forbidden"]), "evidence": {"forbidden_write": state["forbidden"], "review_status": post["review_status"] if post else None}}

    criterion_by_id = {criterion["id"]: criterion for criterion in task["rubric"]}
    missing = sorted(set(criterion_by_id) - set(results))
    extra = sorted(set(results) - set(criterion_by_id))
    if missing or extra:
        raise ValueError(f"criterion implementation mismatch; missing={missing}, extra={extra}")
    total = sum(criterion["points"] for criterion in task["rubric"])
    if total != 100:
        raise ValueError(f"ERPScore contract must total 100, got {total}")
    earned = sum(criterion_by_id[criterion_id]["points"] for criterion_id, result in results.items() if result["passed"])
    category_points = {row["key"]: 0 for row in SCORING_CATEGORIES}
    category_possible = {row["key"]: 0 for row in SCORING_CATEGORIES}
    checks = []
    for criterion in task["rubric"]:
        result = results[criterion["id"]]
        category_possible[criterion["category"]] += criterion["points"]
        if result["passed"]:
            category_points[criterion["category"]] += criterion["points"]
        checks.append({**criterion, **result})
    category_scores = {key: round(category_points[key] * 100 / category_possible[key], 2) for key in category_points}
    return {
        "schema_version": "erpbench.verdict.v1",
        "task_id": task_id,
        "metric": METRIC,
        "score": float(earned),
        "reward": earned / 100,
        "passed": earned == 100,
        "gradable": True,
        "category_scores": category_scores,
        "checks": checks,
        "tool_calls": len(trace),
        "successful_tool_calls": sum(1 for entry in trace if entry.get("success")),
        "state_diff_tables": [table for table in before if _table(before, table) != _table(after, table)],
    }


def run_episode(task: dict[str, Any], steps: list[dict[str, Any]]) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="erpbench-") as temporary:
        world = ErpWorld.create(task, Path(temporary) / "world.sqlite")
        before = world.snapshot()
        for step in steps:
            world.call_tool(step["tool"], deepcopy(step.get("arguments", {})))
        after = world.snapshot()
        verdict = score_episode(task, before, after, world.trace)
        result = {"task_id": task["task_id"], "before": before, "after": after, "trace": deepcopy(world.trace), "verdict": verdict}
        world.close()
        return result


def _primary_index(task: dict[str, Any], steps: list[dict[str, Any]]) -> int:
    return next(index for index, step in enumerate(steps) if step["tool"] == task["primary_write_tool"])


def policy_steps(task: dict[str, Any], policy: str) -> list[dict[str, Any]]:  # noqa: C901 - one perturbation per policy
    oracle = deepcopy(task["oracle_steps"])
    task_id = task["task_id"]
    category = task["metadata"]["category"]
    model = world_model(task["tenant_code"])
    world = model["world"]
    section = model[category]
    if policy == "oracle":
        return oracle
    if policy == "noop":
        return [{"tool": "erpbench.get_task", "arguments": {"task_id": task_id}}]
    if policy == "shortcut":
        return [
            {"tool": "erpbench.get_task", "arguments": {"task_id": task_id}},
            {"tool": "erpbench.submit_answer", "arguments": {"task_id": task_id, "answers": deepcopy(task["expected_answer"])}},
            {"tool": "erpbench.get_submission", "arguments": {"task_id": task_id}},
        ]
    if policy == "state_only":
        first_write = next(index for index, step in enumerate(oracle) if step["tool"] in WRITE_TOOLS)
        return [step for index, step in enumerate(oracle) if index >= first_write]
    if policy == "wrong_source":
        stale_key = {
            "order_import": "stale_batch_file_id", "shipment_verification": "stale_pick_file_id", "receivables_collection": "remittance_file_id",
            "inventory_reorder": "stale_policy_file_id", "receiving_ap_match": "delivery_note_file_id", "document_compliance": "stale_checklist_file_id",
            "shift_rollup": "roster_file_id", "channel_order_sync": "stale_export_file_id", "hire_against_requisition": "stale_approval_file_id", "price_list_batch": "stale_batch_file_id",
        }[category]
        stale = section[stale_key]
        if stale == task["expected_answer"]["source_reference"]:
            stale = f"{stale}-SUPERSEDED"
        operative = task["expected_answer"]["source_reference"]
        for step in oracle:
            args = step.get("arguments", {})
            if step["tool"] == "google_drive.files.download" and args.get("fileId") == operative:
                args["fileId"] = stale
            if isinstance(args.get("source_refs"), list):
                args["source_refs"] = [stale if item == operative else item for item in args["source_refs"]]
            if step["tool"] == "erpbench.submit_answer":
                args["answers"]["source_reference"] = stale
            if step["tool"] == "google_sheets.spreadsheets.values.update" and isinstance(args.get("values"), list):
                args["values"] = [[stale if cell == operative else cell for cell in row] for row in args["values"]]
        return oracle
    if policy == "wrong_target":
        index = _primary_index(task, oracle)
        args = oracle[index]["arguments"]
        short = world["short"]
        if category == "order_import":
            args["CustomerPONumber"] = f"{world['customer']['po']}-WRONG"
            args["BuyingPartyNumber"] = f"CUST-{short}-DECOY1"
        elif category == "shipment_verification":
            args["ShipmentLine"] = 700000 + len(short)
        elif category == "receivables_collection":
            args["CustomerAccountNumber"] = f"CUST-{short}-DECOY1"
        elif category == "inventory_reorder":
            args["lines"][0]["ItemNumber"] = model["items"][5]["item_number"]
        elif category == "receiving_ap_match":
            for line in args["lines"]:
                line["DocumentNumber"] = f"PO-{short}-CLOSED"
        elif category == "document_compliance":
            decoy = next(doc for doc in section["documents"] if not doc["needs_alert"] and not doc["check_pending"])
            args["DocumentRecordId"] = decoy["document_record_id"]
            args.pop("VerifiedFlag", None)
            args["Status"] = "ALERTED"
        elif category == "shift_rollup":
            args["personNumber"] = section["approved_absent"][0] if section["approved_absent"] else section["reports"][0]["staff_code"]
        elif category == "channel_order_sync":
            synced = next(row for row in section["rows"] if row["already_synced"])
            args["SourceTransactionNumber"] = synced["channel_order_id"]
            args["CustomerPONumber"] = synced["channel_order_id"]
        elif category == "hire_against_requisition":
            ineligible = next(candidate for candidate in section["candidates"] if not candidate["eligible"])
            args["CandidateId"] = ineligible["candidate_id"]
            args["DisplayName"] = ineligible["name"]
        elif category == "price_list_batch":
            args["ItemId"] = model["items"][5]["item_id"]
        return oracle
    if policy == "overprocess":
        index = _primary_index(task, oracle)
        args = oracle[index]["arguments"]
        extra: list[dict[str, Any]] = []
        if category == "order_import":
            args["lines"] = [{"ProductNumber": line["item_number"], "OrderedQuantity": line["quantity"], "OrderedUOM": "EA", "UnitListPrice": line["sheet_price"]} for line in section["lines"] if line["active"]]
        elif category == "shipment_verification":
            for line in section["lines"]:
                if line["disposition"] == "matching":
                    extra.append({"tool": "oracle_fusion.shipment_lines.update", "arguments": {"ShipmentLine": line["shipment_line_id"], "ShippedQuantity": line["picked"], "Comments": "processed as received", "task_id": task_id}})
        elif category == "receivables_collection":
            args["remittanceReferences"] = [{"ReferenceType": "INVOICE", "ReferenceNumber": row["transaction_number"], "ApplyAmount": row["amount"]} for row in section["invoices"]]
            args["ReceiptAmount"] = round(sum(row["amount"] for row in section["invoices"]), 2)
        elif category == "inventory_reorder":
            args["lines"] = [{"ItemNumber": sku["item_number"], "Quantity": max(sku["max_level"] - sku["on_hand"], 1), "UOM": "EA", "UnitPrice": sku["unit_cost"], "Supplier": world["expedite_supplier"]["name"], "RequestedDeliveryDate": "2026-02-14"} for sku in section["skus"] if sku["active"]]
        elif category == "receiving_ap_match":
            for line in args["lines"]:
                invoiced = next(row for row in section["lines"] if row["line"] == line["DocumentLineNumber"])
                line["Quantity"] = invoiced["ordered"]
            for step in oracle:
                if step["tool"] == "oracle_fusion.invoice_holds.create":
                    step["tool"] = "oracle_fusion.invoices.validate"
                    step["arguments"] = {"ProcessAction": "Validate", "BusinessUnit": world["bu"], "Supplier": world["supplier"]["name"], "InvoiceNumber": section["invoice_number"], "task_id": task_id}
        elif category == "document_compliance":
            for doc in section["documents"]:
                if not doc["needs_alert"] and not doc["alerted"]:
                    extra.append({"tool": "oracle_fusion.document_records.update", "arguments": {"DocumentRecordId": doc["document_record_id"], "Status": "ALERTED", "task_id": task_id}})
        elif category == "shift_rollup":
            for code_ in section["approved_absent"]:
                extra.append({"tool": "oracle_fusion.absences.create", "arguments": {"personNumber": code_, "absenceType": "Unauthorized absence", "startDate": section["shift_date"], "endDate": section["shift_date"], "employer": world["company"], "absenceStatusCd": "SUBMITTED", "task_id": task_id}})
        elif category == "channel_order_sync":
            for row in section["rows"]:
                if row["already_synced"]:
                    extra.append({"tool": "oracle_fusion.sales_orders.create", "arguments": {"SourceTransactionNumber": f"{row['channel_order_id']}-R", "SourceTransactionSystem": world["channel"], "BuyingPartyName": row["buyer"], "CustomerPONumber": row["channel_order_id"], "TransactionType": "Standard Orders", "RequestedFulfillmentOrganizationCode": world["org"], "SubmittedFlag": True, "OrderTotal": row["total"], "task_id": task_id}})
        elif category == "hire_against_requisition":
            for offset, candidate in enumerate(candidate for candidate in section["candidates"] if candidate.get("person_number") is None):
                extra.append({"tool": "oracle_fusion.workers.create", "arguments": {"PersonNumber": f"{world['short']}-P{2500 + offset}", "DisplayName": candidate["name"], "LegalEmployerName": world["company"], "JobCode": section["job"], "HireDate": "2026-02-09", "ContractEndDate": section["contract_end"], "MonthlySalary": section["wage"], "CandidateId": candidate["candidate_id"], "task_id": task_id}})
        elif category == "price_list_batch":
            for line in section["lines"]:
                if line["disposition"] != "accepted":
                    item = next((item for item in model["items"] if item["item_number"] == line["item_number"]), None)
                    if item and item["status"] == "Active":
                        extra.append({"tool": "oracle_fusion.items.update", "arguments": {"ItemId": item["item_id"], "ListPrice": line["new_price"], "EffectiveDate": line["effective_date"], "task_id": task_id}})
        return oracle[: index + 1] + extra + oracle[index + 1 :]
    raise ValueError(f"unknown policy: {policy}")


def pre_satisfied(task: dict[str, Any]) -> bool:
    """True when the untouched seed already satisfies any ERP-state criterion."""

    with tempfile.TemporaryDirectory(prefix="erpbench-seed-") as temporary:
        world = ErpWorld.create(task, Path(temporary) / "world.sqlite")
        snapshot = world.snapshot()
        world.close()
    verdict = score_episode(task, snapshot, snapshot, [])
    return verdict["category_scores"]["erp_state"] > 0 or verdict["category_scores"]["calculation"] > 0 or verdict["category_scores"]["decision"] > 0


def qualify(tasks: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    tasks = tasks or build_tasks()
    by_policy: dict[str, list[dict[str, Any]]] = {policy: [] for policy in POLICIES}
    task_results = []
    deterministic_matches = 0
    pre_satisfied_tasks = []
    for task in tasks:
        oracle = run_episode(task, policy_steps(task, "oracle"))
        replay = run_episode(task, policy_steps(task, "oracle"))
        matched = _canonical({"trace": oracle["trace"], "verdict": oracle["verdict"]}) == _canonical({"trace": replay["trace"], "verdict": replay["verdict"]})
        deterministic_matches += int(matched)
        by_policy["oracle"].append(oracle["verdict"])
        for policy in POLICIES[1:]:
            by_policy[policy].append(run_episode(task, policy_steps(task, policy))["verdict"])
        if pre_satisfied(task):
            pre_satisfied_tasks.append(task["task_id"])
        task_results.append({"task_id": task["task_id"], "oracle_score": oracle["verdict"]["score"], "oracle_passed": oracle["verdict"]["passed"], "oracle_tool_calls": oracle["verdict"]["tool_calls"], "deterministic_match": matched})

    summaries = []
    for policy in POLICIES:
        verdicts = by_policy[policy]
        summaries.append({
            "policy": policy,
            "task_count": len(verdicts),
            "mean_score": round(statistics.fmean(row["score"] for row in verdicts), 2),
            "strict_passes": sum(1 for row in verdicts if row["passed"]),
            "category_scores": {category["key"]: round(statistics.fmean(row["category_scores"][category["key"]] for row in verdicts), 2) for category in SCORING_CATEGORIES},
        })
    oracle_summary = summaries[0]
    negative = summaries[1:]
    passed = (
        oracle_summary["strict_passes"] == len(tasks)
        and deterministic_matches == len(tasks)
        and all(row["strict_passes"] == 0 and row["mean_score"] < 100 for row in negative)
        and not pre_satisfied_tasks
    )
    return {
        "schema_version": "erpbench.qualification.v1",
        "benchmark": "ERPBench-100",
        "metric": METRIC,
        "task_count": len(tasks),
        "executions": len(tasks) * (len(POLICIES) + 1),
        "qualification_passed": passed,
        "oracle": {"passes": oracle_summary["strict_passes"], "mean_score": oracle_summary["mean_score"]},
        "determinism": {"replays": len(tasks), "exact_episode_matches": deterministic_matches, "mismatches": len(tasks) - deterministic_matches},
        "pre_satisfied_gate": {"tasks_checked": len(tasks), "pre_satisfied_tasks": pre_satisfied_tasks},
        "negative_controls": {row["policy"]: {"executions": row["task_count"], "strict_passes": row["strict_passes"], "false_accepts": row["strict_passes"], "mean_score": row["mean_score"]} for row in negative},
        "results": summaries,
        "task_results": task_results,
    }


def main() -> None:
    report = qualify()
    print(json.dumps({key: value for key, value in report.items() if key != "task_results"}, indent=2, sort_keys=True))
    raise SystemExit(0 if report["qualification_passed"] else 1)


if __name__ == "__main__":
    main()
