-- ERPBench-100 task-local ERP world. One SQLite file per task episode.
-- Every ERP row carries the Nario-shaped lineage columns (tenant_code,
-- created_by, source_message_id, created_at, last_task_id) so a verifier can
-- trace each record to the request that produced it.

CREATE TABLE tenants (
    code TEXT PRIMARY KEY,
    company TEXT NOT NULL,
    org TEXT NOT NULL,
    business_unit TEXT NOT NULL,
    currency TEXT NOT NULL,
    country TEXT NOT NULL,
    profile TEXT NOT NULL,
    as_of TEXT NOT NULL
);

CREATE TABLE users (
    user_id TEXT PRIMARY KEY,
    tenant_code TEXT NOT NULL,
    name TEXT NOT NULL,
    role TEXT NOT NULL,
    email TEXT NOT NULL,
    approval_limit REAL NOT NULL
);

CREATE TABLE items (
    item_id INTEGER PRIMARY KEY,
    tenant_code TEXT NOT NULL,
    item_number TEXT NOT NULL,
    description TEXT NOT NULL,
    organization_code TEXT NOT NULL,
    primary_uom TEXT NOT NULL,
    list_price REAL NOT NULL,
    unit_cost REAL NOT NULL,
    item_status TEXT NOT NULL,
    price_effective_date TEXT NOT NULL,
    last_task_id TEXT
);

CREATE TABLE customers (
    customer_number TEXT PRIMARY KEY,
    tenant_code TEXT NOT NULL,
    name TEXT NOT NULL,
    credit_limit REAL NOT NULL,
    credit_hold INTEGER NOT NULL,
    payment_terms TEXT NOT NULL,
    created_by TEXT NOT NULL,
    source_message_id TEXT
);

CREATE TABLE suppliers (
    supplier_number TEXT PRIMARY KEY,
    tenant_code TEXT NOT NULL,
    name TEXT NOT NULL,
    lead_time_days INTEGER NOT NULL,
    expedite_premium_pct REAL NOT NULL,
    supplier_status TEXT NOT NULL
);

CREATE TABLE sales_orders (
    order_number TEXT PRIMARY KEY,
    tenant_code TEXT NOT NULL,
    source_transaction_number TEXT NOT NULL,
    source_transaction_system TEXT NOT NULL,
    buying_party_number TEXT,
    buying_party_name TEXT NOT NULL,
    customer_po_number TEXT NOT NULL,
    transaction_type TEXT NOT NULL,
    organization_code TEXT NOT NULL,
    submitted_flag INTEGER NOT NULL,
    status TEXT NOT NULL,
    order_total REAL NOT NULL,
    lines_json TEXT NOT NULL,
    created_by TEXT NOT NULL,
    source_message_id TEXT,
    created_at TEXT NOT NULL,
    last_task_id TEXT
);

CREATE TABLE shipments (
    shipment TEXT PRIMARY KEY,
    tenant_code TEXT NOT NULL,
    order_number TEXT NOT NULL,
    shipment_status TEXT NOT NULL,
    organization_code TEXT NOT NULL,
    ship_to_customer TEXT NOT NULL,
    planned_ship_date TEXT NOT NULL
);

CREATE TABLE shipment_lines (
    shipment_line_id INTEGER PRIMARY KEY,
    tenant_code TEXT NOT NULL,
    shipment TEXT NOT NULL,
    line_number INTEGER NOT NULL,
    item_number TEXT NOT NULL,
    requested_quantity INTEGER NOT NULL,
    shipped_quantity INTEGER NOT NULL,
    unit_price REAL NOT NULL,
    line_status TEXT NOT NULL,
    comments TEXT,
    last_task_id TEXT
);

CREATE TABLE receivables_invoices (
    customer_transaction_id INTEGER PRIMARY KEY,
    tenant_code TEXT NOT NULL,
    transaction_number TEXT NOT NULL,
    bill_to_customer_number TEXT NOT NULL,
    entered_amount REAL NOT NULL,
    balance_due REAL NOT NULL,
    transaction_date TEXT NOT NULL,
    due_date TEXT NOT NULL,
    invoice_status TEXT NOT NULL,
    last_task_id TEXT
);

CREATE TABLE standard_receipts (
    standard_receipt_id INTEGER PRIMARY KEY,
    tenant_code TEXT NOT NULL,
    receipt_number TEXT NOT NULL,
    receipt_amount REAL NOT NULL,
    receipt_date TEXT NOT NULL,
    customer_account_number TEXT NOT NULL,
    receipt_method TEXT NOT NULL,
    business_unit TEXT NOT NULL,
    currency TEXT NOT NULL,
    receipt_status TEXT NOT NULL,
    remittance_references_json TEXT NOT NULL,
    created_by TEXT NOT NULL,
    last_task_id TEXT
);

CREATE TABLE onhand_balances (
    balance_id INTEGER PRIMARY KEY,
    tenant_code TEXT NOT NULL,
    organization_code TEXT NOT NULL,
    item_number TEXT NOT NULL,
    subinventory TEXT NOT NULL,
    onhand_quantity INTEGER NOT NULL,
    reserved_quantity INTEGER NOT NULL
);

CREATE TABLE purchase_orders (
    po_number TEXT PRIMARY KEY,
    po_id INTEGER NOT NULL,
    tenant_code TEXT NOT NULL,
    supplier TEXT NOT NULL,
    supplier_number TEXT NOT NULL,
    status TEXT NOT NULL,
    order_date TEXT NOT NULL,
    total_amount REAL NOT NULL,
    buyer TEXT NOT NULL
);

CREATE TABLE purchase_order_lines (
    po_line_id INTEGER PRIMARY KEY,
    tenant_code TEXT NOT NULL,
    po_number TEXT NOT NULL,
    line_number INTEGER NOT NULL,
    item_number TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price REAL NOT NULL,
    received_quantity INTEGER NOT NULL,
    promised_date TEXT NOT NULL,
    last_task_id TEXT
);

CREATE TABLE purchase_requisitions (
    requisition_number TEXT PRIMARY KEY,
    requisition_id INTEGER NOT NULL,
    tenant_code TEXT NOT NULL,
    requisitioning_bu TEXT NOT NULL,
    preparer TEXT NOT NULL,
    description TEXT NOT NULL,
    justification TEXT NOT NULL,
    document_status TEXT NOT NULL,
    lines_json TEXT NOT NULL,
    total_amount REAL NOT NULL,
    created_by TEXT NOT NULL,
    last_task_id TEXT
);

CREATE TABLE receiving_receipt_requests (
    header_interface_id INTEGER PRIMARY KEY,
    tenant_code TEXT NOT NULL,
    receipt_source_code TEXT NOT NULL,
    organization_code TEXT NOT NULL,
    vendor_name TEXT NOT NULL,
    lines_json TEXT NOT NULL,
    processing_status TEXT NOT NULL,
    created_by TEXT NOT NULL,
    last_task_id TEXT
);

CREATE TABLE ap_invoices (
    invoice_id INTEGER PRIMARY KEY,
    tenant_code TEXT NOT NULL,
    invoice_number TEXT NOT NULL,
    business_unit TEXT NOT NULL,
    supplier TEXT NOT NULL,
    invoice_amount REAL NOT NULL,
    invoice_currency TEXT NOT NULL,
    invoice_date TEXT NOT NULL,
    validation_status TEXT NOT NULL,
    lines_json TEXT NOT NULL,
    created_by TEXT NOT NULL,
    last_task_id TEXT
);

CREATE TABLE invoice_holds (
    hold_id INTEGER PRIMARY KEY,
    tenant_code TEXT NOT NULL,
    invoice_id INTEGER NOT NULL,
    hold_name TEXT NOT NULL,
    hold_reason TEXT NOT NULL,
    hold_status TEXT NOT NULL,
    last_task_id TEXT
);

CREATE TABLE workers (
    person_number TEXT PRIMARY KEY,
    tenant_code TEXT NOT NULL,
    display_name TEXT NOT NULL,
    legal_employer_name TEXT NOT NULL,
    job_code TEXT NOT NULL,
    hire_date TEXT NOT NULL,
    contract_end_date TEXT,
    monthly_salary REAL,
    worker_status TEXT NOT NULL,
    candidate_id TEXT,
    created_by TEXT NOT NULL,
    last_task_id TEXT
);

CREATE TABLE document_records (
    document_record_id INTEGER PRIMARY KEY,
    tenant_code TEXT NOT NULL,
    person_number TEXT NOT NULL,
    document_type TEXT NOT NULL,
    date_to TEXT NOT NULL,
    status TEXT NOT NULL,
    verified_flag INTEGER NOT NULL,
    check_outcome TEXT NOT NULL,
    check_pending INTEGER NOT NULL,
    legal_employer_name TEXT NOT NULL,
    last_task_id TEXT
);

CREATE TABLE absences (
    absence_id INTEGER PRIMARY KEY,
    tenant_code TEXT NOT NULL,
    person_number TEXT NOT NULL,
    absence_type TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    employer TEXT NOT NULL,
    absence_status TEXT NOT NULL,
    created_by TEXT NOT NULL,
    last_task_id TEXT
);

CREATE TABLE channel_orders (
    row_id INTEGER PRIMARY KEY,
    tenant_code TEXT NOT NULL,
    channel TEXT NOT NULL,
    channel_order_id TEXT NOT NULL,
    buyer TEXT NOT NULL,
    order_total REAL NOT NULL,
    synced_order_number TEXT
);

CREATE TABLE mail_messages (
    message_id TEXT PRIMARY KEY,
    tenant_code TEXT NOT NULL,
    subject TEXT NOT NULL,
    sender TEXT NOT NULL,
    recipients_json TEXT NOT NULL,
    body TEXT NOT NULL,
    sent_at TEXT NOT NULL,
    task_id TEXT
);

CREATE TABLE mail_drafts (
    draft_id TEXT PRIMARY KEY,
    tenant_code TEXT NOT NULL,
    task_id TEXT NOT NULL,
    recipient TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    review_status TEXT NOT NULL
);

CREATE TABLE drive_files (
    file_id TEXT PRIMARY KEY,
    tenant_code TEXT NOT NULL,
    name TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    logical_name TEXT NOT NULL,
    version INTEGER NOT NULL,
    is_current INTEGER NOT NULL,
    content TEXT NOT NULL,
    modified_time TEXT NOT NULL
);

CREATE TABLE spreadsheets (
    spreadsheet_id TEXT PRIMARY KEY,
    tenant_code TEXT NOT NULL,
    title TEXT NOT NULL,
    ranges_json TEXT NOT NULL
);

CREATE TABLE sheet_changes (
    change_id TEXT PRIMARY KEY,
    tenant_code TEXT NOT NULL,
    spreadsheet_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    cell_range TEXT NOT NULL,
    operation TEXT NOT NULL,
    values_json TEXT NOT NULL
);

CREATE TABLE chat_messages (
    message_id TEXT PRIMARY KEY,
    tenant_code TEXT NOT NULL,
    channel TEXT NOT NULL,
    thread_id TEXT NOT NULL,
    author TEXT NOT NULL,
    text TEXT NOT NULL,
    posted_at TEXT NOT NULL,
    task_id TEXT
);

CREATE TABLE chat_posts (
    post_id TEXT PRIMARY KEY,
    tenant_code TEXT NOT NULL,
    channel TEXT NOT NULL,
    task_id TEXT NOT NULL,
    text TEXT NOT NULL,
    review_status TEXT NOT NULL
);

CREATE TABLE decisions (
    decision_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    decision TEXT NOT NULL,
    status TEXT NOT NULL,
    primary_record TEXT NOT NULL,
    rationale TEXT NOT NULL,
    source_refs_json TEXT NOT NULL
);

CREATE TABLE submissions (
    task_id TEXT PRIMARY KEY,
    answers_json TEXT NOT NULL
);

CREATE TABLE audit_log (
    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT,
    tool TEXT NOT NULL,
    target TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
