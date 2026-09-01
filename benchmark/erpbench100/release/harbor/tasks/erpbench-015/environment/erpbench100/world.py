"""SQLite-backed, provider-shaped ERP sandbox for ERPBench-100.

The tool surface is shaped like Oracle Fusion Cloud REST resources (Order
Management, Shipping, Receivables, Inventory, Procurement, Payables and HCM)
plus documented Gmail, Google Drive, Google Sheets and Slack operations. Every
tool runs against one task-local SQLite database; writes are durable and
task-scoped, reads never reveal the sealed gold answer.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import sqlite3
from copy import deepcopy
from pathlib import Path
from typing import Any

from .spec import AS_OF, AS_OF_DATE, asset_payloads, world_model

SCHEMA_PATH = Path(__file__).with_name("schema.sql")

ORACLE_SCM = "https://docs.oracle.com/en/cloud/saas/supply-chain-and-manufacturing/26a/fasrp/"
ORACLE_FINANCIALS = "https://docs.oracle.com/en/cloud/saas/financials/26a/farfa/"
ORACLE_PROCUREMENT = "https://docs.oracle.com/en/cloud/saas/procurement/26a/fapra/"
ORACLE_HCM = "https://docs.oracle.com/en/cloud/saas/human-resources/26a/farws/"
GMAIL = "https://developers.google.com/workspace/gmail/api/reference/rest/v1/"
DRIVE = "https://developers.google.com/workspace/drive/api/reference/rest/v3/"
SHEETS = "https://developers.google.com/workspace/sheets/api/reference/rest/v4/"
SLACK = "https://api.slack.com/methods/"
FSCM = "/fscmRestApi/resources/11.13.18.05/"
HCM = "/hcmRestApi/resources/11.13.18.05/"

SERVER_BY_PREFIX = {
    "erpbench": "erpbench",
    "oracle_fusion": "oracle_fusion",
    "gmail": "gmail",
    "google_drive": "google_drive",
    "google_sheets": "google_sheets",
    "slack": "slack",
}

SERVERS = ("erpbench", "oracle_fusion", "gmail", "google_drive", "google_sheets", "slack")


def _schema(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {"type": "object", "additionalProperties": False, "properties": properties, "required": required}


def _string(description: str) -> dict[str, str]:
    return {"type": "string", "description": description}


def _integer(description: str) -> dict[str, Any]:
    return {"type": "integer", "description": description}


def _number(description: str) -> dict[str, Any]:
    return {"type": "number", "description": description}


def _boolean(description: str) -> dict[str, Any]:
    return {"type": "boolean", "description": description}


def _object(description: str = "Structured values") -> dict[str, Any]:
    return {"type": "object", "description": description, "additionalProperties": True}


def _array(description: str = "Values") -> dict[str, Any]:
    return {"type": "array", "description": description, "items": {}}


def _string_array(description: str) -> dict[str, Any]:
    return {"type": "array", "description": description, "items": {"type": "string"}}


TASK_ID = {"task_id": _string("Active task identifier; every write must carry it")}
Q = {"q": _string("Provider query expression, e.g. Field='value' and Other='value'")}


def _oracle_page(method: str, path: str, override: str | None = None) -> str:
    if override:
        return override
    resource = path.removeprefix(FSCM).removeprefix(HCM)
    segments = [segment.strip("{}").lower() for segment in resource.split("/")]
    return f"op-{'-'.join(segments)}-{method.lower()}.html"


def _upstream(base: str, method: str, path: str, *, page: str | None = None, mode: str = "documented-operation") -> dict[str, Any]:
    return {"method": method, "path": path, "source": f"{base}{_oracle_page(method, path, page) if base.startswith('https://docs.oracle.com') else page}", "contractMode": mode}


def _tool(name: str, description: str, properties: dict[str, Any], required: list[str], *, read_only: bool, upstream: dict[str, Any]) -> dict[str, Any]:
    server = SERVER_BY_PREFIX[name.split(".", 1)[0]]
    mode = upstream.pop("contractMode")
    return {
        "name": name,
        "title": name.replace(".", " · ").replace("_", " "),
        "description": description,
        "inputSchema": _schema(properties, required),
        "annotations": {"readOnlyHint": read_only, "destructiveHint": False, "idempotentHint": read_only, "openWorldHint": False},
        "_meta": {
            "erpbench": {
                "server": server,
                "contractMode": mode,
                "implementation": "sqlite-stateful synthetic closed sandbox",
                "upstream": upstream,
            }
        },
    }


def tool_definitions(answer_schema: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    fscm = lambda method, resource, page=None: _upstream(ORACLE_SCM, method, f"{FSCM}{resource}", page=page)  # noqa: E731
    fin = lambda method, resource, page=None: _upstream(ORACLE_FINANCIALS, method, f"{FSCM}{resource}", page=page)  # noqa: E731
    proc = lambda method, resource, page=None: _upstream(ORACLE_PROCUREMENT, method, f"{FSCM}{resource}", page=page)  # noqa: E731
    hcm = lambda method, resource: _upstream(ORACLE_HCM, method, f"{HCM}{resource}", page="index.html", mode="provider-shaped")  # noqa: E731
    google = lambda base, method, path, page: {"method": method, "path": path, "source": f"{base}{page}", "contractMode": "documented-operation"}  # noqa: E731
    slack = lambda method_name: {"method": "POST", "path": f"/api/{method_name}", "source": f"{SLACK}{method_name}", "contractMode": "documented-operation"}  # noqa: E731
    control = lambda: {"method": "MCP", "path": "erpbench", "source": "https://blobfish.ai/benchmarks/erpbench-100", "contractMode": "benchmark-control"}  # noqa: E731

    return [
        _tool("erpbench.get_task", "Read the task-scoped outcome contract without revealing the gold answer.", {"task_id": _string("Task identifier")}, ["task_id"], read_only=True, upstream=control()),
        _tool("erpbench.get_decision", "Read back the durable decision record for a task.", {"task_id": _string("Task identifier")}, ["task_id"], read_only=True, upstream=control()),
        _tool("erpbench.get_submission", "Read back the durable submitted answer.", {"task_id": _string("Task identifier")}, ["task_id"], read_only=True, upstream=control()),
        _tool("erpbench.record_decision", "Record the selected option, status, primary ERP record, rationale and source references.", {**TASK_ID, "decision": _string("Selected option"), "status": _string("Decision status"), "primary_record": _string("Primary ERP record number"), "rationale": _string("Rationale"), "source_refs": _string_array("Source references")}, ["task_id", "decision", "status", "primary_record", "rationale", "source_refs"], read_only=False, upstream=control()),
        _tool("erpbench.submit_answer", "Persist the structured final answer for deterministic grading.", {**TASK_ID, "answers": answer_schema or _object("Task-specific answer")}, ["task_id", "answers"], read_only=False, upstream=control()),
        # Oracle Fusion — order management, shipping, product master, receivables
        _tool("oracle_fusion.items.list", "Get items for an inventory organization.", Q, [], read_only=True, upstream=fscm("GET", "itemsV2")),
        _tool("oracle_fusion.items.update", "Update the list price of one item as of an effective date.", {**TASK_ID, "ItemId": _integer("Item identifier"), "ListPrice": _number("New list price"), "EffectiveDate": _string("ISO effective date")}, ["task_id", "ItemId", "ListPrice", "EffectiveDate"], read_only=False, upstream=fscm("PATCH", "itemsV2/{itemsV2UniqID}")),
        _tool("oracle_fusion.customer_account_activities.get", "Get one customer account with open receivables and credit status.", {"AccountId": _string("Customer account number")}, ["AccountId"], read_only=True, upstream=fin("GET", "receivablesCustomerAccountActivities/{AccountId}")),
        _tool("oracle_fusion.sales_orders.list", "Get sales orders from Order Management.", Q, [], read_only=True, upstream=fscm("GET", "salesOrdersForOrderHub", "api-order-management-sales-orders-for-order-hub.html")),
        _tool("oracle_fusion.sales_orders.get", "Get one sales order with its lines.", {"OrderKey": _string("Order number")}, ["OrderKey"], read_only=True, upstream=fscm("GET", "salesOrdersForOrderHub/{OrderKey}")),
        _tool("oracle_fusion.sales_orders.create", "Create one sales order; SubmittedFlag false leaves it as a draft awaiting release.", {**TASK_ID, "SourceTransactionNumber": _string("Source document reference"), "SourceTransactionSystem": _string("Source system"), "BuyingPartyNumber": _string("Customer account number"), "BuyingPartyName": _string("Customer name when no account exists"), "CustomerPONumber": _string("Customer purchase order"), "TransactionType": _string("Order type"), "RequestedFulfillmentOrganizationCode": _string("Fulfillment organization"), "SubmittedFlag": _boolean("Submit the order"), "OrderTotal": _number("Header total when lines are not itemized"), "lines": _array("Order lines: ProductNumber, OrderedQuantity, OrderedUOM, UnitListPrice")}, ["task_id", "SourceTransactionNumber", "SourceTransactionSystem", "CustomerPONumber", "TransactionType", "RequestedFulfillmentOrganizationCode", "SubmittedFlag"], read_only=False, upstream=fscm("POST", "salesOrdersForOrderHub")),
        _tool("oracle_fusion.shipments.list", "Get shipments.", Q, [], read_only=True, upstream=fscm("GET", "shipments")),
        _tool("oracle_fusion.shipment_lines.list", "Get shipment lines with requested and shipped quantities.", Q, [], read_only=True, upstream=fscm("GET", "shipmentLines")),
        _tool("oracle_fusion.shipment_lines.update", "Update the shipped quantity of one unconfirmed shipment line.", {**TASK_ID, "ShipmentLine": _integer("Shipment line identifier"), "ShippedQuantity": _integer("Corrected shipped quantity"), "Comments": _string("Reason")}, ["task_id", "ShipmentLine", "ShippedQuantity"], read_only=False, upstream=fscm("PATCH", "shipmentLines/{ShipmentLine}")),
        _tool("oracle_fusion.receivables_invoices.list", "Get receivables invoices.", Q, [], read_only=True, upstream=fin("GET", "receivablesInvoices")),
        _tool("oracle_fusion.receivables_invoices.get", "Get one receivables invoice.", {"CustomerTransactionId": _integer("Transaction identifier")}, ["CustomerTransactionId"], read_only=True, upstream=fin("GET", "receivablesInvoices/{CustomerTransactionId}")),
        _tool("oracle_fusion.standard_receipts.list", "Get standard receipts for a customer account.", Q, [], read_only=True, upstream=fin("GET", "standardReceipts")),
        _tool("oracle_fusion.standard_receipts.create", "Create a standard receipt and apply it through remittance references.", {**TASK_ID, "ReceiptNumber": _string("Receipt number"), "ReceiptAmount": _number("Receipt amount"), "ReceiptDate": _string("ISO receipt date"), "CustomerAccountNumber": _string("Customer account number"), "ReceiptMethod": _string("Receipt method"), "BusinessUnit": _string("Business unit"), "Currency": _string("Currency"), "remittanceReferences": _array("Rows of ReferenceType, ReferenceNumber, ApplyAmount")}, ["task_id", "ReceiptNumber", "ReceiptAmount", "ReceiptDate", "CustomerAccountNumber", "ReceiptMethod", "BusinessUnit", "Currency", "remittanceReferences"], read_only=False, upstream=fin("POST", "standardReceipts")),
        # Oracle Fusion — inventory and procurement
        _tool("oracle_fusion.onhand_balances.list", "Get on-hand and reserved quantities.", Q, [], read_only=True, upstream=fscm("GET", "inventoryOnhandBalances", "api-inventory-management-inventory-on-hand-balances.html")),
        _tool("oracle_fusion.purchase_orders.list", "Get purchase orders.", Q, [], read_only=True, upstream=proc("GET", "purchaseOrders", "api-purchase-orders.html")),
        _tool("oracle_fusion.purchase_orders.get", "Get one purchase order.", {"purchaseOrdersUniqID": _string("Purchase order number")}, ["purchaseOrdersUniqID"], read_only=True, upstream=proc("GET", "purchaseOrders/{purchaseOrdersUniqID}", "api-purchase-orders.html")),
        _tool("oracle_fusion.purchase_order_lines.list", "Get the lines of one purchase order.", {"purchaseOrdersUniqID": _string("Purchase order number")}, ["purchaseOrdersUniqID"], read_only=True, upstream=proc("GET", "purchaseOrders/{purchaseOrdersUniqID}/child/lines", "api-purchase-orders-lines.html")),
        _tool("oracle_fusion.suppliers.list", "Get suppliers with lead times.", Q, [], read_only=True, upstream=proc("GET", "suppliers", "api-suppliers.html")),
        _tool("oracle_fusion.purchase_requisitions.create", "Create a purchase requisition with lines.", {**TASK_ID, "RequisitioningBU": _string("Requisitioning business unit"), "Preparer": _string("Preparer"), "Description": _string("Description"), "Justification": _string("Justification"), "lines": _array("Lines: ItemNumber, Quantity, UOM, UnitPrice, Supplier, RequestedDeliveryDate")}, ["task_id", "RequisitioningBU", "Preparer", "Description", "Justification", "lines"], read_only=False, upstream=proc("POST", "purchaseRequisitions")),
        _tool("oracle_fusion.purchase_requisitions.submit", "Submit a requisition for approval.", {**TASK_ID, "purchaseRequisitionsUniqID": _string("Requisition number")}, ["task_id", "purchaseRequisitionsUniqID"], read_only=False, upstream=proc("POST", "purchaseRequisitions/{purchaseRequisitionsUniqID}/action/submitRequisition")),
        _tool("oracle_fusion.purchase_requisitions.get", "Get one purchase requisition.", {"purchaseRequisitionsUniqID": _string("Requisition number")}, ["purchaseRequisitionsUniqID"], read_only=True, upstream=proc("GET", "purchaseRequisitions/{purchaseRequisitionsUniqID}")),
        _tool("oracle_fusion.receiving_receipt_requests.list", "Get receiving receipt requests.", Q, [], read_only=True, upstream=fscm("GET", "receivingReceiptRequests", "api-inventory-management-receiving-receipt-requests.html")),
        _tool("oracle_fusion.receiving_receipt_requests.create", "Create a receiving receipt request for delivered purchase-order lines.", {**TASK_ID, "ReceiptSourceCode": _string("Receipt source"), "OrganizationCode": _string("Organization"), "VendorName": _string("Supplier"), "lines": _array("Lines: DocumentNumber, DocumentLineNumber, ItemNumber, Quantity, TransactionType")}, ["task_id", "ReceiptSourceCode", "OrganizationCode", "lines"], read_only=False, upstream=fscm("POST", "receivingReceiptRequests", "op-receivingreceipttransactionrequests-post.html")),
        # Oracle Fusion — payables
        _tool("oracle_fusion.invoices.list", "Get Payables invoices.", Q, [], read_only=True, upstream=fin("GET", "invoices", "api-invoices.html")),
        _tool("oracle_fusion.invoices.get", "Get one Payables invoice with holds.", {"invoicesUniqID": _string("Invoice number")}, ["invoicesUniqID"], read_only=True, upstream=fin("GET", "invoices/{invoicesUniqID}")),
        _tool("oracle_fusion.invoices.create", "Create one Payables invoice matched to purchase-order lines.", {**TASK_ID, "BusinessUnit": _string("Business unit"), "Supplier": _string("Supplier"), "InvoiceNumber": _string("Invoice number"), "InvoiceAmount": _number("Invoice amount"), "InvoiceCurrency": _string("Currency"), "InvoiceDate": _string("ISO invoice date"), "invoiceLines": _array("Lines: LineNumber, PurchaseOrderNumber, PurchaseOrderLineNumber, ItemNumber, Quantity, UnitPrice")}, ["task_id", "BusinessUnit", "Supplier", "InvoiceNumber", "InvoiceAmount", "InvoiceCurrency", "InvoiceDate", "invoiceLines"], read_only=False, upstream=fin("POST", "invoices")),
        _tool("oracle_fusion.invoices.validate", "Validate an invoice for payment.", {**TASK_ID, "ProcessAction": _string("Must be Validate"), "BusinessUnit": _string("Business unit"), "Supplier": _string("Supplier"), "InvoiceNumber": _string("Invoice number")}, ["task_id", "ProcessAction", "BusinessUnit", "Supplier", "InvoiceNumber"], read_only=False, upstream=fin("POST", "invoices/action/validateInvoice")),
        _tool("oracle_fusion.invoice_holds.create", "Place one Payables invoice on hold with a reason.", {**TASK_ID, "InvoiceId": _integer("Invoice identifier"), "HoldName": _string("Hold name"), "HoldReason": _string("Hold reason")}, ["task_id", "InvoiceId", "HoldName", "HoldReason"], read_only=False, upstream=fin("POST", "invoiceHolds", "api-invoice-holds.html")),
        # Oracle Fusion — HCM shaped
        _tool("oracle_fusion.workers.list", "Get workers for a legal employer.", Q, [], read_only=True, upstream=hcm("GET", "workers")),
        _tool("oracle_fusion.workers.create", "Hire one worker under a standard contract.", {**TASK_ID, "PersonNumber": _string("Person number"), "DisplayName": _string("Display name"), "LegalEmployerName": _string("Legal employer"), "JobCode": _string("Job"), "HireDate": _string("ISO hire date"), "ContractEndDate": _string("ISO contract end"), "MonthlySalary": _number("Monthly salary"), "CandidateId": _string("Candidate identifier")}, ["task_id", "PersonNumber", "DisplayName", "LegalEmployerName", "JobCode", "HireDate", "ContractEndDate", "MonthlySalary", "CandidateId"], read_only=False, upstream=hcm("POST", "workers")),
        _tool("oracle_fusion.document_records.list", "Get worker documents of record with expiry and check status.", Q, [], read_only=True, upstream=hcm("GET", "documentRecords")),
        _tool("oracle_fusion.document_records.update", "Update the status or verification flag of one document record.", {**TASK_ID, "DocumentRecordId": _integer("Document record identifier"), "Status": _string("New status, e.g. ALERTED"), "VerifiedFlag": _boolean("Mark the mandatory check verified")}, ["task_id", "DocumentRecordId"], read_only=False, upstream=hcm("PATCH", "documentRecords/{DocumentRecordId}")),
        _tool("oracle_fusion.absences.list", "Get absence records.", Q, [], read_only=True, upstream=hcm("GET", "absences")),
        _tool("oracle_fusion.absences.create", "Record one absence for a worker.", {**TASK_ID, "personNumber": _string("Person number"), "absenceType": _string("Absence type"), "startDate": _string("ISO start"), "endDate": _string("ISO end"), "employer": _string("Legal employer"), "absenceStatusCd": _string("Status code")}, ["task_id", "personNumber", "absenceType", "startDate", "endDate", "employer", "absenceStatusCd"], read_only=False, upstream=hcm("POST", "absences")),
        # Gmail
        _tool("gmail.messages.list", "Search mailbox messages.", {"q": _string("Gmail search query")}, ["q"], read_only=True, upstream=google(GMAIL, "GET", "/gmail/v1/users/{userId}/messages", "users.messages/list")),
        _tool("gmail.messages.get", "Read one mailbox message.", {"id": _string("Message identifier")}, ["id"], read_only=True, upstream=google(GMAIL, "GET", "/gmail/v1/users/{userId}/messages/{id}", "users.messages/get")),
        _tool("gmail.drafts.create", "Save a review-only email draft; drafts are never sent by the sandbox.", {**TASK_ID, "to": _string("Recipient"), "subject": _string("Subject"), "body": _string("Body")}, ["task_id", "to", "subject", "body"], read_only=False, upstream=google(GMAIL, "POST", "/gmail/v1/users/{userId}/drafts", "users.drafts/create")),
        _tool("gmail.drafts.get", "Read back one draft.", {"id": _string("Draft identifier")}, ["id"], read_only=True, upstream=google(GMAIL, "GET", "/gmail/v1/users/{userId}/drafts/{id}", "users.drafts/get")),
        # Google Drive
        _tool("google_drive.files.list", "List files; supports name contains 'text'.", {"q": _string("Drive query")}, ["q"], read_only=True, upstream=google(DRIVE, "GET", "/drive/v3/files", "files/list")),
        _tool("google_drive.files.get", "Read file metadata, version and current-authority flag.", {"fileId": _string("File identifier")}, ["fileId"], read_only=True, upstream=google(DRIVE, "GET", "/drive/v3/files/{fileId}", "files/get")),
        _tool("google_drive.files.download", "Download the content of one file.", {"fileId": _string("File identifier")}, ["fileId"], read_only=True, upstream=google(DRIVE, "GET", "/drive/v3/files/{fileId}?alt=media", "files/get")),
        # Google Sheets
        _tool("google_sheets.spreadsheets.values.get", "Read a range from the ops workbook.", {"spreadsheetId": _string("Spreadsheet identifier"), "range": _string("A1 range")}, ["spreadsheetId", "range"], read_only=True, upstream=google(SHEETS, "GET", "/v4/spreadsheets/{spreadsheetId}/values/{range}", "spreadsheets.values/get")),
        _tool("google_sheets.spreadsheets.values.update", "Write one controlled range; other cells are preserved.", {**TASK_ID, "spreadsheetId": _string("Spreadsheet identifier"), "range": _string("A1 range"), "valueInputOption": _string("RAW or USER_ENTERED"), "values": _array("Two-dimensional values")}, ["task_id", "spreadsheetId", "range", "valueInputOption", "values"], read_only=False, upstream=google(SHEETS, "PUT", "/v4/spreadsheets/{spreadsheetId}/values/{range}", "spreadsheets.values/update")),
        _tool("google_sheets.spreadsheets.values.append", "Append rows to a tab.", {**TASK_ID, "spreadsheetId": _string("Spreadsheet identifier"), "range": _string("Tab range"), "valueInputOption": _string("RAW or USER_ENTERED"), "values": _array("Rows to append")}, ["task_id", "spreadsheetId", "range", "valueInputOption", "values"], read_only=False, upstream=google(SHEETS, "POST", "/v4/spreadsheets/{spreadsheetId}/values/{range}:append", "spreadsheets.values/append")),
        # Slack
        _tool("slack.conversations_history", "Read a channel's messages, including task posts.", {"channel": _string("Channel"), "task_id": _string("Filter to one task's posts")}, ["channel"], read_only=True, upstream=slack("conversations.history")),
        _tool("slack.search_messages", "Search messages across channels.", {"query": _string("Search query")}, ["query"], read_only=True, upstream=slack("search.messages")),
        _tool("slack.chat_postMessage", "Post the review handoff to a channel.", {**TASK_ID, "channel": _string("Channel"), "text": _string("Message"), "review_status": _string("Must remain draft_for_review")}, ["task_id", "channel", "text", "review_status"], read_only=False, upstream=slack("chat.postMessage")),
    ]


READ_TOOLS = {tool["name"] for tool in tool_definitions() if tool["annotations"]["readOnlyHint"]}
WRITE_TOOLS = {tool["name"] for tool in tool_definitions() if not tool["annotations"]["readOnlyHint"]}


def grouped_tool_definitions(answer_schema: dict[str, Any] | None = None) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {server: [] for server in SERVERS}
    for tool in tool_definitions(answer_schema):
        grouped[tool["_meta"]["erpbench"]["server"]].append(tool)
    return grouped


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _render_asset(kind: str, content: Any) -> str:
    if kind == "text":
        return str(content)
    if kind == "json":
        return json.dumps(content, indent=2, sort_keys=True, ensure_ascii=False)
    if kind == "xlsx":
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        for row in content:
            writer.writerow(row)
        return buffer.getvalue()
    if kind == "pdf":
        return str(content)
    raise ValueError(kind)


MIME_BY_SUFFIX = {
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "csv": "text/csv",
    "pdf": "application/pdf",
    "md": "text/markdown",
    "json": "application/json",
    "eml": "message/rfc822",
    "yaml": "application/yaml",
    "log": "text/plain",
}


def drive_file_ids(short: str) -> dict[str, str]:
    """Map asset basename -> Drive file id (current authority files)."""

    return {
        "01-consolidated-order-batch.xlsx": f"FILE-{short}-ORDER-BATCH-0209",
        "02-prior-partial-import.xlsx": f"FILE-{short}-ORDER-BATCH-0203",
        "03-current-price-list.csv": f"FILE-{short}-PRICE-LIST-CURRENT",
        "04-superseded-price-list.csv": f"FILE-{short}-PRICE-LIST-2025H2",
        "05-pick-confirmation.csv": f"FILE-{short}-PICK-CONFIRM-0208",
        "06-remittance-advice.pdf": f"FILE-{short}-REMIT-ADVICE-0206",
        "07-ar-aging.xlsx": f"FILE-{short}-AR-AGING-0209",
        "08-credit-policy.md": f"FILE-{short}-CREDIT-POLICY-R6",
        "09-reorder-policy.xlsx": f"FILE-{short}-REORDER-POLICY-R4",
        "10-demand-forecast.csv": f"FILE-{short}-DEMAND-FORECAST-F06",
        "11-supplier-invoice.pdf": f"FILE-{short}-SUPPLIER-INVOICE-0207",
        "12-delivery-note.pdf": f"FILE-{short}-DELIVERY-NOTE-0206",
        "13-ap-match-policy.md": f"FILE-{short}-AP-MATCH-POLICY",
        "14-compliance-checklist.xlsx": f"FILE-{short}-COMPLIANCE-CHECKLIST-0209",
        "15-document-alert-log.csv": f"FILE-{short}-DOCUMENT-ALERT-LOG",
        "16-shift-roster.xlsx": f"FILE-{short}-SHIFT-ROSTER-0208",
        "17-shift-work-reports.csv": f"FILE-{short}-SHIFT-REPORTS-0208",
        "18-channel-export.json": f"FILE-{short}-CHANNEL-EXPORT-0209",
        "19-customer-capture-chat.json": f"FILE-{short}-CUSTOMER-CAPTURE-0209",
        "20-headcount-approval.pdf": f"FILE-{short}-HEADCOUNT-APPROVAL-2026",
        "21-candidate-register.xlsx": f"FILE-{short}-CANDIDATE-REGISTER",
        "22-wage-table.csv": f"FILE-{short}-WAGE-TABLE",
        "23-price-batch.csv": f"FILE-{short}-PRICE-BATCH-Q2",
        "24-authority-memo.eml": f"FILE-{short}-AUTHORITY-MEMO-0209",
        "25-source-map.yaml": f"FILE-{short}-SOURCE-MAP",
        "26-ops-audit.log": f"FILE-{short}-OPS-AUDIT-LOG",
    }


def _stale_files(world: dict[str, Any], model: dict[str, Any]) -> list[tuple[str, str, str, str]]:
    """Superseded Drive versions: (file_id, name, logical_name, content)."""

    short = world["short"]
    sv = model["shipment_verification"]
    stale_pick = "shipment,line,item,requested,picked,picker,confirmed_at\n" + "".join(
        f"{sv['shipment']},{line['line']},{line['item_number']},{line['requested']},{line['requested']},WH-{10 + line['line']},2026-02-05T20:{10 + line['line']:02d}:00Z\n" for line in sv["lines"]
    )
    stale_policy = "Item,Reorder point,Planned maximum,Count open POs as supply,Policy revision\n" + "".join(
        f"{sku['item_number']},{max(sku['reorder_point'] - 200, 0)},{sku['max_level']},no,R3\n" for sku in model["inventory_reorder"]["skus"]
    )
    stale_checklist = "Person,Person number,Document,Expires,Days remaining\n" + "".join(
        f"{doc['person']},{doc['person_number']},{doc['document_type']},{doc['date_to']},{doc['days_to_expiry'] + 14}\n" for doc in model["document_compliance"]["documents"]
    )
    stale_export = json.dumps({"channel": world["channel"], "exported_at": "2026-02-02T06:00:00Z", "orders": [
        {"channel_order_id": row["channel_order_id"], "buyer": row["buyer"], "order_total": row["total"], "status": "paid"} for row in model["channel_order_sync"]["rows"] if row["already_synced"]
    ]}, indent=2, sort_keys=True)
    hr = model["hire_against_requisition"]
    stale_headcount = f"{world['company']} headcount approval 2025 (superseded)\nPosition: {hr['job']}   Approved headcount: {hr['approved'] + 2}\nApproved monthly wage: {hr['wage'] * 0.94:.2f}\nSuperseded by the 2026 approval.\n"
    pb = model["price_list_batch"]
    stale_batch = "batch,line,item,new_list_price,effective_date\n" + "".join(
        f"PRICE-BATCH-{short}-2026Q1,{index},{item['item_number']},{item['list_price']:.2f},2026-01-01\n" for index, item in enumerate(model["items"], start=1)
    )
    return [
        (sv["stale_pick_file_id"], f"{sv['shipment']}-pick-confirmation-2026-02-05.csv", "pick-confirmation", stale_pick),
        (model["inventory_reorder"]["stale_policy_file_id"], "reorder-policy-R3.xlsx", "reorder-policy", stale_policy),
        (model["document_compliance"]["stale_checklist_file_id"], "compliance-checklist-2026-01-26.xlsx", "compliance-checklist", stale_checklist),
        (model["channel_order_sync"]["stale_export_file_id"], f"{world['channel']}-export-2026-02-02.json", "channel-export", stale_export),
        (hr["stale_approval_file_id"], "headcount-approval-2025.pdf", "headcount-approval", stale_headcount),
        (pb["stale_batch_file_id"], f"PRICE-BATCH-{short}-2026Q1.csv", "price-batch", stale_batch),
    ]


def _q_filters(q: str | None) -> dict[str, str]:
    filters: dict[str, str] = {}
    if not q:
        return filters
    for clause in re.split(r"\s+and\s+", q, flags=re.IGNORECASE):
        match = re.match(r"\s*([A-Za-z_]+)\s*=\s*'?([^']*)'?\s*$", clause)
        if match:
            filters[match.group(1)] = match.group(2)
    return filters


def seed_database(task: dict[str, Any], path: Path) -> sqlite3.Connection:
    if path.exists():
        path.unlink()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    world = next(world for world in _worlds() if world["code"] == task["tenant_code"])
    model = world_model(world["code"])
    short = world["short"]
    code = world["code"]
    org = world["org"]
    customer = world["customer"]
    supplier = world["supplier"]
    expedite = world["expedite_supplier"]
    people = world["people"]
    task_id = task["task_id"]
    ex = connection.execute
    exm = connection.executemany

    ex("INSERT INTO tenants VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (code, world["company"], org, world["bu"], world["currency"], world["country"], world["profile"], AS_OF))
    exm(
        "INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("analyst", code, "Operations analyst", "analyst", f"analyst@{world['domain']}", 0.0),
            ("ops_lead", code, people["ops_lead"], "operations lead", f"{people['ops_lead'].lower().replace(' ', '.')}@{world['domain']}", 25000.0),
            ("finance_lead", code, people["finance_lead"], "finance lead", f"{people['finance_lead'].lower().replace(' ', '.')}@{world['domain']}", 250000.0),
            ("hr_lead", code, people["hr_lead"], "hr lead", f"{people['hr_lead'].lower().replace(' ', '.')}@{world['domain']}", 50000.0),
        ],
    )
    exm(
        "INSERT INTO items VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)",
        [(item["item_id"], code, item["item_number"], item["description"], org, "EA", item["list_price"], item["unit_cost"], item["status"], "2026-01-01") for item in model["items"]],
    )
    exm(
        "INSERT INTO customers VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (customer["number"], code, customer["name"], customer["credit_limit"], int(customer["credit_hold"]), "Net 30", "sales_ops", f"MSG-{short}-CUSTOMER-SETUP"),
            (f"CUST-{short}-DECOY1", code, f"{world['industry'].split()[0]} Outlet Co.", 40000.0, 0, "Net 30", "sales_ops", None),
            (f"CUST-{short}-DECOY2", code, "Northern Regional Buyers", 55000.0, 1, "Net 45", "sales_ops", None),
        ],
    )
    exm(
        "INSERT INTO suppliers VALUES (?, ?, ?, ?, ?, ?)",
        [
            (supplier["number"], code, supplier["name"], supplier["lead_time_days"], 0.0, "Active"),
            (expedite["number"], code, expedite["name"], expedite["lead_time_days"], expedite["premium_pct"], "Active"),
            (f"SUP-{short}-DECOY", code, "Legacy Components Ltd.", 30, 0.0, "Inactive"),
        ],
    )

    # Sales orders: prior partial import, shipping order, synced channel orders, decoy.
    oi = model["order_import"]
    prior_lines = [{"ProductNumber": line["item_number"], "OrderedQuantity": line["quantity"], "OrderedUOM": "EA", "UnitListPrice": line["list_price"]} for line in oi["lines"] if line["previously_imported"]]
    orders = [
        (oi["prior_order_number"], code, oi["stale_batch_file_id"], "OPS", customer["number"], customer["name"], customer["po"], "Standard Orders", org, 1, "Awaiting Shipping", oi["prior_total"], _json(prior_lines), "ops_lead", f"MSG-{short}-ORDER-0203", "2026-02-03T10:12:00Z", None),
        (model["shipment_verification"]["order"], code, f"MSG-{short}-ORDER-0130", "OPS", customer["number"], customer["name"], f"{customer['po']}-B", "Standard Orders", org, 1, "Awaiting Shipping", model["shipment_verification"]["confirmed_value"], _json([{"ProductNumber": line["item_number"], "OrderedQuantity": line["requested"], "OrderedUOM": "EA", "UnitListPrice": line["list_price"]} for line in model["shipment_verification"]["lines"]]), "ops_lead", f"MSG-{short}-ORDER-0130", "2026-01-30T09:00:00Z", None),
        (f"SO-{short}-DECOY", code, "MANUAL-2026-01", "OPS", f"CUST-{short}-DECOY1", f"{world['industry'].split()[0]} Outlet Co.", "OUTLET-118", "Standard Orders", org, 1, "Closed", 1280.0, _json([]), "ops_lead", None, "2026-01-12T09:00:00Z", None),
    ]
    for row in model["channel_order_sync"]["rows"]:
        if row["already_synced"]:
            orders.append((row["synced_order_number"], code, row["channel_order_id"], world["channel"], None, row["buyer"], row["channel_order_id"], "Standard Orders", org, 1, "Booked", row["total"], _json([]), "channel_sync", None, "2026-02-02T08:00:00Z", None))
    exm("INSERT INTO sales_orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", orders)

    sv = model["shipment_verification"]
    ex("INSERT INTO shipments VALUES (?, ?, ?, ?, ?, ?, ?)", (sv["shipment"], code, sv["order"], "Staged", org, customer["name"], "2026-02-09"))
    ex("INSERT INTO shipments VALUES (?, ?, ?, ?, ?, ?, ?)", (f"SHP-{short}-DECOY", code, f"SO-{short}-DECOY", "Shipped", org, f"{world['industry'].split()[0]} Outlet Co.", "2026-01-14"))
    exm(
        "INSERT INTO shipment_lines VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)",
        [(line["shipment_line_id"], code, sv["shipment"], line["line"], line["item_number"], line["requested"], line["shipped"], line["list_price"], "Staged", None) for line in sv["lines"]]
        + [(700000 + len(short), code, f"SHP-{short}-DECOY", 1, model["items"][0]["item_number"], 40, 40, model["items"][0]["list_price"], "Shipped", None)],
    )

    rc = model["receivables_collection"]
    invoices = [(row["customer_transaction_id"], code, row["transaction_number"], customer["number"], row["amount"], row["amount"], "2026-01-05", row["due_date"], "Open", None) for row in rc["invoices"]]
    invoices.append((999000 + len(short), code, f"INV-{short}-DECOY", f"CUST-{short}-DECOY1", 3200.0, 3200.0, "2026-01-20", "2026-02-19", "Open", None))
    exm("INSERT INTO receivables_invoices VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", invoices)
    ex("INSERT INTO standard_receipts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)", (930000 + len(short), code, f"RCPT-{short}-PRIOR", 4400.0, "2026-01-22", customer["number"], "Wire", world["bu"], world["currency"], "Applied", _json([{"ReferenceType": "INVOICE", "ReferenceNumber": f"INV-{short}-PRIOR", "ApplyAmount": 4400.0}]), "ar_clerk"))

    ir = model["inventory_reorder"]
    exm(
        "INSERT INTO onhand_balances VALUES (?, ?, ?, ?, ?, ?, ?)",
        [(100 + index, code, org, sku["item_number"], "MAIN", sku["on_hand"], sku["reserved"]) for index, sku in enumerate(ir["skus"])],
    )
    open_lines = [sku for sku in ir["skus"] if sku["open_po_qty"]]
    ap = model["receiving_ap_match"]
    ex("INSERT INTO purchase_orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (ap["po"], ap["po_id"], code, supplier["name"], supplier["number"], "Open", "2026-01-26", ap["invoice_total"], "buyer"))
    exm(
        "INSERT INTO purchase_order_lines VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)",
        [(ap["po_id"] * 10 + line["line"], code, ap["po"], line["line"], line["item_number"], line["ordered"], line["po_price"], 0, "2026-02-06") for line in ap["lines"]],
    )
    if open_lines:
        open_po = f"PO-{short}-OPEN-SUPPLY"
        ex("INSERT INTO purchase_orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (open_po, ap["po_id"] + 1, code, supplier["name"], supplier["number"], "Open", "2026-02-01", sum(sku["open_po_qty"] * sku["unit_cost"] for sku in open_lines), "buyer"))
        exm(
            "INSERT INTO purchase_order_lines VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)",
            [((ap["po_id"] + 1) * 10 + index, code, open_po, index, sku["item_number"], sku["open_po_qty"], sku["unit_cost"], 0, "2026-02-14") for index, sku in enumerate(open_lines, start=1)],
        )
    ex("INSERT INTO purchase_orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (f"PO-{short}-CLOSED", ap["po_id"] + 2, code, supplier["name"], supplier["number"], "Closed", "2025-12-10", 980.0, "buyer"))

    dc = model["document_compliance"]
    workers = [(doc["person_number"], code, doc["person"], world["company"], "plant operative", "2025-06-01", None, None, "Active", None, "hr_lead", None) for doc in dc["documents"]]
    sr = model["shift_rollup"]
    workers += [(code_, code, f"Shift staff {code_}", world["company"], "shift operator", "2025-09-01", None, None, "Active", None, "hr_lead", None) for code_ in sr["roster_codes"]]
    hr = model["hire_against_requisition"]
    workers += [(f"{short}-P{3001 + index}", code, f"Incumbent {index + 1}", world["company"], hr["job"], "2025-03-01", None, hr["wage"], "Active", None, "hr_lead", None) for index in range(hr["current"])]
    exm("INSERT INTO workers VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", workers)
    exm(
        "INSERT INTO document_records VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)",
        [(doc["document_record_id"], code, doc["person_number"], doc["document_type"], doc["date_to"], "ALERTED" if doc["alerted"] else "ACTIVE", 0, doc["check_outcome"], int(doc["check_pending"]), world["company"]) for doc in dc["documents"]],
    )
    exm(
        "INSERT INTO absences VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)",
        [(1 + index, code, code_, "Approved leave", sr["shift_date"], sr["shift_date"], world["company"], "APPROVED", "hr_lead") for index, code_ in enumerate(sr["approved_absent"])],
    )
    co = model["channel_order_sync"]
    exm(
        "INSERT INTO channel_orders VALUES (?, ?, ?, ?, ?, ?, ?)",
        [(row["row"], code, world["channel"], row["channel_order_id"], row["buyer"], row["total"], row["synced_order_number"]) for row in co["rows"]],
    )

    # Mail
    messages = [
        (f"MSG-{task_id}-REQUEST", code, f"{task_id} operating request", f"{people['requester'].lower().replace(' ', '.')}@{world['domain']}", _json([f"analyst@{world['domain']}"]), task["prompt"], AS_OF, task_id),
        (f"MSG-{short}-AUTHORITY-0209", code, f"{world['company']} operating authority for February", f"{people['ops_lead'].lower().replace(' ', '.')}@{world['domain']}", _json([f"analyst@{world['domain']}"]), _render_asset(*asset_payloads(world)[f"assets/{code.lower()}/24-authority-memo.eml"]), "2026-02-09T07:30:00Z", None),
        (rc["remittance_message_id"], code, f"Remittance advice from {customer['name']}", f"ap@{customer['name'].lower().split()[0]}-sim.example", _json([f"ar@{world['domain']}"]), f"Please find our remittance advice attached as {rc['remittance_file_id']}. Payment of {rc['receipt_amount']:.2f} by {rc['receipt_method']} on {rc['receipt_date']} covers the invoices listed there. Other invoices are being reviewed by our accounts team.", "2026-02-06T11:20:00Z", None),
        (f"MSG-{short}-SUPPLIER-INVOICE-0207", code, f"Invoice {ap['invoice_number']} for {ap['po']}", f"billing@{supplier['name'].lower().split()[0]}-sim.example", _json([f"ap@{world['domain']}"]), f"Attached is invoice {ap['invoice_number']} for purchase order {ap['po']} (file {ap['invoice_file_id']}). Delivery note DN-{short}-0206 was signed at {world['site']} on 2026-02-06.", "2026-02-07T09:05:00Z", None),
        (f"MSG-{short}-AUDITOR-0205", code, "Compliance audit scope", f"audit@{world['domain']}", _json([f"hr@{world['domain']}"]), f"The audit covers worker documents expiring within {30} days and any mandatory check that has failed or is still pending. Use the 2026-02-09 checklist ({dc['checklist_file_id']}); the January checklist is superseded.", "2026-02-05T14:00:00Z", None),
        (f"MSG-{short}-SUPERVISOR-0208", code, f"{sr['shift']} shift {sr['shift_date']} reports", f"{people['supervisor'].lower().replace(' ', '.')}@{world['domain']}", _json([f"analyst@{world['domain']}"]), f"Reports for the {sr['shift'].lower()} shift on {sr['shift_date']} are in the shared drive; the cutoff is {sr['cutoff']}. Approved leave is on the roster ({sr['roster_file_id']}). Anyone rostered, not on approved leave and without a report is an unauthorized absence.", "2026-02-08T23:30:00Z", None),
        (f"MSG-{short}-CHANNEL-0209", code, f"{world['channel']} export ready", f"ecommerce@{world['domain']}", _json([f"analyst@{world['domain']}"]), f"This week's {world['channel']} export is {co['export_file_id']}. Orders already carrying a sales order number were synced last week; the export may contain repeated rows. A new buyer introduced themselves in the customers channel.", "2026-02-09T06:10:00Z", None),
        (f"MSG-{short}-HIRING-0209", code, f"{hr['job']} hiring round", f"{people['hr_lead'].lower().replace(' ', '.')}@{world['domain']}", _json([f"analyst@{world['domain']}"]), f"Close the {hr['job']} round against the 2026 headcount approval ({hr['approval_file_id']}). Candidates are in the register; contracts run {hr['contract_months']} months from today at the approved wage. Do not hire beyond the approved headcount.", "2026-02-09T08:00:00Z", None),
        (f"MSG-{short}-PRICING-0209", code, f"{model['price_list_batch']['batch']} for review", f"pricing@{world['domain']}", _json([f"analyst@{world['domain']}"]), f"The {world['quarter']} batch is {model['price_list_batch']['batch_file_id']}. Policy: known active items only, no effective dates in the past, changes within {model['price_list_batch']['max_change_pct']:.0f}%, and the later effective date wins when an item appears twice.", "2026-02-09T08:15:00Z", None),
        (f"MSG-{short}-OLD-INSTRUCTIONS", code, "Old shortcuts (superseded)", f"former.analyst@{world['domain']}", _json([f"analyst@{world['domain']}"]), "Just import whatever the customer sends, pay invoices as billed and hire everyone on the list. (Superseded by the February authority memo.)", "2025-11-02T08:00:00Z", None),
    ]
    exm("INSERT INTO mail_messages VALUES (?, ?, ?, ?, ?, ?, ?, ?)", messages)

    # Drive
    files = []
    ids = drive_file_ids(short)
    for path_, (kind, content) in asset_payloads(world).items():
        name = path_.rsplit("/", 1)[-1]
        suffix = name.rsplit(".", 1)[-1]
        logical = name[3:].rsplit(".", 1)[0]
        is_current = 0 if name.startswith(("02-", "04-")) else 1
        files.append((ids[name], code, name, MIME_BY_SUFFIX[suffix], logical, 2, is_current, _render_asset(kind, content), "2026-02-09T06:00:00Z" if is_current else "2026-02-03T10:00:00Z"))
    for file_id, name, logical, content in _stale_files(world, model):
        files.append((file_id, code, name, MIME_BY_SUFFIX[name.rsplit('.', 1)[-1]], logical, 1, 0, content, "2026-01-26T09:00:00Z"))
    exm("INSERT INTO drive_files VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", files)

    # Sheets
    ranges = {
        "Register!A1:H40": [["Record", "Option", "Values", "", "", "", "", "Source"], [f"SO-{short}-DECOY", "closed_manual_order", 1, 0, 1280.0, 0, 0, "MANUAL-2026-01"]],
        "PriceList!A1:E12": [["Item", "Description", "List price", "Status", "Effective"]] + [[item["item_number"], item["description"], item["list_price"], item["status"], "2026-01-01"] for item in model["items"]],
        "Shipping!A1:F20": [["Shipment", "Order", "Status", "Lines", "Value", "Verified"], [f"SHP-{short}-DECOY", f"SO-{short}-DECOY", "Shipped", 1, 40 * model["items"][0]["list_price"], "yes"], [sv["shipment"], sv["order"], "Staged", len(sv["lines"]), "", "no"]],
        "Aging!A1:E12": [["Invoice", "Amount", "Due", "Days past due", "Status"]] + [[row["transaction_number"], row["amount"], row["due_date"], max(row["days_past_due"], 0), "open"] for row in rc["invoices"]],
        "Reorder!A1:F12": [["Item", "Reorder point", "Planned maximum", "Open POs count", "Revision", "Need window"]] + [[sku["item_number"], sku["reorder_point"], sku["max_level"], "yes", "R4", ir["need_days"]] for sku in ir["skus"]],
        "Compliance!A1:G14": [["Person", "Person number", "Document", "Expires", "Days", "Check", "Alerted"]] + [[doc["person"], doc["person_number"], doc["document_type"], doc["date_to"], doc["days_to_expiry"], doc["check_outcome"], "yes" if doc["alerted"] else "no"] for doc in dc["documents"]],
        "Shifts!A1:F30": [["Staff", "Shift", "Date", "Approved leave", "Reported", "Late"]] + [[code_, sr["shift"], sr["shift_date"], "yes" if code_ in sr["approved_absent"] else "no", "", ""] for code_ in sr["roster_codes"]],
        "Customers!A1:E12": [["Customer", "Number", "Email", "Tax id", "Channel"], [customer["name"], customer["number"], f"ap@{customer['name'].lower().split()[0]}-sim.example", f"TX-{short}-0001", "direct"], [f"{world['industry'].split()[0]} Outlet Co.", f"CUST-{short}-DECOY1", "buyer@outlet-sim.example", f"TX-{short}-0002", "direct"]],
        "Headcount!A1:E12": [["Position", "Approved", "Current", "Open", "Revision"], [hr["job"], hr["approved"], hr["current"], "", "2026-R2"]],
        "PricingPolicy!A1:C6": [["Rule", "Value", "Note"], ["Maximum change pct", model["price_list_batch"]["max_change_pct"], "per line versus current list price"], ["Past effective dates", "reject", ""], ["Unknown or inactive items", "reject", ""], ["Same item twice", "later effective date wins", "earlier line superseded"]],
    }
    ex("INSERT INTO spreadsheets VALUES (?, ?, ?, ?)", (f"SHEET-{short}-OPS", code, f"{world['company']} operations register", _json(ranges)))

    # Chat
    channel = f"#ops-{short.lower()}"
    chat = [
        (f"CHAT-{task_id}-1", code, channel, f"THREAD-{task_id}", people["ops_lead"], f"Please resolve {task_id} against the current February authority; keep the handoff in review.", AS_OF, task_id),
        (f"CHAT-{task_id}-2", code, channel, f"THREAD-{task_id}", "controls", "Operative sources are listed in the source map file; superseded versions stay in Drive for reference only.", AS_OF, task_id),
        (f"CHAT-{short}-PRIOR-IMPORT", code, channel, f"THREAD-{short}-IMPORT", people["ops_lead"], f"Partial import for {customer['po']} went in on 2026-02-03 as {oi['prior_order_number']}; the rest of the lines are still pending.", "2026-02-03T10:20:00Z", None),
        (f"CHAT-{short}-WAREHOUSE", code, f"#warehouse-{short.lower()}", f"THREAD-{short}-WH", people["supervisor"], f"{sv['shipment']} picked; the pick confirmation is uploaded, a couple of lines did not match the requested quantity.", "2026-02-08T22:10:00Z", None),
        (f"CHAT-{short}-PLANNING", code, f"#planning-{short.lower()}", f"THREAD-{short}-PLAN", people["ops_lead"], f"Reorder run today: use policy R4 (open POs count as supply) and the {ir['need_days']}-day need window; {supplier['name']} lead time is {supplier['lead_time_days']} days.", "2026-02-09T07:45:00Z", None),
        (f"CHAT-{short}-HR", code, f"#hr-{short.lower()}", f"THREAD-{short}-HR", people["hr_lead"], "Compliance audit next week; document alerts, failed checks and the hiring round all need closing this week.", "2026-02-06T09:00:00Z", None),
        (f"CHAT-{short}-SHIFT", code, f"#shift-{short.lower()}", f"THREAD-{short}-SHIFT", people["supervisor"], f"{sr['shift']} shift {sr['shift_date']}: reports due by {sr['cutoff']}; overtime is measured from shift end.", "2026-02-08T21:00:00Z", None),
        (f"CHAT-{short}-PRICING", code, f"#pricing-{short.lower()}", f"THREAD-{short}-PRICE", "pricing", f"Price batch {model['price_list_batch']['batch']} is out; policy tab in the ops register applies.", "2026-02-09T08:20:00Z", None),
        (f"CHAT-{short}-CAPTURE-1", code, f"#customers-{short.lower()}", f"THREAD-{short}-CAPTURE", "sales-inbox", f"New buyer from {world['channel']}: {co['new_customer']['name']}, tax id {co['new_customer']['tax_id']}, orders via {co['new_customer']['email']}. Needs a master record before invoicing.", "2026-02-09T06:30:00Z", None),
        (f"CHAT-{short}-CAPTURE-2", code, f"#customers-{short.lower()}", f"THREAD-{short}-CAPTURE", people["ops_lead"], "Capture it in the customer master tab, not as a note; check the channel export for their first order.", "2026-02-09T06:35:00Z", None),
    ]
    exm("INSERT INTO chat_messages VALUES (?, ?, ?, ?, ?, ?, ?, ?)", chat)
    connection.commit()
    return connection


def _worlds() -> tuple[dict[str, Any], ...]:
    from .spec import WORLDS

    return WORLDS


def _row(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    result = dict(row)
    for key in list(result):
        if key.endswith("_json"):
            result[key.removesuffix("_json")] = json.loads(result.pop(key))
    return result


def _rows(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [_row(row) or {} for row in rows]


TABLES = (
    "tenants", "users", "items", "customers", "suppliers", "sales_orders", "shipments", "shipment_lines",
    "receivables_invoices", "standard_receipts", "onhand_balances", "purchase_orders", "purchase_order_lines",
    "purchase_requisitions", "receiving_receipt_requests", "ap_invoices", "invoice_holds", "workers",
    "document_records", "absences", "channel_orders", "mail_messages", "mail_drafts", "drive_files",
    "spreadsheets", "sheet_changes", "chat_messages", "chat_posts", "decisions", "submissions", "audit_log",
)

IMMUTABLE_TABLES = (
    "tenants", "users", "customers", "suppliers", "onhand_balances", "purchase_orders", "channel_orders",
    "mail_messages", "drive_files", "chat_messages", "shipments",
)


class ErpWorld:
    def __init__(self, task: dict[str, Any], connection: sqlite3.Connection):
        self.task = task
        self.connection = connection
        self.connection.row_factory = sqlite3.Row
        self.trace: list[dict[str, Any]] = []
        self.model = world_model(task["tenant_code"])
        self.world = self.model["world"]
        self.short = self.world["short"]

    @classmethod
    def create(cls, task: dict[str, Any], path: Path) -> "ErpWorld":
        return cls(task, seed_database(task, path))

    def close(self) -> None:
        self.connection.close()

    def snapshot(self) -> dict[str, list[dict[str, Any]]]:
        return {table: _rows(self.connection.execute(f"SELECT * FROM {table} ORDER BY 1").fetchall()) for table in TABLES}

    def _audit(self, tool: str, target: str, payload: dict[str, Any]) -> None:
        self.connection.execute("INSERT INTO audit_log(task_id, tool, target, payload_json) VALUES (?, ?, ?, ?)", (payload.get("task_id"), tool, target, _json(payload)))

    def _assert_task(self, arguments: dict[str, Any]) -> None:
        if arguments.get("task_id") != self.task["task_id"]:
            raise ValueError("write is outside the active task scope")

    def call_tool(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if tool not in READ_TOOLS | WRITE_TOOLS:
            result = {"error": f"unknown tool: {tool}"}
            self._record(tool, arguments, False, result)
            return result
        try:
            result = self._dispatch(tool, deepcopy(arguments))
            self.connection.commit()
            self._record(tool, arguments, True, result)
            return result
        except (KeyError, TypeError, ValueError, AttributeError, sqlite3.Error) as exc:
            self.connection.rollback()
            result = {"error": str(exc) or exc.__class__.__name__}
            self._record(tool, arguments, False, result)
            return result

    def _record(self, tool: str, arguments: dict[str, Any], success: bool, result: dict[str, Any]) -> None:
        self.trace.append({"index": len(self.trace) + 1, "server": SERVER_BY_PREFIX.get(tool.split(".", 1)[0], "erpbench"), "tool": tool, "arguments": deepcopy(arguments), "success": success, "result": deepcopy(result)})

    def _one(self, query: str, values: tuple[Any, ...]) -> dict[str, Any]:
        value = _row(self.connection.execute(query, values).fetchone())
        if value is None:
            raise ValueError("record not found")
        return value

    def _all(self, query: str, values: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        return _rows(self.connection.execute(query, values).fetchall())

    def _filtered(self, table: str, q: str | None, mapping: dict[str, str], order: str) -> list[dict[str, Any]]:
        filters = _q_filters(q)
        clauses = ["tenant_code = ?"]
        values: list[Any] = [self.task["tenant_code"]]
        for field, value in filters.items():
            column = mapping.get(field)
            if column:
                clauses.append(f"{column} = ?")
                values.append(value)
        return self._all(f"SELECT * FROM {table} WHERE {' AND '.join(clauses)} ORDER BY {order}", tuple(values))

    # ------------------------------------------------------------------
    def _dispatch(self, tool: str, a: dict[str, Any]) -> dict[str, Any]:  # noqa: C901 - one dispatch table per world
        code = self.task["tenant_code"]
        short = self.short
        model = self.model
        if tool == "erpbench.get_task":
            if a["task_id"] != self.task["task_id"]:
                raise ValueError("task not found")
            return {
                "task_id": self.task["task_id"],
                "prompt": self.task["prompt"],
                "tenant_code": code,
                "company": self.task["company"],
                "as_of": AS_OF,
                "answer_schema": self.task["answer_schema"],
                "decision_options": [{"id": option["id"], "label": option["label"]} for option in self.task["decision_options"]],
                "status_options": deepcopy(self.task["status_options"]),
                "register_contract": deepcopy(self.task["register_contract"]),
                "allowed_write_tools": self.task["allowed_write_tools"],
                "ops_channel": f"#ops-{short.lower()}",
                "handoff": "Save one review-only email draft and one ops-channel post; both stay draft_for_review. Record the decision, then submit the structured answer.",
            }
        if tool == "erpbench.get_decision":
            return self._one("SELECT * FROM decisions WHERE task_id = ?", (a["task_id"],))
        if tool == "erpbench.get_submission":
            return self._one("SELECT * FROM submissions WHERE task_id = ?", (a["task_id"],))
        if tool == "erpbench.record_decision":
            self._assert_task(a)
            decision_id = f"DECISION-{a['task_id']}"
            self.connection.execute("INSERT OR REPLACE INTO decisions VALUES (?, ?, ?, ?, ?, ?, ?)", (decision_id, a["task_id"], a["decision"], a["status"], a["primary_record"], a["rationale"], _json(a["source_refs"])))
            self._audit(tool, decision_id, a)
            return self._one("SELECT * FROM decisions WHERE decision_id = ?", (decision_id,))
        if tool == "erpbench.submit_answer":
            self._assert_task(a)
            if not isinstance(a["answers"], dict):
                raise ValueError("answers must be an object")
            self.connection.execute("INSERT OR REPLACE INTO submissions VALUES (?, ?)", (a["task_id"], _json(a["answers"])))
            self._audit(tool, a["task_id"], a)
            return {"task_id": a["task_id"], "answers": a["answers"], "durable": True}

        # ---- Oracle: product master, customers, orders ----
        if tool == "oracle_fusion.items.list":
            rows = self._filtered("items", a.get("q"), {"OrganizationCode": "organization_code", "ItemNumber": "item_number", "ItemStatusValue": "item_status"}, "item_number")
            return {"items": [{"ItemId": row["item_id"], "ItemNumber": row["item_number"], "ItemDescription": row["description"], "OrganizationCode": row["organization_code"], "PrimaryUOMValue": row["primary_uom"], "ListPrice": row["list_price"], "ItemStatusValue": row["item_status"], "PriceEffectiveDate": row["price_effective_date"]} for row in rows], "count": len(rows)}
        if tool == "oracle_fusion.items.update":
            self._assert_task(a)
            item = self._one("SELECT * FROM items WHERE item_id = ? AND tenant_code = ?", (a["ItemId"], code))
            if item["item_status"] != "Active":
                raise ValueError("cannot update the price of an inactive item")
            if not isinstance(a["ListPrice"], (int, float)) or a["ListPrice"] <= 0:
                raise ValueError("ListPrice must be a positive number")
            self.connection.execute("UPDATE items SET list_price = ?, price_effective_date = ?, last_task_id = ? WHERE item_id = ?", (round(float(a["ListPrice"]), 2), a["EffectiveDate"], a["task_id"], a["ItemId"]))
            self._audit(tool, str(a["ItemId"]), a)
            row = self._one("SELECT * FROM items WHERE item_id = ?", (a["ItemId"],))
            return {"ItemId": row["item_id"], "ItemNumber": row["item_number"], "ListPrice": row["list_price"], "PriceEffectiveDate": row["price_effective_date"], "LastUpdateDate": AS_OF}
        if tool == "oracle_fusion.customer_account_activities.get":
            customer = self._one("SELECT * FROM customers WHERE customer_number = ? AND tenant_code = ?", (a["AccountId"], code))
            invoices = self._all("SELECT * FROM receivables_invoices WHERE bill_to_customer_number = ? AND tenant_code = ? ORDER BY due_date", (a["AccountId"], code))
            open_invoices = [row for row in invoices if row["balance_due"] > 0]
            past_due = [row for row in open_invoices if row["due_date"] < AS_OF_DATE.isoformat()]
            return {"AccountId": customer["customer_number"], "CustomerName": customer["name"], "CreditLimit": customer["credit_limit"], "CreditHoldFlag": bool(customer["credit_hold"]), "PaymentTerms": customer["payment_terms"], "OpenTransactions": len(open_invoices), "OpenReceivablesAmount": round(sum(row["balance_due"] for row in open_invoices), 2), "PastDueAmount": round(sum(row["balance_due"] for row in past_due), 2), "AsOfDate": AS_OF_DATE.isoformat()}
        if tool == "oracle_fusion.sales_orders.list":
            rows = self._filtered("sales_orders", a.get("q"), {"CustomerPONumber": "customer_po_number", "SourceTransactionSystem": "source_transaction_system", "BuyingPartyNumber": "buying_party_number", "OrderNumber": "order_number", "Status": "status"}, "order_number")
            return {"items": [self._order_view(row, with_lines=False) for row in rows], "count": len(rows)}
        if tool == "oracle_fusion.sales_orders.get":
            row = self._one("SELECT * FROM sales_orders WHERE order_number = ? AND tenant_code = ?", (a["OrderKey"], code))
            return self._order_view(row, with_lines=True)
        if tool == "oracle_fusion.sales_orders.create":
            self._assert_task(a)
            lines = a.get("lines") or []
            if not isinstance(lines, list):
                raise ValueError("lines must be an array")
            if not lines and a.get("OrderTotal") is None:
                raise ValueError("an order needs lines or an OrderTotal")
            total = 0.0
            normalized = []
            for line in lines:
                item = _row(self.connection.execute("SELECT * FROM items WHERE item_number = ? AND tenant_code = ?", (line.get("ProductNumber"), code)).fetchone())
                if item is None:
                    raise ValueError(f"unknown item {line.get('ProductNumber')}")
                if item["item_status"] != "Active":
                    raise ValueError(f"item {item['item_number']} is inactive and cannot be ordered")
                quantity = int(line.get("OrderedQuantity") or 0)
                if quantity <= 0:
                    raise ValueError("OrderedQuantity must be positive")
                price = float(line.get("UnitListPrice", item["list_price"]))
                total += quantity * price
                normalized.append({"ProductNumber": item["item_number"], "OrderedQuantity": quantity, "OrderedUOM": line.get("OrderedUOM", "EA"), "UnitListPrice": round(price, 2)})
            if not lines:
                total = float(a["OrderTotal"])
            existing = _row(self.connection.execute("SELECT * FROM sales_orders WHERE source_transaction_number = ? AND source_transaction_system = ? AND tenant_code = ?", (a["SourceTransactionNumber"], a["SourceTransactionSystem"], code)).fetchone())
            if existing is not None:
                raise ValueError(f"source transaction {a['SourceTransactionNumber']} already exists as {existing['order_number']}")
            if a["SourceTransactionSystem"] == self.world["channel"]:
                channel_row = _row(self.connection.execute("SELECT * FROM channel_orders WHERE channel_order_id = ? AND tenant_code = ? ORDER BY row_id", (a["SourceTransactionNumber"], code)).fetchone())
                if channel_row is None:
                    raise ValueError("channel order not found in the export")
                create_rows = [row for row in model["channel_order_sync"]["rows"] if row["disposition"] == "create"]
                position = next((index for index, row in enumerate(create_rows, start=1) if row["channel_order_id"] == a["SourceTransactionNumber"]), None)
                order_number = f"SO-{short}-{52000 + (position or (len(create_rows) + 1)) * 7}"
            else:
                order_number = f"SO-{short}-{50000 + len(a['CustomerPONumber'])}"
                if _row(self.connection.execute("SELECT 1 FROM sales_orders WHERE order_number = ?", (order_number,)).fetchone()):
                    order_number = f"{order_number}-{self.connection.execute('SELECT COUNT(*) FROM sales_orders WHERE last_task_id = ?', (a['task_id'],)).fetchone()[0] + 1}"
            status = "Booked" if a["SubmittedFlag"] else "Draft"
            self.connection.execute(
                "INSERT INTO sales_orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (order_number, code, a["SourceTransactionNumber"], a["SourceTransactionSystem"], a.get("BuyingPartyNumber"), a.get("BuyingPartyName") or self._customer_name(a.get("BuyingPartyNumber")), a["CustomerPONumber"], a["TransactionType"], a["RequestedFulfillmentOrganizationCode"], int(bool(a["SubmittedFlag"])), status, round(total, 2), _json(normalized), "analyst", f"MSG-{a['task_id']}-REQUEST", AS_OF, a["task_id"]),
            )
            self._audit(tool, order_number, a)
            return self._order_view(self._one("SELECT * FROM sales_orders WHERE order_number = ?", (order_number,)), with_lines=True)
        if tool == "oracle_fusion.shipments.list":
            rows = self._filtered("shipments", a.get("q"), {"Shipment": "shipment", "ShipmentStatus": "shipment_status", "OrganizationCode": "organization_code"}, "shipment")
            return {"items": [{"Shipment": row["shipment"], "ShipmentStatus": row["shipment_status"], "OrganizationCode": row["organization_code"], "ShipToCustomer": row["ship_to_customer"], "Order": row["order_number"], "PlannedShipDate": row["planned_ship_date"]} for row in rows], "count": len(rows)}
        if tool == "oracle_fusion.shipment_lines.list":
            rows = self._filtered("shipment_lines", a.get("q"), {"Shipment": "shipment", "Item": "item_number", "LineStatus": "line_status"}, "shipment, line_number")
            return {"items": [self._shipment_line_view(row) for row in rows], "count": len(rows)}
        if tool == "oracle_fusion.shipment_lines.update":
            self._assert_task(a)
            line = self._one("SELECT * FROM shipment_lines WHERE shipment_line_id = ? AND tenant_code = ?", (a["ShipmentLine"], code))
            if line["line_status"] != "Staged":
                raise ValueError("only staged shipment lines can be updated")
            quantity = int(a["ShippedQuantity"])
            if quantity < 0 or quantity > line["requested_quantity"]:
                raise ValueError("ShippedQuantity must be between 0 and the requested quantity")
            self.connection.execute("UPDATE shipment_lines SET shipped_quantity = ?, comments = ?, last_task_id = ? WHERE shipment_line_id = ?", (quantity, a.get("Comments"), a["task_id"], a["ShipmentLine"]))
            self._audit(tool, str(a["ShipmentLine"]), a)
            return {**self._shipment_line_view(self._one("SELECT * FROM shipment_lines WHERE shipment_line_id = ?", (a["ShipmentLine"],))), "LastUpdateDate": AS_OF}
        if tool == "oracle_fusion.receivables_invoices.list":
            rows = self._filtered("receivables_invoices", a.get("q"), {"BillToCustomerNumber": "bill_to_customer_number", "InvoiceStatus": "invoice_status", "TransactionNumber": "transaction_number"}, "due_date")
            return {"items": [self._invoice_view(row) for row in rows], "count": len(rows)}
        if tool == "oracle_fusion.receivables_invoices.get":
            return self._invoice_view(self._one("SELECT * FROM receivables_invoices WHERE customer_transaction_id = ? AND tenant_code = ?", (a["CustomerTransactionId"], code)))
        if tool == "oracle_fusion.standard_receipts.list":
            rows = self._filtered("standard_receipts", a.get("q"), {"CustomerAccountNumber": "customer_account_number", "ReceiptNumber": "receipt_number"}, "receipt_date")
            return {"items": [self._receipt_view(row) for row in rows], "count": len(rows)}
        if tool == "oracle_fusion.standard_receipts.create":
            self._assert_task(a)
            self._one("SELECT * FROM customers WHERE customer_number = ? AND tenant_code = ?", (a["CustomerAccountNumber"], code))
            if _row(self.connection.execute("SELECT 1 FROM standard_receipts WHERE receipt_number = ? AND tenant_code = ?", (a["ReceiptNumber"], code)).fetchone()):
                raise ValueError("receipt number already exists")
            references = a["remittanceReferences"]
            if not isinstance(references, list) or not references:
                raise ValueError("remittanceReferences must list the invoices covered")
            applied = 0.0
            for reference in references:
                invoice = _row(self.connection.execute("SELECT * FROM receivables_invoices WHERE transaction_number = ? AND tenant_code = ?", (reference.get("ReferenceNumber"), code)).fetchone())
                if invoice is None:
                    raise ValueError(f"unknown invoice {reference.get('ReferenceNumber')}")
                if invoice["bill_to_customer_number"] != a["CustomerAccountNumber"]:
                    raise ValueError("invoice belongs to a different customer account")
                amount = float(reference.get("ApplyAmount", invoice["balance_due"]))
                if amount <= 0 or amount > invoice["balance_due"] + 0.005:
                    raise ValueError("ApplyAmount exceeds the open balance")
                applied += amount
            if abs(applied - float(a["ReceiptAmount"])) > 0.005:
                raise ValueError("applications must equal the receipt amount")
            for reference in references:
                invoice = self._one("SELECT * FROM receivables_invoices WHERE transaction_number = ? AND tenant_code = ?", (reference["ReferenceNumber"], code))
                balance = round(invoice["balance_due"] - float(reference.get("ApplyAmount", invoice["balance_due"])), 2)
                self.connection.execute("UPDATE receivables_invoices SET balance_due = ?, invoice_status = ?, last_task_id = ? WHERE customer_transaction_id = ?", (balance, "Closed" if balance <= 0.005 else "Open", a["task_id"], invoice["customer_transaction_id"]))
            receipt_id = model["receivables_collection"]["new_receipt_id"] + self.connection.execute("SELECT COUNT(*) FROM standard_receipts WHERE last_task_id = ?", (a["task_id"],)).fetchone()[0]
            self.connection.execute("INSERT INTO standard_receipts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (receipt_id, code, a["ReceiptNumber"], round(float(a["ReceiptAmount"]), 2), a["ReceiptDate"], a["CustomerAccountNumber"], a["ReceiptMethod"], a["BusinessUnit"], a["Currency"], "Applied", _json(references), "analyst", a["task_id"]))
            self._audit(tool, a["ReceiptNumber"], a)
            return self._receipt_view(self._one("SELECT * FROM standard_receipts WHERE standard_receipt_id = ?", (receipt_id,)))

        # ---- Oracle: inventory and procurement ----
        if tool == "oracle_fusion.onhand_balances.list":
            rows = self._filtered("onhand_balances", a.get("q"), {"OrganizationCode": "organization_code", "ItemNumber": "item_number", "Subinventory": "subinventory"}, "item_number")
            return {"items": [{"OrganizationCode": row["organization_code"], "ItemNumber": row["item_number"], "Subinventory": row["subinventory"], "OnhandQuantity": row["onhand_quantity"], "ReservedQuantity": row["reserved_quantity"], "AvailableToReserve": row["onhand_quantity"] - row["reserved_quantity"]} for row in rows], "count": len(rows)}
        if tool == "oracle_fusion.purchase_orders.list":
            rows = self._filtered("purchase_orders", a.get("q"), {"Supplier": "supplier", "Status": "status", "OrderNumber": "po_number", "SupplierNumber": "supplier_number"}, "po_number")
            return {"items": [self._po_view(row) for row in rows], "count": len(rows)}
        if tool == "oracle_fusion.purchase_orders.get":
            return self._po_view(self._one("SELECT * FROM purchase_orders WHERE po_number = ? AND tenant_code = ?", (a["purchaseOrdersUniqID"], code)))
        if tool == "oracle_fusion.purchase_order_lines.list":
            self._one("SELECT * FROM purchase_orders WHERE po_number = ? AND tenant_code = ?", (a["purchaseOrdersUniqID"], code))
            rows = self._all("SELECT * FROM purchase_order_lines WHERE po_number = ? AND tenant_code = ? ORDER BY line_number", (a["purchaseOrdersUniqID"], code))
            return {"items": [{"POLineId": row["po_line_id"], "LineNumber": row["line_number"], "Item": row["item_number"], "Quantity": row["quantity"], "UnitPrice": row["unit_price"], "ReceivedQuantity": row["received_quantity"], "PromisedDeliveryDate": row["promised_date"]} for row in rows], "count": len(rows)}
        if tool == "oracle_fusion.suppliers.list":
            rows = self._all("SELECT * FROM suppliers WHERE tenant_code = ? ORDER BY supplier_number", (code,))
            q = a.get("q") or ""
            numbers = re.findall(r"SUP-[A-Z0-9-]+", q)
            if numbers:
                rows = [row for row in rows if row["supplier_number"] in numbers]
            return {"items": [{"SupplierId": row["supplier_number"], "SupplierNumber": row["supplier_number"], "Supplier": row["name"], "LeadTimeDays": row["lead_time_days"], "ExpeditePremiumPct": row["expedite_premium_pct"], "Status": row["supplier_status"]} for row in rows], "count": len(rows)}
        if tool == "oracle_fusion.purchase_requisitions.create":
            self._assert_task(a)
            lines = a["lines"]
            if not isinstance(lines, list) or not lines:
                raise ValueError("a requisition needs at least one line")
            normalized = []
            total = 0.0
            for line in lines:
                item = _row(self.connection.execute("SELECT * FROM items WHERE item_number = ? AND tenant_code = ?", (line.get("ItemNumber"), code)).fetchone())
                if item is None or item["item_status"] != "Active":
                    raise ValueError(f"item {line.get('ItemNumber')} cannot be requisitioned")
                quantity = int(line.get("Quantity") or 0)
                if quantity <= 0:
                    raise ValueError("Quantity must be positive")
                price = round(float(line.get("UnitPrice", item["unit_cost"])), 2)
                total += quantity * price
                normalized.append({"ItemNumber": item["item_number"], "Quantity": quantity, "UOM": line.get("UOM", "EA"), "UnitPrice": price, "Supplier": line.get("Supplier"), "RequestedDeliveryDate": line.get("RequestedDeliveryDate")})
            count = self.connection.execute("SELECT COUNT(*) FROM purchase_requisitions WHERE last_task_id = ?", (a["task_id"],)).fetchone()[0]
            number = model["inventory_reorder"]["requisition_number"] if count == 0 else f"{model['inventory_reorder']['requisition_number']}-{count + 1}"
            self.connection.execute("INSERT INTO purchase_requisitions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (number, model["inventory_reorder"]["requisition_id"] + count, code, a["RequisitioningBU"], a["Preparer"], a["Description"], a["Justification"], "Incomplete", _json(normalized), round(total, 2), "analyst", a["task_id"]))
            self._audit(tool, number, a)
            return self._requisition_view(self._one("SELECT * FROM purchase_requisitions WHERE requisition_number = ?", (number,)))
        if tool == "oracle_fusion.purchase_requisitions.submit":
            self._assert_task(a)
            requisition = self._one("SELECT * FROM purchase_requisitions WHERE requisition_number = ? AND tenant_code = ?", (a["purchaseRequisitionsUniqID"], code))
            if requisition["document_status"] != "Incomplete":
                raise ValueError("requisition is not in a submittable status")
            self.connection.execute("UPDATE purchase_requisitions SET document_status = 'Pending approval', last_task_id = ? WHERE requisition_number = ?", (a["task_id"], a["purchaseRequisitionsUniqID"]))
            self._audit(tool, a["purchaseRequisitionsUniqID"], a)
            return self._requisition_view(self._one("SELECT * FROM purchase_requisitions WHERE requisition_number = ?", (a["purchaseRequisitionsUniqID"],)))
        if tool == "oracle_fusion.purchase_requisitions.get":
            return self._requisition_view(self._one("SELECT * FROM purchase_requisitions WHERE requisition_number = ? AND tenant_code = ?", (a["purchaseRequisitionsUniqID"], code)))
        if tool == "oracle_fusion.receiving_receipt_requests.list":
            rows = self._filtered("receiving_receipt_requests", a.get("q"), {"OrganizationCode": "organization_code", "VendorName": "vendor_name"}, "header_interface_id")
            return {"items": [{"HeaderInterfaceId": row["header_interface_id"], "ReceiptSourceCode": row["receipt_source_code"], "OrganizationCode": row["organization_code"], "VendorName": row["vendor_name"], "ProcessingStatusCode": row["processing_status"], "lines": row["lines"]} for row in rows], "count": len(rows)}
        if tool == "oracle_fusion.receiving_receipt_requests.create":
            self._assert_task(a)
            lines = a["lines"]
            if not isinstance(lines, list) or not lines:
                raise ValueError("a receipt request needs lines")
            normalized = []
            for line in lines:
                po_line = _row(self.connection.execute("SELECT * FROM purchase_order_lines WHERE po_number = ? AND line_number = ? AND tenant_code = ?", (line.get("DocumentNumber"), line.get("DocumentLineNumber"), code)).fetchone())
                if po_line is None:
                    raise ValueError("purchase-order line not found")
                quantity = int(line.get("Quantity") or 0)
                if quantity <= 0 or quantity + po_line["received_quantity"] > po_line["quantity"]:
                    raise ValueError("received quantity exceeds the open purchase-order quantity")
                self.connection.execute("UPDATE purchase_order_lines SET received_quantity = received_quantity + ?, last_task_id = ? WHERE po_line_id = ?", (quantity, a["task_id"], po_line["po_line_id"]))
                normalized.append({"DocumentNumber": line["DocumentNumber"], "DocumentLineNumber": int(line["DocumentLineNumber"]), "ItemNumber": po_line["item_number"], "Quantity": quantity, "TransactionType": line.get("TransactionType", "RECEIVE")})
            count = self.connection.execute("SELECT COUNT(*) FROM receiving_receipt_requests WHERE last_task_id = ?", (a["task_id"],)).fetchone()[0]
            header_id = model["receiving_ap_match"]["receipt_header_id"] + count
            self.connection.execute("INSERT INTO receiving_receipt_requests VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (header_id, code, a["ReceiptSourceCode"], a["OrganizationCode"], a.get("VendorName", ""), _json(normalized), "SUCCESS", "analyst", a["task_id"]))
            self._audit(tool, str(header_id), a)
            return {"HeaderInterfaceId": header_id, "ReceiptSourceCode": a["ReceiptSourceCode"], "OrganizationCode": a["OrganizationCode"], "ProcessingStatusCode": "SUCCESS", "lines": normalized}

        # ---- Oracle: payables ----
        if tool == "oracle_fusion.invoices.list":
            rows = self._filtered("ap_invoices", a.get("q"), {"Supplier": "supplier", "InvoiceNumber": "invoice_number", "BusinessUnit": "business_unit"}, "invoice_number")
            return {"items": [self._ap_invoice_view(row) for row in rows], "count": len(rows)}
        if tool == "oracle_fusion.invoices.get":
            return self._ap_invoice_view(self._one("SELECT * FROM ap_invoices WHERE invoice_number = ? AND tenant_code = ?", (a["invoicesUniqID"], code)))
        if tool == "oracle_fusion.invoices.create":
            self._assert_task(a)
            if _row(self.connection.execute("SELECT 1 FROM ap_invoices WHERE invoice_number = ? AND supplier = ? AND tenant_code = ?", (a["InvoiceNumber"], a["Supplier"], code)).fetchone()):
                raise ValueError("invoice already exists for this supplier")
            lines = a["invoiceLines"]
            if not isinstance(lines, list) or not lines:
                raise ValueError("an invoice needs lines")
            normalized = []
            total = 0.0
            for line in lines:
                po_line = _row(self.connection.execute("SELECT * FROM purchase_order_lines WHERE po_number = ? AND line_number = ? AND tenant_code = ?", (line.get("PurchaseOrderNumber"), line.get("PurchaseOrderLineNumber"), code)).fetchone())
                if po_line is None:
                    raise ValueError("purchase-order line not found for invoice matching")
                quantity = int(line.get("Quantity") or 0)
                price = round(float(line.get("UnitPrice") or 0), 2)
                if quantity <= 0 or price <= 0:
                    raise ValueError("invoice lines need positive quantity and price")
                total += quantity * price
                normalized.append({"LineNumber": int(line.get("LineNumber", len(normalized) + 1)), "PurchaseOrderNumber": line["PurchaseOrderNumber"], "PurchaseOrderLineNumber": int(line["PurchaseOrderLineNumber"]), "ItemNumber": po_line["item_number"], "Quantity": quantity, "UnitPrice": price, "ReceivedQuantity": po_line["received_quantity"], "PurchaseOrderPrice": po_line["unit_price"]})
            if abs(total - float(a["InvoiceAmount"])) > 0.005:
                raise ValueError("InvoiceAmount must equal the sum of the lines")
            count = self.connection.execute("SELECT COUNT(*) FROM ap_invoices WHERE last_task_id = ?", (a["task_id"],)).fetchone()[0]
            invoice_id = model["receiving_ap_match"]["invoice_id"] + count
            self.connection.execute("INSERT INTO ap_invoices VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (invoice_id, code, a["InvoiceNumber"], a["BusinessUnit"], a["Supplier"], round(total, 2), a["InvoiceCurrency"], a["InvoiceDate"], "Not validated", _json(normalized), "analyst", a["task_id"]))
            self._audit(tool, a["InvoiceNumber"], a)
            return self._ap_invoice_view(self._one("SELECT * FROM ap_invoices WHERE invoice_id = ?", (invoice_id,)))
        if tool == "oracle_fusion.invoices.validate":
            self._assert_task(a)
            if a["ProcessAction"] != "Validate":
                raise ValueError("ProcessAction must be Validate")
            invoice = self._one("SELECT * FROM ap_invoices WHERE invoice_number = ? AND supplier = ? AND tenant_code = ?", (a["InvoiceNumber"], a["Supplier"], code))
            holds = self._all("SELECT * FROM invoice_holds WHERE invoice_id = ? AND hold_status = 'Active'", (invoice["invoice_id"],))
            status = "Validated with holds" if holds else "Validated"
            self.connection.execute("UPDATE ap_invoices SET validation_status = ?, last_task_id = ? WHERE invoice_id = ?", (status, a["task_id"], invoice["invoice_id"]))
            self._audit(tool, a["InvoiceNumber"], a)
            return self._ap_invoice_view(self._one("SELECT * FROM ap_invoices WHERE invoice_id = ?", (invoice["invoice_id"],)))
        if tool == "oracle_fusion.invoice_holds.create":
            self._assert_task(a)
            invoice = self._one("SELECT * FROM ap_invoices WHERE invoice_id = ? AND tenant_code = ?", (a["InvoiceId"], code))
            if not str(a.get("HoldReason", "")).strip():
                raise ValueError("HoldReason is required")
            count = self.connection.execute("SELECT COUNT(*) FROM invoice_holds WHERE last_task_id = ?", (a["task_id"],)).fetchone()[0]
            hold_id = model["receiving_ap_match"]["hold_id"] + count
            self.connection.execute("INSERT INTO invoice_holds VALUES (?, ?, ?, ?, ?, ?, ?)", (hold_id, code, invoice["invoice_id"], a["HoldName"], a["HoldReason"], "Active", a["task_id"]))
            self.connection.execute("UPDATE ap_invoices SET validation_status = 'On hold', last_task_id = ? WHERE invoice_id = ?", (a["task_id"], invoice["invoice_id"]))
            self._audit(tool, str(hold_id), a)
            return {"HoldId": hold_id, "InvoiceId": invoice["invoice_id"], "HoldName": a["HoldName"], "HoldReason": a["HoldReason"], "HoldStatus": "Active"}

        # ---- Oracle: HCM shaped ----
        if tool == "oracle_fusion.workers.list":
            rows = self._filtered("workers", a.get("q"), {"LegalEmployerName": "legal_employer_name", "JobCode": "job_code", "PersonNumber": "person_number", "WorkerStatus": "worker_status"}, "person_number")
            return {"items": [self._worker_view(row) for row in rows], "count": len(rows)}
        if tool == "oracle_fusion.workers.create":
            self._assert_task(a)
            if _row(self.connection.execute("SELECT 1 FROM workers WHERE person_number = ? AND tenant_code = ?", (a["PersonNumber"], code)).fetchone()):
                raise ValueError("person number already exists")
            if _row(self.connection.execute("SELECT 1 FROM workers WHERE candidate_id = ? AND tenant_code = ?", (a["CandidateId"], code)).fetchone()):
                raise ValueError("candidate already hired")
            if a["LegalEmployerName"] != self.world["company"]:
                raise ValueError("legal employer is outside the active tenant")
            self.connection.execute("INSERT INTO workers VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (a["PersonNumber"], code, a["DisplayName"], a["LegalEmployerName"], a["JobCode"], a["HireDate"], a["ContractEndDate"], round(float(a["MonthlySalary"]), 2), "Active", a["CandidateId"], "analyst", a["task_id"]))
            self._audit(tool, a["PersonNumber"], a)
            return self._worker_view(self._one("SELECT * FROM workers WHERE person_number = ?", (a["PersonNumber"],)))
        if tool == "oracle_fusion.document_records.list":
            rows = self._filtered("document_records", a.get("q"), {"LegalEmployerName": "legal_employer_name", "PersonNumber": "person_number", "DocumentType": "document_type", "Status": "status"}, "document_record_id")
            return {"items": [self._document_view(row) for row in rows], "count": len(rows)}
        if tool == "oracle_fusion.document_records.update":
            self._assert_task(a)
            record = self._one("SELECT * FROM document_records WHERE document_record_id = ? AND tenant_code = ?", (a["DocumentRecordId"], code))
            if "Status" not in a and "VerifiedFlag" not in a:
                raise ValueError("nothing to update")
            status = a.get("Status", record["status"])
            verified = record["verified_flag"]
            if a.get("VerifiedFlag") is True:
                if record["check_outcome"] == "fail":
                    raise ValueError("a failed mandatory check cannot be marked verified")
                verified = 1
            elif a.get("VerifiedFlag") is False:
                verified = 0
            self.connection.execute("UPDATE document_records SET status = ?, verified_flag = ?, check_pending = ?, last_task_id = ? WHERE document_record_id = ?", (status, verified, 0 if verified else record["check_pending"], a["task_id"], a["DocumentRecordId"]))
            self._audit(tool, str(a["DocumentRecordId"]), a)
            return {**self._document_view(self._one("SELECT * FROM document_records WHERE document_record_id = ?", (a["DocumentRecordId"],))), "LastUpdateDate": AS_OF}
        if tool == "oracle_fusion.absences.list":
            rows = self._filtered("absences", a.get("q"), {"employer": "employer", "startDate": "start_date", "personNumber": "person_number", "absenceType": "absence_type"}, "absence_id")
            return {"items": [self._absence_view(row) for row in rows], "count": len(rows)}
        if tool == "oracle_fusion.absences.create":
            self._assert_task(a)
            self._one("SELECT * FROM workers WHERE person_number = ? AND tenant_code = ?", (a["personNumber"], code))
            if _row(self.connection.execute("SELECT 1 FROM absences WHERE person_number = ? AND start_date = ? AND tenant_code = ?", (a["personNumber"], a["startDate"], code)).fetchone()):
                raise ValueError("an absence already exists for this person and date")
            absence_id = 100 + self.connection.execute("SELECT COUNT(*) FROM absences WHERE last_task_id = ?", (a["task_id"],)).fetchone()[0]
            self.connection.execute("INSERT INTO absences VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (absence_id, code, a["personNumber"], a["absenceType"], a["startDate"], a["endDate"], a["employer"], a["absenceStatusCd"], "analyst", a["task_id"]))
            self._audit(tool, a["personNumber"], a)
            return self._absence_view(self._one("SELECT * FROM absences WHERE absence_id = ?", (absence_id,)))

        # ---- Gmail ----
        if tool == "gmail.messages.list":
            query = a["q"]
            rows = self._all("SELECT message_id, subject, sender, sent_at, task_id FROM mail_messages WHERE tenant_code = ? AND (subject LIKE ? OR body LIKE ? OR task_id = ?) ORDER BY sent_at DESC", (code, f"%{query}%", f"%{query}%", query))
            return {"messages": [{"id": row["message_id"], "subject": row["subject"], "from": row["sender"], "internalDate": row["sent_at"], "task_id": row["task_id"]} for row in rows], "resultSizeEstimate": len(rows)}
        if tool == "gmail.messages.get":
            row = self._one("SELECT * FROM mail_messages WHERE message_id = ? AND tenant_code = ?", (a["id"], code))
            return {"id": row["message_id"], "subject": row["subject"], "from": row["sender"], "to": row["recipients"], "internalDate": row["sent_at"], "body": row["body"], "task_id": row["task_id"]}
        if tool == "gmail.drafts.create":
            self._assert_task(a)
            if not str(a.get("body", "")).strip() or not str(a.get("to", "")).strip():
                raise ValueError("a draft needs a recipient and a body")
            draft_id = f"DRAFT-{a['task_id']}"
            self.connection.execute("INSERT OR REPLACE INTO mail_drafts VALUES (?, ?, ?, ?, ?, ?, ?)", (draft_id, code, a["task_id"], a["to"], a["subject"], a["body"], "draft_for_review"))
            self._audit(tool, draft_id, a)
            return {"id": draft_id, "message": {"to": a["to"], "subject": a["subject"], "labelIds": ["DRAFT"]}, "review_status": "draft_for_review"}
        if tool == "gmail.drafts.get":
            row = self._one("SELECT * FROM mail_drafts WHERE draft_id = ? AND tenant_code = ?", (a["id"], code))
            return {"id": row["draft_id"], "message": {"to": row["recipient"], "subject": row["subject"], "body": row["body"], "labelIds": ["DRAFT"]}, "review_status": row["review_status"]}

        # ---- Drive ----
        if tool == "google_drive.files.list":
            query = a["q"]
            match = re.search(r"name contains '([^']+)'", query)
            rows = self._all("SELECT * FROM drive_files WHERE tenant_code = ? ORDER BY name", (code,))
            if match:
                needle = match.group(1).lower()
                rows = [row for row in rows if needle in row["name"].lower() or needle in row["logical_name"].lower() or needle in row["content"].lower()]
            return {"files": [{"id": row["file_id"], "name": row["name"], "mimeType": row["mime_type"], "version": row["version"], "isCurrentAuthority": bool(row["is_current"]), "modifiedTime": row["modified_time"]} for row in rows]}
        if tool == "google_drive.files.get":
            row = self._one("SELECT * FROM drive_files WHERE file_id = ? AND tenant_code = ?", (a["fileId"], code))
            return {"id": row["file_id"], "name": row["name"], "mimeType": row["mime_type"], "version": row["version"], "isCurrentAuthority": bool(row["is_current"]), "modifiedTime": row["modified_time"], "size": len(row["content"].encode("utf-8"))}
        if tool == "google_drive.files.download":
            row = self._one("SELECT * FROM drive_files WHERE file_id = ? AND tenant_code = ?", (a["fileId"], code))
            return {"id": row["file_id"], "name": row["name"], "mimeType": row["mime_type"], "isCurrentAuthority": bool(row["is_current"]), "content": row["content"]}

        # ---- Sheets ----
        if tool == "google_sheets.spreadsheets.values.get":
            sheet = self._one("SELECT * FROM spreadsheets WHERE spreadsheet_id = ? AND tenant_code = ?", (a["spreadsheetId"], code))
            return {"spreadsheetId": a["spreadsheetId"], "range": a["range"], "values": sheet["ranges"].get(a["range"])}
        if tool in {"google_sheets.spreadsheets.values.update", "google_sheets.spreadsheets.values.append"}:
            self._assert_task(a)
            sheet = self._one("SELECT * FROM spreadsheets WHERE spreadsheet_id = ? AND tenant_code = ?", (a["spreadsheetId"], code))
            values = a["values"]
            if not isinstance(values, list) or not values or not all(isinstance(row, list) for row in values):
                raise ValueError("values must be a two-dimensional array")
            ranges = sheet["ranges"]
            operation = "update" if tool.endswith("update") else "append"
            if operation == "update":
                ranges[a["range"]] = values
            else:
                ranges[a["range"]] = list(ranges.get(a["range"]) or []) + values
            self.connection.execute("UPDATE spreadsheets SET ranges_json = ? WHERE spreadsheet_id = ?", (_json(ranges), a["spreadsheetId"]))
            count = self.connection.execute("SELECT COUNT(*) FROM sheet_changes WHERE task_id = ?", (a["task_id"],)).fetchone()[0]
            change_id = f"CHANGE-{a['task_id']}-{count + 1}"
            self.connection.execute("INSERT INTO sheet_changes VALUES (?, ?, ?, ?, ?, ?, ?)", (change_id, code, a["spreadsheetId"], a["task_id"], a["range"], operation, _json(values)))
            self._audit(tool, a["spreadsheetId"], a)
            return {"spreadsheetId": a["spreadsheetId"], "updatedRange": a["range"], "updatedRows": len(values), "changeId": change_id}

        # ---- Slack ----
        if tool == "slack.conversations_history":
            messages = self._all("SELECT * FROM chat_messages WHERE channel = ? AND tenant_code = ? ORDER BY posted_at", (a["channel"], code))
            posts = self._all("SELECT * FROM chat_posts WHERE channel = ? AND tenant_code = ?" + (" AND task_id = ?" if a.get("task_id") else "") + " ORDER BY post_id", (a["channel"], code, *( [a["task_id"]] if a.get("task_id") else [] )))
            return {"ok": True, "channel": a["channel"], "messages": [{"ts": row["posted_at"], "user": row["author"], "text": row["text"], "thread_ts": row["thread_id"]} for row in messages] + [{"ts": AS_OF, "user": "analyst", "text": row["text"], "review_status": row["review_status"], "task_id": row["task_id"]} for row in posts]}
        if tool == "slack.search_messages":
            needle = a["query"].lower()
            rows = self._all("SELECT * FROM chat_messages WHERE tenant_code = ? ORDER BY posted_at", (code,))
            matches = [row for row in rows if needle in row["text"].lower() or needle in row["channel"].lower()]
            return {"ok": True, "query": a["query"], "messages": {"total": len(matches), "matches": [{"channel": row["channel"], "user": row["author"], "text": row["text"], "ts": row["posted_at"]} for row in matches]}}
        if tool == "slack.chat_postMessage":
            self._assert_task(a)
            if a["review_status"] != "draft_for_review":
                raise ValueError("handoff must remain draft_for_review")
            if not str(a.get("text", "")).strip():
                raise ValueError("text is required")
            post_id = f"POST-{a['task_id']}"
            self.connection.execute("INSERT OR REPLACE INTO chat_posts VALUES (?, ?, ?, ?, ?, ?)", (post_id, code, a["channel"], a["task_id"], a["text"], a["review_status"]))
            self._audit(tool, post_id, a)
            return {"ok": True, "channel": a["channel"], "ts": AS_OF, "message": {"text": a["text"], "review_status": a["review_status"]}}
        raise ValueError(f"unimplemented tool: {tool}")

    # ------------------------------------------------------------------
    def _customer_name(self, number: str | None) -> str:
        if not number:
            return ""
        row = _row(self.connection.execute("SELECT name FROM customers WHERE customer_number = ?", (number,)).fetchone())
        return row["name"] if row else ""

    def _order_view(self, row: dict[str, Any], *, with_lines: bool) -> dict[str, Any]:
        view = {"OrderNumber": row["order_number"], "OrderKey": row["order_number"], "SourceTransactionNumber": row["source_transaction_number"], "SourceTransactionSystem": row["source_transaction_system"], "BuyingPartyNumber": row["buying_party_number"], "BuyingPartyName": row["buying_party_name"], "CustomerPONumber": row["customer_po_number"], "TransactionType": row["transaction_type"], "RequestedFulfillmentOrganizationCode": row["organization_code"], "SubmittedFlag": bool(row["submitted_flag"]), "StatusCode": row["status"], "OrderTotal": row["order_total"], "CreatedBy": row["created_by"], "CreationDate": row["created_at"], "LastUpdateDate": AS_OF if row["last_task_id"] else row["created_at"]}
        if with_lines:
            view["lines"] = row["lines"]
        else:
            view["lineCount"] = len(row["lines"])
        return view

    def _shipment_line_view(self, row: dict[str, Any]) -> dict[str, Any]:
        return {"ShipmentLine": row["shipment_line_id"], "Shipment": row["shipment"], "LineNumber": row["line_number"], "Item": row["item_number"], "RequestedQuantity": row["requested_quantity"], "ShippedQuantity": row["shipped_quantity"], "UnitPrice": row["unit_price"], "LineStatus": row["line_status"], "Comments": row["comments"]}

    def _invoice_view(self, row: dict[str, Any]) -> dict[str, Any]:
        return {"CustomerTransactionId": row["customer_transaction_id"], "TransactionNumber": row["transaction_number"], "BillToCustomerNumber": row["bill_to_customer_number"], "EnteredAmount": row["entered_amount"], "BalanceDue": row["balance_due"], "TransactionDate": row["transaction_date"], "DueDate": row["due_date"], "InvoiceStatus": row["invoice_status"]}

    def _receipt_view(self, row: dict[str, Any]) -> dict[str, Any]:
        return {"StandardReceiptId": row["standard_receipt_id"], "ReceiptNumber": row["receipt_number"], "ReceiptAmount": row["receipt_amount"], "ReceiptDate": row["receipt_date"], "CustomerAccountNumber": row["customer_account_number"], "ReceiptMethod": row["receipt_method"], "BusinessUnit": row["business_unit"], "Currency": row["currency"], "Status": row["receipt_status"], "remittanceReferences": row["remittance_references"]}

    def _po_view(self, row: dict[str, Any]) -> dict[str, Any]:
        return {"POHeaderId": row["po_id"], "OrderNumber": row["po_number"], "Supplier": row["supplier"], "SupplierNumber": row["supplier_number"], "Status": row["status"], "OrderDate": row["order_date"], "Total": row["total_amount"], "Buyer": row["buyer"]}

    def _requisition_view(self, row: dict[str, Any]) -> dict[str, Any]:
        return {"RequisitionHeaderId": row["requisition_id"], "Requisition": row["requisition_number"], "RequisitioningBU": row["requisitioning_bu"], "Preparer": row["preparer"], "Description": row["description"], "Justification": row["justification"], "DocumentStatus": row["document_status"], "TotalAmount": row["total_amount"], "lines": row["lines"], "LastUpdateDate": AS_OF}

    def _ap_invoice_view(self, row: dict[str, Any]) -> dict[str, Any]:
        holds = self._all("SELECT * FROM invoice_holds WHERE invoice_id = ? ORDER BY hold_id", (row["invoice_id"],))
        return {"InvoiceId": row["invoice_id"], "InvoiceNumber": row["invoice_number"], "BusinessUnit": row["business_unit"], "Supplier": row["supplier"], "InvoiceAmount": row["invoice_amount"], "InvoiceCurrency": row["invoice_currency"], "InvoiceDate": row["invoice_date"], "ValidationStatus": row["validation_status"], "invoiceLines": row["lines"], "invoiceHolds": [{"HoldId": hold["hold_id"], "HoldName": hold["hold_name"], "HoldReason": hold["hold_reason"], "HoldStatus": hold["hold_status"]} for hold in holds], "LastUpdateDate": AS_OF}

    def _worker_view(self, row: dict[str, Any]) -> dict[str, Any]:
        return {"PersonNumber": row["person_number"], "DisplayName": row["display_name"], "LegalEmployerName": row["legal_employer_name"], "JobCode": row["job_code"], "HireDate": row["hire_date"], "ContractEndDate": row["contract_end_date"], "MonthlySalary": row["monthly_salary"], "WorkerStatus": row["worker_status"], "CandidateId": row["candidate_id"]}

    def _document_view(self, row: dict[str, Any]) -> dict[str, Any]:
        return {"DocumentRecordId": row["document_record_id"], "PersonNumber": row["person_number"], "DocumentType": row["document_type"], "DateTo": row["date_to"], "Status": row["status"], "VerifiedFlag": bool(row["verified_flag"]), "MandatoryCheckOutcome": row["check_outcome"], "CheckPending": bool(row["check_pending"]), "LegalEmployerName": row["legal_employer_name"]}

    def _absence_view(self, row: dict[str, Any]) -> dict[str, Any]:
        return {"absenceId": row["absence_id"], "personNumber": row["person_number"], "absenceType": row["absence_type"], "startDate": row["start_date"], "endDate": row["end_date"], "employer": row["employer"], "absenceStatusCd": row["absence_status"]}
