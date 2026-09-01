"""Synthetic ERP tenants and task contracts for ERPBench-100.

Every tenant, person, customer, supplier, item, quantity, amount, document and
message in this module is synthetic. The workflow families are grounded in the
production ERP archetypes observed through Nario's dataflywheel traces (order
import, shipment verification, unpaid-invoice reconciliation, reorder
monitoring, procure-to-pay, document expiry, work-report rollups, channel-order
sync, recruitment quotas, and effective-dated record supersession); only the
structure of that work is reused, never any customer value.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from functools import lru_cache
from typing import Any

BENCHMARK_NAME = "ERPBench-100"
BENCHMARK_VERSION = "1.0.0"
WORLD_ID = "fusion-erp-tenants-v1"
METRIC = "ERPScore"
AS_OF_DATE = date(2026, 2, 9)
AS_OF = "2026-02-09T09:00:00Z"
DOCUMENT_ALERT_WINDOW_DAYS = 30


def _d(value: Any) -> Decimal:
    return Decimal(str(value))


def _q(value: Decimal | float | int, places: str = "0.01") -> float:
    return float(_d(value).quantize(Decimal(places), rounding=ROUND_HALF_UP))


def _iso(days_from_as_of: int) -> str:
    return (AS_OF_DATE + timedelta(days=days_from_as_of)).isoformat()


# ---------------------------------------------------------------------------
# Tenants
# ---------------------------------------------------------------------------
# items: (item_number, description, list_price, unit_cost); the sixth item is
# inactive/discontinued in every tenant and must never be sold or reordered.
# orders.lines: (item_index, quantity); previously_imported: line indexes that
# an earlier partial import already created for the same customer PO.
# shipping.lines: (item_index, requested, picked, shipped).
# receivables.invoices: (number, amount, days_past_due — negative = not yet due).
# inventory.skus: (item_index, on_hand, reserved, reorder_point, max_level, open_po_qty).
# payables.lines: (item_index, ordered, po_price, received, invoiced_qty, invoice_price).
# documents.workers: (person, document_type, days_to_expiry, alerted, mandatory_check_outcome, check_pending).
# time.reports: (staff_code, submitted_at HH:MM, minutes_over_shift).
# channel.orders: (channel_order_id, buyer, total, already_synced, duplicate_row).
# hiring.candidates: (name, permit_days_to_expiry, checks_passed).
# pricing.lines: (item_number, new_price, effective_days_from_as_of).

WORLDS: tuple[dict[str, Any], ...] = (
    {
        "code": "NORTHBRIDGE", "short": "NBR", "company": "Northbridge Fastener Works", "industry": "Industrial fasteners",
        "profile": "discrete manufacturer", "country": "US", "currency": "USD", "org": "NBR1", "site": "Toledo plant",
        "bu": "Northbridge Manufacturing", "channel": "Shopify", "domain": "northbridge-sim.example", "quarter": "Q2",
        "people": {"requester": "Dana Whitfield", "ops_lead": "Marcus Lee", "finance_lead": "Priya Natarajan", "hr_lead": "Elena Voss", "supervisor": "Tom Okafor"},
        "customer": {"number": "CUST-10412", "name": "Cascade Assembly Inc.", "credit_limit": 180000.0, "credit_hold": False, "po": "CA-PO-77310"},
        "supplier": {"number": "SUP-2201", "name": "Ridgeway Metals", "lead_time_days": 9},
        "expedite_supplier": {"number": "SUP-2377", "name": "Quickbolt Distribution", "lead_time_days": 4, "premium_pct": 12.0},
        "items": [("FST-M8-40", "M8 x 40 hex bolt, zinc", 0.84, 0.58), ("FST-M10-60", "M10 x 60 hex bolt, zinc", 1.32, 0.91), ("NUT-M8-NYL", "M8 nylon lock nut", 0.19, 0.11), ("WSH-M10-SS", "M10 flat washer, stainless", 0.11, 0.06), ("ANC-12-100", "12 x 100 wedge anchor", 2.45, 1.72), ("FST-M6-20-OLD", "M6 x 20 hex bolt (discontinued)", 0.52, 0.40)],
        "orders": {"lines": [(0, 1200), (1, 800), (2, 640), (3, 300), (0, 450), (4, 220), (5, 150), (2, 500)], "previously_imported": [4, 7], "sheet_price_drift": 0.06},
        "shipping": {"shipment": "SHP-NBR-4471", "order": "SO-NBR-30916", "lines": [(0, 600, 600, 600), (1, 400, 380, 400), (2, 320, 320, 320), (3, 150, 150, 150), (4, 110, 116, 110), (2, 200, 200, 200)]},
        "receivables": {"invoices": [("INV-NBR-51120", 18400.00, 34), ("INV-NBR-51188", 9650.00, 21), ("INV-NBR-51231", 22780.00, 9), ("INV-NBR-51302", 14300.00, -6), ("INV-NBR-51377", 7920.00, -18)], "receipt": {"number": "RCPT-NBR-8817", "covers": [0, 2], "date": "2026-02-06", "method": "Wire"}, "hold_threshold_pct": 25.0},
        "inventory": {"need_days": 10, "skus": [(0, 3200, 900, 2600, 6000, 0), (1, 1500, 200, 1800, 4000, 600), (2, 900, 350, 1200, 3000, 0), (3, 2100, 100, 1500, 3500, 0), (4, 260, 90, 300, 900, 0), (5, 40, 0, 0, 0, 0)]},
        "payables": {"po": "PO-NBR-88120", "invoice": "RM-INV-55021", "tolerance_pct": 2.0, "lines": [(0, 5000, 0.58, 5000, 5000, 0.58), (1, 3000, 0.91, 3000, 3000, 0.97), (2, 2000, 0.11, 1800, 1800, 0.11), (3, 1500, 0.06, 1500, 1500, 0.06)]},
        "documents": {"workers": [("Mateo Reyes", "Forklift licence", 12, False, "pass", False), ("Lin Hui-Ying", "Work permit", 27, True, "pass", False), ("Kofi Mensah", "Safety induction", 45, False, "pass", False), ("Ana Sousa", "Work permit", 8, False, "fail", False), ("Jonas Berg", "Medical certificate", 19, False, "pass", True), ("Ravi Menon", "Forklift licence", 120, False, "pass", False), ("Sofia Marin", "Work permit", 26, False, "pass", True), ("Ethan Cole", "Safety induction", 3, True, "pass", False)]},
        "time": {"shift_date": "2026-02-08", "shift": "Night", "cutoff": "07:15", "expected": 12, "approved_absences": 1, "reports": [("NB-101", "07:02", 0), ("NB-102", "07:09", 30), ("NB-103", "07:31", 0), ("NB-104", "07:05", 45), ("NB-105", "07:11", 0), ("NB-106", "07:44", 15), ("NB-107", "07:00", 0), ("NB-108", "07:06", 0), ("NB-109", "07:12", 60)]},
        "channel_sync": {"orders": [("SHP-90211", "Riverbend Hardware", 1840.50, True, False), ("SHP-90212", "Oakline Builders", 2310.00, False, False), ("SHP-90213", "Summit DIY", 655.20, True, False), ("SHP-90214", "Harlow Contracting", 3120.75, False, False), ("SHP-90214", "Harlow Contracting", 3120.75, False, True), ("SHP-90215", "Pinecrest Supply", 980.00, False, False), ("SHP-90216", "Delta Fixings", 1475.30, True, False)], "new_customer": {"name": "Oakline Builders", "email": "orders@oakline-sim.example", "tax_id": "TX-88-402911"}},
        "hiring": {"job": "machine operator", "approved": 7, "current": 4, "wage": 3450.0, "months": 24, "candidates": [("Luis Ortega", 900, True), ("Mei Chen", 400, True), ("Samir Haddad", 1100, False), ("Grace Adeyemi", 950, True), ("Viktor Novak", 1400, True), ("Hana Sato", 620, True)]},
        "pricing": {"batch": "PRICE-BATCH-NBR-2026Q2", "max_change_pct": 15.0, "lines": [("FST-M8-40", 0.89, 20), ("FST-M10-60", 1.38, 20), ("NUT-M8-NYL", 0.26, 20), ("WSH-M10-SS", 0.12, -12), ("ANC-12-100", 2.55, 20), ("FST-M8-40", 0.92, 50), ("FST-M12-80", 2.10, 20), ("FST-M6-20-OLD", 0.55, 20)]},
    },
    {
        "code": "HARBORLINE", "short": "HBL", "company": "Harborline Trading Co.", "industry": "Food import and export",
        "profile": "trading company", "country": "TW", "currency": "USD", "org": "HBL1", "site": "Kaohsiung warehouse",
        "bu": "Harborline Distribution", "channel": "CyberBiz", "domain": "harborline-sim.example", "quarter": "Q2",
        "people": {"requester": "Chen Yu-Ting", "ops_lead": "Wang Po-Wei", "finance_lead": "Lin Shu-Fen", "hr_lead": "Huang Mei-Ling", "supervisor": "Liu Cheng"},
        "customer": {"number": "CUST-20077", "name": "Pacific Grocers Ltd.", "credit_limit": 95000.0, "credit_hold": True, "po": "PG-2026-0442"},
        "supplier": {"number": "SUP-3104", "name": "Formosa Leaf Estates", "lead_time_days": 14},
        "expedite_supplier": {"number": "SUP-3190", "name": "Island Air Freight Foods", "lead_time_days": 5, "premium_pct": 18.0},
        "items": [("TEA-OOL-500", "Oolong tea 500 g tin", 14.50, 9.20), ("RICE-JAS-5K", "Jasmine rice 5 kg", 11.80, 7.90), ("SOY-PRM-1L", "Premium soy sauce 1 L", 6.40, 3.90), ("NDL-DRY-1K", "Dried noodles 1 kg", 4.90, 3.10), ("CHL-OIL-250", "Chili oil 250 ml", 5.60, 3.40), ("MCH-GIFT-OLD", "Mochi gift box (retired)", 12.00, 8.00)],
        "orders": {"lines": [(0, 240), (1, 600), (2, 360), (3, 800), (4, 300), (1, 150), (5, 40), (0, 120), (3, 200)], "previously_imported": [5], "sheet_price_drift": -0.04},
        "shipping": {"shipment": "SHP-HBL-2210", "order": "SO-HBL-41022", "lines": [(0, 200, 200, 200), (1, 500, 500, 500), (2, 300, 288, 300), (3, 600, 600, 600), (4, 250, 250, 250)]},
        "receivables": {"invoices": [("INV-HBL-70311", 26400.00, 41), ("INV-HBL-70358", 12850.00, 27), ("INV-HBL-70402", 8300.00, 12), ("INV-HBL-70455", 15700.00, 4), ("INV-HBL-70491", 6100.00, -9), ("INV-HBL-70530", 9900.00, -21)], "receipt": {"number": "RCPT-HBL-3319", "covers": [1, 2], "date": "2026-02-05", "method": "Bank transfer"}, "hold_threshold_pct": 25.0},
        "inventory": {"need_days": 12, "skus": [(0, 420, 180, 300, 900, 0), (1, 1300, 100, 1500, 4000, 800), (2, 900, 200, 600, 1800, 0), (3, 2600, 400, 2000, 5000, 0), (4, 180, 60, 250, 700, 0), (5, 15, 0, 0, 0, 0)]},
        "payables": {"po": "PO-HBL-51877", "invoice": "FLE-INV-2026-118", "tolerance_pct": 1.5, "lines": [(0, 800, 9.20, 800, 800, 9.20), (1, 1200, 7.90, 1200, 1200, 7.90), (2, 600, 3.90, 600, 600, 3.90), (4, 400, 3.40, 360, 360, 3.40)]},
        "documents": {"workers": [("Nguyen Thi Hoa", "Work permit", 22, False, "pass", False), ("Budi Santoso", "Health check", 9, False, "pass", True), ("Maria Dela Cruz", "Work permit", 61, False, "pass", False), ("Tran Van Long", "Forklift licence", 15, True, "pass", False), ("Siti Rahayu", "Work permit", 28, False, "fail", False), ("Chen Wei", "Safety induction", 200, False, "pass", False), ("Dewi Lestari", "Health check", 5, False, "pass", True)]},
        "time": {"shift_date": "2026-02-08", "shift": "Day", "cutoff": "18:10", "expected": 10, "approved_absences": 2, "reports": [("HB-201", "18:01", 0), ("HB-202", "18:22", 20), ("HB-203", "18:05", 0), ("HB-204", "18:08", 0), ("HB-205", "18:31", 40), ("HB-206", "18:02", 0), ("HB-207", "18:09", 25)]},
        "channel_sync": {"orders": [("CB-55801", "Lotus Mart", 1275.00, True, False), ("CB-55802", "Jade Pantry", 2140.40, False, False), ("CB-55803", "Sunrise Foods", 860.20, False, False), ("CB-55803", "Sunrise Foods", 860.20, False, True), ("CB-55804", "Harmony Grocers", 3320.00, True, False), ("CB-55805", "Bamboo Kitchen", 1910.75, False, False), ("CB-55806", "Golden Bowl", 540.00, True, False), ("CB-55807", "Orchid Deli", 2275.50, False, False)], "new_customer": {"name": "Jade Pantry", "email": "buying@jadepantry-sim.example", "tax_id": "TW-24-771093"}},
        "hiring": {"job": "warehouse picker", "approved": 5, "current": 2, "wage": 1620.0, "months": 12, "candidates": [("Rina Wulandari", 300, True), ("Joko Prasetyo", 250, True), ("Ahmad Fauzi", 700, True), ("Putri Ayu", 500, False), ("Le Van Minh", 900, True)]},
        "pricing": {"batch": "PRICE-BATCH-HBL-2026Q2", "max_change_pct": 12.0, "lines": [("TEA-OOL-500", 15.20, 15), ("RICE-JAS-5K", 12.10, 15), ("SOY-PRM-1L", 7.60, 15), ("NDL-DRY-1K", 5.10, -3), ("CHL-OIL-250", 5.90, 15), ("CHL-OIL-250", 6.10, 45), ("RICE-BAS-5K", 13.40, 15), ("MCH-GIFT-OLD", 12.50, 15), ("TEA-OOL-500", 15.60, 60)]},
    },
    {
        "code": "MERIDIAN", "short": "MSS", "company": "Meridian Staffing Services", "industry": "Workforce placement",
        "profile": "staffing and placement agency", "country": "TW", "currency": "USD", "org": "MSS1", "site": "Taipei head office",
        "bu": "Meridian Placement Services", "channel": "Agency portal", "domain": "meridian-sim.example", "quarter": "Q2",
        "people": {"requester": "Hsu Chia-Hao", "ops_lead": "Kao Li-Wen", "finance_lead": "Cheng Yi-Ru", "hr_lead": "Tsai Ming-Hui", "supervisor": "Yang Jun"},
        "customer": {"number": "CUST-30155", "name": "Everfield Electronics", "credit_limit": 120000.0, "credit_hold": False, "po": "EF-LAB-2026-07"},
        "supplier": {"number": "SUP-4402", "name": "Nusantara Sending Agency", "lead_time_days": 21},
        "expedite_supplier": {"number": "SUP-4419", "name": "Manila Direct Placement", "lead_time_days": 9, "premium_pct": 15.0},
        "items": [("SVC-FACT-OP", "Factory operator placement", 1180.00, 790.00), ("SVC-CARE-LIVEIN", "Live-in caregiver placement", 1450.00, 980.00), ("SVC-CONSTR", "Construction worker placement", 1260.00, 845.00), ("SVC-DOM-HELP", "Domestic helper placement", 1120.00, 760.00), ("SVC-RENEW", "Contract renewal service", 380.00, 210.00), ("SVC-TRAIN-OLD", "Pre-departure training (retired)", 260.00, 150.00)],
        "orders": {"lines": [(0, 12), (2, 6), (1, 4), (4, 9), (0, 5), (3, 3), (5, 2), (2, 4)], "previously_imported": [4], "sheet_price_drift": 0.05},
        "shipping": {"shipment": "SHP-MSS-1180", "order": "SO-MSS-22019", "lines": [(0, 12, 12, 12), (2, 6, 5, 6), (1, 4, 4, 4), (4, 9, 9, 9), (3, 3, 4, 3)]},
        "receivables": {"invoices": [("INV-MSS-40211", 33600.00, 52), ("INV-MSS-40260", 14200.00, 30), ("INV-MSS-40307", 9800.00, 16), ("INV-MSS-40352", 21400.00, 2), ("INV-MSS-40398", 11600.00, -11)], "receipt": {"number": "RCPT-MSS-5502", "covers": [1, 2], "date": "2026-02-07", "method": "Cheque"}, "hold_threshold_pct": 30.0},
        "inventory": {"need_days": 15, "skus": [(0, 18, 6, 15, 40, 0), (1, 9, 3, 8, 20, 4), (2, 5, 2, 6, 16, 0), (3, 11, 1, 8, 18, 0), (4, 30, 4, 20, 50, 0), (5, 2, 0, 0, 0, 0)]},
        "payables": {"po": "PO-MSS-30455", "invoice": "NSA-INV-0931", "tolerance_pct": 2.0, "lines": [(0, 10, 790.00, 10, 10, 790.00), (1, 4, 980.00, 4, 4, 1040.00), (2, 6, 845.00, 5, 5, 845.00)]},
        "documents": {"workers": [("Arif Hidayat", "Work permit", 18, False, "pass", False), ("Lorna Bautista", "Medical certificate", 25, False, "pass", True), ("Ketut Sudiarta", "Work permit", 4, True, "pass", False), ("Thi Mai Phuong", "Residence card", 29, False, "fail", False), ("Wayan Suarta", "Work permit", 75, False, "pass", False), ("Rosa Villanueva", "Medical certificate", 11, False, "pass", False), ("Agus Salim", "Residence card", 30, False, "pass", True), ("Bayu Nugroho", "Work permit", 2, False, "fail", False), ("Ngo Thi Lan", "Safety induction", 150, True, "pass", False)]},
        "time": {"shift_date": "2026-02-08", "shift": "Day", "cutoff": "17:30", "expected": 15, "approved_absences": 2, "reports": [("MS-301", "17:12", 0), ("MS-302", "17:35", 0), ("MS-303", "17:20", 90), ("MS-304", "17:25", 0), ("MS-305", "17:41", 30), ("MS-306", "17:10", 0), ("MS-307", "17:15", 0), ("MS-308", "17:29", 0), ("MS-309", "17:33", 60), ("MS-310", "17:02", 0), ("MS-311", "17:26", 0)]},
        "channel_sync": {"orders": [("AP-7101", "Taoyuan Precision", 5900.00, True, False), ("AP-7102", "Kaohsiung Care Homes", 8700.00, False, False), ("AP-7103", "Hsinchu Foundry", 3540.00, False, False), ("AP-7104", "Tainan Textiles", 2360.00, True, False), ("AP-7103", "Hsinchu Foundry", 3540.00, False, True), ("AP-7105", "Keelung Shipworks", 6300.00, False, False)], "new_customer": {"name": "Kaohsiung Care Homes", "email": "admin@kh-carehomes-sim.example", "tax_id": "TW-31-556201"}},
        "hiring": {"job": "placement coordinator", "approved": 4, "current": 1, "wage": 2180.0, "months": 12, "candidates": [("Pham Thi Thu", 800, True), ("Dian Puspita", 150, True), ("Marco Reyes", 1000, True), ("Ida Ayu", 420, True)]},
        "pricing": {"batch": "PRICE-BATCH-MSS-2026Q2", "max_change_pct": 10.0, "lines": [("SVC-FACT-OP", 1230.00, 30), ("SVC-CARE-LIVEIN", 1490.00, 30), ("SVC-CONSTR", 1420.00, 30), ("SVC-DOM-HELP", 1150.00, 30), ("SVC-RENEW", 395.00, -20), ("SVC-FACT-OP", 1260.00, 75), ("SVC-DRIVER", 1300.00, 30), ("SVC-TRAIN-OLD", 270.00, 30)]},
    },
    {
        "code": "SUNGROVE", "short": "SGF", "company": "Sungrove Foods", "industry": "Snack and beverage processing",
        "profile": "food processing plant", "country": "ID", "currency": "USD", "org": "SGF1", "site": "Malang plant",
        "bu": "Sungrove Manufacturing", "channel": "Tokopedia", "domain": "sungrove-sim.example", "quarter": "Q2",
        "people": {"requester": "Rizky Pratama", "ops_lead": "Ayu Kartika", "finance_lead": "Bambang Wijaya", "hr_lead": "Sari Dewanti", "supervisor": "Eko Susanto"},
        "customer": {"number": "CUST-40890", "name": "Nusa Retail Group", "credit_limit": 60000.0, "credit_hold": False, "po": "NRG-0209-88"},
        "supplier": {"number": "SUP-5510", "name": "Java Agro Cooperative", "lead_time_days": 7},
        "expedite_supplier": {"number": "SUP-5566", "name": "Surabaya Fresh Logistics", "lead_time_days": 3, "premium_pct": 10.0},
        "items": [("SNK-CASSAVA-200", "Cassava chips 200 g", 1.90, 1.10), ("SNK-BANANA-150", "Banana chips 150 g", 2.10, 1.25), ("SAUCE-SAMBAL-300", "Sambal 300 ml", 2.60, 1.50), ("COF-ROBUSTA-1K", "Robusta beans 1 kg", 9.80, 6.40), ("TEA-JAS-100", "Jasmine tea 100 bags", 4.20, 2.60), ("SNK-TEMPE-OLD", "Tempeh crisps (retired)", 1.70, 1.00)],
        "orders": {"lines": [(0, 2400), (1, 1800), (2, 900), (3, 300), (4, 600), (0, 1200), (5, 400), (1, 700), (2, 350), (3, 150)], "previously_imported": [5, 8], "sheet_price_drift": 0.08},
        "shipping": {"shipment": "SHP-SGF-6630", "order": "SO-SGF-51840", "lines": [(0, 2000, 2000, 2000), (1, 1500, 1500, 1500), (2, 800, 776, 800), (3, 250, 250, 250), (4, 500, 500, 500), (0, 900, 924, 900), (1, 400, 400, 400)]},
        "receivables": {"invoices": [("INV-SGF-61050", 9200.00, 38), ("INV-SGF-61102", 4750.00, 25), ("INV-SGF-61149", 6100.00, 10), ("INV-SGF-61203", 3900.00, -5), ("INV-SGF-61240", 5150.00, -17)], "receipt": {"number": "RCPT-SGF-2208", "covers": [1], "date": "2026-02-04", "method": "Bank transfer"}, "hold_threshold_pct": 25.0},
        "inventory": {"need_days": 10, "skus": [(0, 5200, 1500, 4000, 9000, 0), (1, 3100, 400, 3000, 7000, 0), (2, 1400, 300, 1200, 3000, 500), (3, 380, 120, 400, 1200, 0), (4, 900, 100, 700, 1600, 0), (5, 60, 0, 0, 0, 0)]},
        "payables": {"po": "PO-SGF-71203", "invoice": "JAC-INV-4471", "tolerance_pct": 2.5, "lines": [(0, 6000, 1.10, 6000, 6000, 1.10), (1, 4000, 1.25, 4000, 4000, 1.25), (2, 2000, 1.50, 2000, 2000, 1.50), (3, 800, 6.40, 700, 700, 6.40)]},
        "documents": {"workers": [("Dwi Handayani", "Food handler certificate", 14, False, "pass", False), ("Slamet Riyadi", "Health check", 21, False, "pass", False), ("Yuni Astuti", "Food handler certificate", 60, False, "pass", False), ("Agung Setiawan", "Forklift licence", 6, True, "pass", False), ("Ratna Sari", "Health check", 28, False, "pass", True), ("Hendra Gunawan", "Food handler certificate", 17, False, "pass", True), ("Nur Aini", "Safety induction", 240, False, "pass", False)]},
        "time": {"shift_date": "2026-02-08", "shift": "Morning", "cutoff": "15:10", "expected": 16, "approved_absences": 3, "reports": [("SG-401", "15:00", 0), ("SG-402", "15:04", 0), ("SG-403", "15:22", 35), ("SG-404", "15:07", 0), ("SG-405", "15:09", 0), ("SG-406", "15:15", 20), ("SG-407", "15:03", 0), ("SG-408", "15:08", 0), ("SG-409", "15:01", 0), ("SG-410", "15:40", 55), ("SG-411", "15:05", 0), ("SG-412", "15:06", 0)]},
        "channel_sync": {"orders": [("TK-31001", "Warung Sejahtera", 410.00, True, False), ("TK-31002", "Toko Maju Jaya", 985.50, False, False), ("TK-31003", "Minimart Bahagia", 620.00, False, False), ("TK-31004", "Kios Berkah", 275.25, True, False), ("TK-31005", "Grosir Makmur", 1540.00, False, False), ("TK-31005", "Grosir Makmur", 1540.00, False, True), ("TK-31006", "Toko Subur", 330.00, True, False), ("TK-31007", "Warung Ceria", 710.80, False, False), ("TK-31007", "Warung Ceria", 710.80, False, True)], "new_customer": {"name": "Toko Maju Jaya", "email": "order@majujaya-sim.example", "tax_id": "ID-09-330187"}},
        "hiring": {"job": "line packer", "approved": 10, "current": 6, "wage": 640.0, "months": 12, "candidates": [("Wahyu Nugraha", 500, True), ("Lilis Suryani", 200, True), ("Taufik Hidayat", 900, True), ("Mega Utami", 700, False), ("Andi Saputra", 1200, True), ("Fitri Handayani", 60, True)]},
        "pricing": {"batch": "PRICE-BATCH-SGF-2026Q2", "max_change_pct": 15.0, "lines": [("SNK-CASSAVA-200", 2.05, 10), ("SNK-BANANA-150", 2.20, 10), ("SAUCE-SAMBAL-300", 2.75, 10), ("COF-ROBUSTA-1K", 11.60, 10), ("TEA-JAS-100", 4.40, -1), ("SNK-CASSAVA-200", 2.10, 40), ("SNK-COCONUT-120", 2.30, 10), ("SNK-TEMPE-OLD", 1.80, 10), ("SNK-BANANA-150", 2.25, 70)]},
    },
    {
        "code": "KESTREL", "short": "KEA", "company": "Kestrel Electronics Assembly", "industry": "Electronics manufacturing services",
        "profile": "contract electronics manufacturer", "country": "MY", "currency": "USD", "org": "KEA1", "site": "Penang plant",
        "bu": "Kestrel Assembly", "channel": "Shopee B2B", "domain": "kestrel-sim.example", "quarter": "Q2",
        "people": {"requester": "Farah Aziz", "ops_lead": "Daniel Tan", "finance_lead": "Nurul Hassan", "hr_lead": "Vijay Kumar", "supervisor": "Lim Wei Shen"},
        "customer": {"number": "CUST-50321", "name": "Orion Devices Sdn Bhd", "credit_limit": 250000.0, "credit_hold": True, "po": "OD-PO-118834"},
        "supplier": {"number": "SUP-6601", "name": "Shenzhen Board Partners", "lead_time_days": 18},
        "expedite_supplier": {"number": "SUP-6640", "name": "Penang Component Express", "lead_time_days": 6, "premium_pct": 22.0},
        "items": [("PCB-CTRL-A7", "Controller PCB A7", 38.50, 24.20), ("HARN-12P", "12-pin wiring harness", 6.90, 4.10), ("ENC-ALU-S", "Aluminium enclosure S", 12.40, 7.80), ("PSU-24V-60", "24 V 60 W power module", 21.00, 13.60), ("SENS-TEMP-K", "Type K temperature sensor", 8.30, 5.20), ("PCB-CTRL-A5-OLD", "Controller PCB A5 (EOL)", 31.00, 20.00)],
        "orders": {"lines": [(0, 500), (1, 1200), (2, 500), (3, 300), (4, 800), (5, 100), (0, 250), (1, 400)], "previously_imported": [6], "sheet_price_drift": -0.05},
        "shipping": {"shipment": "SHP-KEA-3350", "order": "SO-KEA-60412", "lines": [(0, 400, 400, 400), (1, 1000, 970, 1000), (2, 400, 400, 400), (3, 240, 240, 240), (4, 600, 612, 600), (0, 100, 100, 100)]},
        "receivables": {"invoices": [("INV-KEA-81004", 64200.00, 47), ("INV-KEA-81061", 31800.00, 33), ("INV-KEA-81119", 18400.00, 14), ("INV-KEA-81177", 42600.00, 6), ("INV-KEA-81230", 27300.00, -8), ("INV-KEA-81288", 15900.00, -19)], "receipt": {"number": "RCPT-KEA-9921", "covers": [2, 3], "date": "2026-02-06", "method": "Wire"}, "hold_threshold_pct": 25.0},
        "inventory": {"need_days": 14, "skus": [(0, 620, 300, 500, 1400, 0), (1, 2400, 600, 2000, 5000, 400), (2, 700, 100, 800, 2000, 0), (3, 350, 120, 300, 900, 0), (4, 1500, 250, 1200, 2800, 0), (5, 30, 0, 0, 0, 0)]},
        "payables": {"po": "PO-KEA-90581", "invoice": "SBP-INV-77120", "tolerance_pct": 1.0, "lines": [(0, 1000, 24.20, 1000, 1000, 24.20), (1, 3000, 4.10, 3000, 3000, 4.30), (2, 1000, 7.80, 900, 900, 7.80), (4, 2000, 5.20, 2000, 2000, 5.24)]},
        "documents": {"workers": [("Aisyah Rahman", "Work permit", 16, False, "pass", False), ("Kumar Selvan", "ESD certification", 23, True, "pass", False), ("Wong Mei Lin", "Work permit", 90, False, "pass", False), ("Hafiz Ismail", "Safety induction", 7, False, "fail", False), ("Priya Raj", "ESD certification", 29, False, "pass", True), ("Chong Kah Wai", "Medical certificate", 13, False, "pass", True), ("Nadia Yusof", "Work permit", 1, False, "pass", False), ("Ravi Pillai", "Safety induction", 300, False, "pass", False)]},
        "time": {"shift_date": "2026-02-08", "shift": "Night", "cutoff": "07:20", "expected": 18, "approved_absences": 2, "reports": [("KE-501", "07:05", 0), ("KE-502", "07:12", 0), ("KE-503", "07:25", 50), ("KE-504", "07:08", 0), ("KE-505", "07:18", 0), ("KE-506", "07:33", 0), ("KE-507", "07:02", 0), ("KE-508", "07:16", 0), ("KE-509", "07:21", 30), ("KE-510", "07:10", 0), ("KE-511", "07:04", 0), ("KE-512", "07:07", 0), ("KE-513", "07:47", 75), ("KE-514", "07:14", 0)]},
        "channel_sync": {"orders": [("SB-44801", "Nexa Robotics", 9450.00, False, False), ("SB-44802", "Bluewave Labs", 3120.60, True, False), ("SB-44803", "Cordova Sensors", 5580.00, False, False), ("SB-44804", "Meridian Motors", 12750.00, True, False), ("SB-44803", "Cordova Sensors", 5580.00, False, True), ("SB-44805", "Altair Instruments", 2280.40, False, False), ("SB-44806", "Zenith Controls", 7660.00, True, False)], "new_customer": {"name": "Nexa Robotics", "email": "procurement@nexa-sim.example", "tax_id": "MY-77-120548"}},
        "hiring": {"job": "SMT line technician", "approved": 8, "current": 5, "wage": 1480.0, "months": 24, "candidates": [("Arun Krishnan", 1100, True), ("Siti Nabila", 500, True), ("Jason Ooi", 900, False), ("Farid Anwar", 780, True), ("Kavitha Nair", 1500, True)]},
        "pricing": {"batch": "PRICE-BATCH-KEA-2026Q2", "max_change_pct": 12.0, "lines": [("PCB-CTRL-A7", 40.90, 25), ("HARN-12P", 7.20, 25), ("ENC-ALU-S", 14.50, 25), ("PSU-24V-60", 22.40, 25), ("SENS-TEMP-K", 8.60, -7), ("PCB-CTRL-A7", 41.50, 55), ("PCB-CTRL-A8", 44.00, 25), ("PCB-CTRL-A5-OLD", 32.00, 25)]},
    },
    {
        "code": "ALDERWOOD", "short": "ALD", "company": "Alderwood Furniture", "industry": "Wood furniture manufacturing",
        "profile": "furniture manufacturer", "country": "VN", "currency": "USD", "org": "ALD1", "site": "Binh Duong factory",
        "bu": "Alderwood Production", "channel": "Wayfair", "domain": "alderwood-sim.example", "quarter": "Q2",
        "people": {"requester": "Pham Quang Huy", "ops_lead": "Nguyen Thanh Tam", "finance_lead": "Le Thi Hong", "hr_lead": "Tran Minh Chau", "supervisor": "Vo Van Duc"},
        "customer": {"number": "CUST-60244", "name": "Homestead Living Stores", "credit_limit": 140000.0, "credit_hold": False, "po": "HLS-PO-2026-031"},
        "supplier": {"number": "SUP-7702", "name": "Mekong Hardwood Mills", "lead_time_days": 12},
        "expedite_supplier": {"number": "SUP-7745", "name": "Saigon Timber Express", "lead_time_days": 5, "premium_pct": 14.0},
        "items": [("CHR-OAK-DIN", "Oak dining chair", 96.00, 58.00), ("TBL-OAK-180", "Oak dining table 180 cm", 420.00, 255.00), ("STL-BAR-75", "Bar stool 75 cm", 72.00, 44.00), ("SHF-WAL-5", "Walnut shelf 5-tier", 210.00, 128.00), ("BNCH-TEAK-120", "Teak bench 120 cm", 165.00, 99.00), ("CHR-PINE-OLD", "Pine chair (discontinued)", 54.00, 33.00)],
        "orders": {"lines": [(0, 240), (1, 60), (2, 120), (3, 45), (4, 30), (0, 80), (5, 50), (2, 40)], "previously_imported": [5, 7], "sheet_price_drift": 0.04},
        "shipping": {"shipment": "SHP-ALD-7702", "order": "SO-ALD-71033", "lines": [(0, 200, 200, 200), (1, 50, 48, 50), (2, 100, 100, 100), (3, 40, 40, 40), (4, 24, 26, 24)]},
        "receivables": {"invoices": [("INV-ALD-90020", 41200.00, 44), ("INV-ALD-90077", 18600.00, 29), ("INV-ALD-90130", 27400.00, 11), ("INV-ALD-90188", 12900.00, -4), ("INV-ALD-90241", 19800.00, -16)], "receipt": {"number": "RCPT-ALD-1177", "covers": [0], "date": "2026-02-05", "method": "Wire"}, "hold_threshold_pct": 30.0},
        "inventory": {"need_days": 10, "skus": [(0, 520, 240, 400, 1200, 0), (1, 90, 40, 80, 220, 30), (2, 310, 60, 300, 800, 0), (3, 140, 20, 100, 260, 0), (4, 75, 30, 60, 180, 0), (5, 8, 0, 0, 0, 0)]},
        "payables": {"po": "PO-ALD-20940", "invoice": "MHM-INV-3308", "tolerance_pct": 2.0, "lines": [(0, 300, 58.00, 300, 300, 58.00), (1, 60, 255.00, 60, 60, 255.00), (2, 200, 44.00, 180, 180, 44.00), (4, 40, 99.00, 40, 40, 99.00)]},
        "documents": {"workers": [("Dang Van Hung", "Woodworking safety card", 10, False, "pass", False), ("Bui Thi Ngoc", "Health check", 26, False, "pass", True), ("Hoang Van Nam", "Forklift licence", 33, False, "pass", False), ("Ly Thi Thu", "Work permit", 19, True, "pass", False), ("Do Minh Tuan", "Woodworking safety card", 24, False, "fail", False), ("Vu Thi Hanh", "Health check", 88, False, "pass", False), ("Ngo Van Phuc", "Safety induction", 15, False, "pass", True)]},
        "time": {"shift_date": "2026-02-08", "shift": "Day", "cutoff": "17:15", "expected": 20, "approved_absences": 2, "reports": [("AL-601", "17:01", 0), ("AL-602", "17:03", 0), ("AL-603", "17:18", 40), ("AL-604", "17:06", 0), ("AL-605", "17:10", 0), ("AL-606", "17:02", 0), ("AL-607", "17:26", 0), ("AL-608", "17:08", 20), ("AL-609", "17:04", 0), ("AL-610", "17:12", 0), ("AL-611", "17:09", 0), ("AL-612", "17:35", 60), ("AL-613", "17:00", 0), ("AL-614", "17:07", 0), ("AL-615", "17:11", 0), ("AL-616", "17:05", 0)]},
        "channel_sync": {"orders": [("WF-20901", "Casa Verde Interiors", 6840.00, True, False), ("WF-20902", "Northwind Homes", 3960.00, False, False), ("WF-20903", "Elm Street Design", 2520.00, False, False), ("WF-20904", "Harbor House", 5100.00, True, False), ("WF-20902", "Northwind Homes", 3960.00, False, True), ("WF-20905", "Maple & Co", 1890.00, False, False), ("WF-20906", "Fernway Rentals", 4380.00, True, False), ("WF-20907", "Loft 27", 2310.00, False, False)], "new_customer": {"name": "Northwind Homes", "email": "buyers@northwind-sim.example", "tax_id": "VN-15-908233"}},
        "hiring": {"job": "finishing technician", "approved": 6, "current": 3, "wage": 520.0, "months": 24, "candidates": [("Le Van Sang", 800, True), ("Nguyen Thi Bich", 300, True), ("Tran Quoc Bao", 1000, True), ("Pham Thi Lan", 950, True), ("Hoang Duc Anh", 700, False)]},
        "pricing": {"batch": "PRICE-BATCH-ALD-2026Q2", "max_change_pct": 10.0, "lines": [("CHR-OAK-DIN", 99.00, 15), ("TBL-OAK-180", 445.00, 15), ("STL-BAR-75", 84.00, 15), ("SHF-WAL-5", 215.00, -10), ("BNCH-TEAK-120", 172.00, 15), ("CHR-OAK-DIN", 102.00, 45), ("TBL-OAK-220", 520.00, 15), ("CHR-PINE-OLD", 56.00, 15)]},
    },
    {
        "code": "CALDERA", "short": "CLD", "company": "Caldera Packaging", "industry": "Corrugated and flexible packaging",
        "profile": "packaging converter", "country": "US", "currency": "USD", "org": "CLD1", "site": "Reno plant",
        "bu": "Caldera Converting", "channel": "Amazon Business", "domain": "caldera-sim.example", "quarter": "Q2",
        "people": {"requester": "Jordan Blake", "ops_lead": "Alicia Romero", "finance_lead": "Ben Carter", "hr_lead": "Monica Ruiz", "supervisor": "Greg Halvorsen"},
        "customer": {"number": "CUST-70510", "name": "Sierra Fulfillment LLC", "credit_limit": 200000.0, "credit_hold": False, "po": "SF-PO-51188"},
        "supplier": {"number": "SUP-8801", "name": "Cascade Paper Mills", "lead_time_days": 8},
        "expedite_supplier": {"number": "SUP-8830", "name": "Nevada Linerboard Express", "lead_time_days": 3, "premium_pct": 11.0},
        "items": [("BOX-RSC-12", "12 x 12 x 12 RSC carton", 0.92, 0.57), ("MAIL-PAD-6", "Padded mailer #6", 0.34, 0.19), ("FILM-STR-18", "Stretch film 18 in roll", 11.60, 7.40), ("TAPE-PP-48", "PP tape 48 mm x 100 m", 1.85, 1.10), ("LBL-THERM-46", "Thermal label 4 x 6 roll", 9.40, 5.90), ("BOX-RSC-10-OLD", "10 x 10 x 10 RSC (retired)", 0.78, 0.50)],
        "orders": {"lines": [(0, 8000), (1, 12000), (2, 400), (3, 2400), (4, 600), (0, 2000), (5, 1500), (1, 3000), (3, 800)], "previously_imported": [5], "sheet_price_drift": 0.07},
        "shipping": {"shipment": "SHP-CLD-9910", "order": "SO-CLD-82077", "lines": [(0, 6000, 6000, 6000), (1, 9000, 8800, 9000), (2, 300, 300, 300), (3, 2000, 2000, 2000), (4, 500, 520, 500), (1, 2000, 2000, 2000)]},
        "receivables": {"invoices": [("INV-CLD-11220", 52300.00, 36), ("INV-CLD-11276", 24800.00, 22), ("INV-CLD-11330", 17650.00, 8), ("INV-CLD-11391", 33100.00, -3), ("INV-CLD-11447", 21900.00, -14), ("INV-CLD-11502", 12400.00, -25)], "receipt": {"number": "RCPT-CLD-4402", "covers": [0, 1], "date": "2026-02-06", "method": "ACH"}, "hold_threshold_pct": 25.0},
        "inventory": {"need_days": 7, "skus": [(0, 24000, 9000, 15000, 40000, 0), (1, 30000, 4000, 25000, 60000, 6000), (2, 900, 300, 800, 2000, 0), (3, 5200, 800, 4000, 9000, 0), (4, 1100, 400, 900, 2400, 0), (5, 200, 0, 0, 0, 0)]},
        "payables": {"po": "PO-CLD-40118", "invoice": "CPM-INV-2026-0207", "tolerance_pct": 2.0, "lines": [(0, 20000, 0.57, 20000, 20000, 0.57), (1, 25000, 0.19, 25000, 25000, 0.19), (3, 6000, 1.10, 5400, 5400, 1.10), (4, 2000, 5.90, 2000, 2000, 5.90)]},
        "documents": {"workers": [("Carlos Mendoza", "Forklift licence", 20, False, "pass", False), ("Ashley Nguyen", "Safety induction", 30, True, "pass", False), ("Derek Holt", "Medical certificate", 9, False, "pass", True), ("Maya Patel", "Forklift licence", 55, False, "pass", False), ("Luis Herrera", "Work permit", 27, False, "fail", False), ("Kim Dawson", "Safety induction", 14, False, "pass", False), ("Omar Farouk", "Medical certificate", 2, False, "pass", True), ("Tina Brooks", "Forklift licence", 180, True, "pass", False)]},
        "time": {"shift_date": "2026-02-08", "shift": "Swing", "cutoff": "23:15", "expected": 14, "approved_absences": 1, "reports": [("CL-701", "23:02", 0), ("CL-702", "23:09", 0), ("CL-703", "23:20", 45), ("CL-704", "23:05", 0), ("CL-705", "23:12", 0), ("CL-706", "23:30", 0), ("CL-707", "23:01", 0), ("CL-708", "23:08", 30), ("CL-709", "23:14", 0), ("CL-710", "23:03", 0), ("CL-711", "23:16", 0)]},
        "channel_sync": {"orders": [("AB-88101", "Pacific Ecom Partners", 4120.00, False, False), ("AB-88102", "Reno Roasters", 1330.50, True, False), ("AB-88103", "Highline Apparel", 2760.00, False, False), ("AB-88104", "Truckee Provisions", 890.00, True, False), ("AB-88103", "Highline Apparel", 2760.00, False, True), ("AB-88105", "Desert Bloom Cosmetics", 3450.75, False, False), ("AB-88106", "Summit Gear", 2180.00, True, False), ("AB-88101", "Pacific Ecom Partners", 4120.00, False, True)], "new_customer": {"name": "Pacific Ecom Partners", "email": "ap@pacificecom-sim.example", "tax_id": "TX-91-664120"}},
        "hiring": {"job": "corrugator operator", "approved": 5, "current": 3, "wage": 3980.0, "months": 12, "candidates": [("Miguel Santos", 1200, True), ("Rachel Kim", 800, False), ("Andre Bell", 1500, True), ("Sonia Alvarez", 950, True)]},
        "pricing": {"batch": "PRICE-BATCH-CLD-2026Q2", "max_change_pct": 15.0, "lines": [("BOX-RSC-12", 0.98, 12), ("MAIL-PAD-6", 0.36, 12), ("FILM-STR-18", 13.60, 12), ("TAPE-PP-48", 1.95, -5), ("LBL-THERM-46", 9.90, 12), ("BOX-RSC-12", 1.02, 42), ("BOX-RSC-14", 1.15, 12), ("BOX-RSC-10-OLD", 0.80, 12), ("TAPE-PP-48", 2.00, 65)]},
    },
    {
        "code": "RIVERSTONE", "short": "RVS", "company": "Riverstone Medical Supply", "industry": "Medical consumables distribution",
        "profile": "medical distributor", "country": "SG", "currency": "USD", "org": "RVS1", "site": "Jurong distribution centre",
        "bu": "Riverstone Distribution", "channel": "Lazada", "domain": "riverstone-sim.example", "quarter": "Q2",
        "people": {"requester": "Amanda Goh", "ops_lead": "Ryan Teo", "finance_lead": "Shalini Devi", "hr_lead": "Marcus Ng", "supervisor": "Zul Hakim"},
        "customer": {"number": "CUST-80633", "name": "Harbourview Clinics", "credit_limit": 75000.0, "credit_hold": True, "po": "HVC-2026-0201"},
        "supplier": {"number": "SUP-9902", "name": "Medigrade Manufacturing", "lead_time_days": 11},
        "expedite_supplier": {"number": "SUP-9950", "name": "Changi Med Air", "lead_time_days": 4, "premium_pct": 16.0},
        "items": [("GLV-NIT-M", "Nitrile gloves M (box 100)", 8.90, 5.60), ("MSK-SURG-3", "Surgical mask level 3 (50)", 6.20, 3.70), ("SYR-5ML-100", "Syringe 5 ml (100)", 12.50, 8.10), ("GAUZE-4X4", "Gauze pad 4 x 4 (200)", 7.40, 4.60), ("THERM-IR", "Infrared thermometer", 34.00, 21.50), ("MSK-CLOTH-OLD", "Cloth mask (retired)", 2.10, 1.20)],
        "orders": {"lines": [(0, 900), (1, 1500), (2, 300), (3, 450), (4, 60), (0, 300), (5, 200), (2, 120), (1, 500)], "previously_imported": [5, 7], "sheet_price_drift": 0.05},
        "shipping": {"shipment": "SHP-RVS-5580", "order": "SO-RVS-92210", "lines": [(0, 800, 800, 800), (1, 1200, 1170, 1200), (2, 250, 250, 250), (3, 400, 400, 400), (4, 50, 52, 50), (1, 300, 300, 300)]},
        "receivables": {"invoices": [("INV-RVS-13310", 21500.00, 49), ("INV-RVS-13367", 9800.00, 31), ("INV-RVS-13421", 13400.00, 17), ("INV-RVS-13478", 7600.00, 5), ("INV-RVS-13530", 11200.00, -7)], "receipt": {"number": "RCPT-RVS-6613", "covers": [1, 3], "date": "2026-02-07", "method": "GIRO"}, "hold_threshold_pct": 25.0},
        "inventory": {"need_days": 10, "skus": [(0, 4200, 1500, 3000, 8000, 0), (1, 6100, 900, 5000, 12000, 1500), (2, 800, 250, 700, 1800, 0), (3, 1600, 300, 1200, 2800, 0), (4, 140, 60, 120, 320, 0), (5, 90, 0, 0, 0, 0)]},
        "payables": {"po": "PO-RVS-61022", "invoice": "MGM-INV-8814", "tolerance_pct": 1.5, "lines": [(0, 4000, 5.60, 4000, 4000, 5.60), (1, 6000, 3.70, 6000, 6000, 3.85), (2, 1200, 8.10, 1000, 1000, 8.10), (3, 2000, 4.60, 2000, 2000, 4.60)]},
        "documents": {"workers": [("Nurul Izzah", "Cold-chain handling certificate", 11, False, "pass", False), ("Kelvin Lim", "Forklift licence", 24, True, "pass", False), ("Deepa Menon", "Work permit", 29, False, "pass", True), ("Hafiz Rahman", "Health check", 40, False, "pass", False), ("Grace Tan", "Cold-chain handling certificate", 6, False, "fail", False), ("Arjun Das", "Safety induction", 21, False, "pass", False), ("Mei Ling Chua", "Work permit", 100, False, "pass", False), ("Siti Aminah", "Health check", 18, False, "pass", True)]},
        "time": {"shift_date": "2026-02-08", "shift": "Day", "cutoff": "18:00", "expected": 11, "approved_absences": 1, "reports": [("RV-801", "17:50", 0), ("RV-802", "17:58", 0), ("RV-803", "18:07", 25), ("RV-804", "17:55", 0), ("RV-805", "18:12", 0), ("RV-806", "17:52", 0), ("RV-807", "17:59", 0), ("RV-808", "18:03", 35)]},
        "channel_sync": {"orders": [("LZ-61001", "Bayfront Dental", 1120.00, True, False), ("LZ-61002", "Clementi Family Clinic", 2640.50, False, False), ("LZ-61003", "Woodlands Physio", 780.00, False, False), ("LZ-61004", "Tampines Eldercare", 3310.00, True, False), ("LZ-61003", "Woodlands Physio", 780.00, False, True), ("LZ-61005", "Bishan Vet Clinic", 1455.25, False, False), ("LZ-61006", "Marina Pharmacy", 920.00, True, False)], "new_customer": {"name": "Clementi Family Clinic", "email": "orders@clementifc-sim.example", "tax_id": "SG-20-441870"}},
        "hiring": {"job": "cold-chain picker", "approved": 6, "current": 4, "wage": 1750.0, "months": 12, "candidates": [("Ismail Bakar", 600, True), ("Chloe Lee", 200, True), ("Rajesh Nair", 1300, True), ("Aina Zahra", 850, True), ("Brandon Koh", 700, False)]},
        "pricing": {"batch": "PRICE-BATCH-RVS-2026Q2", "max_change_pct": 12.0, "lines": [("GLV-NIT-M", 9.30, 18), ("MSK-SURG-3", 6.40, 18), ("SYR-5ML-100", 12.90, 18), ("GAUZE-4X4", 8.50, 18), ("THERM-IR", 35.00, -2), ("GLV-NIT-M", 9.60, 48), ("GLV-NIT-L", 9.30, 18), ("MSK-CLOTH-OLD", 2.20, 18)]},
    },
    {
        "code": "BLUEFIN", "short": "BLF", "company": "Bluefin Marine Parts", "industry": "Marine spare parts distribution",
        "profile": "parts distributor", "country": "AU", "currency": "USD", "org": "BLF1", "site": "Fremantle depot",
        "bu": "Bluefin Parts", "channel": "eBay Motors", "domain": "bluefin-sim.example", "quarter": "Q2",
        "people": {"requester": "Hannah Dwyer", "ops_lead": "Callum Reid", "finance_lead": "Olivia Marsh", "hr_lead": "Jack Thornton", "supervisor": "Mia Fraser"},
        "customer": {"number": "CUST-90418", "name": "Southern Cross Boatworks", "credit_limit": 110000.0, "credit_hold": False, "po": "SCB-PO-3391"},
        "supplier": {"number": "SUP-1101", "name": "Tasman Propulsion Supply", "lead_time_days": 10},
        "expedite_supplier": {"number": "SUP-1160", "name": "Perth Marine Courier", "lead_time_days": 3, "premium_pct": 13.0},
        "items": [("IMP-WP-40", "Water pump impeller 40 mm", 28.00, 17.50), ("ANODE-ZN-2", "Zinc anode 2 kg", 19.50, 12.00), ("FILT-FUEL-10", "Fuel filter 10 micron", 16.80, 10.40), ("PROP-AL-13", "Aluminium propeller 13 in", 210.00, 135.00), ("HOSE-BILGE-25", "Bilge hose 25 mm (per metre)", 4.60, 2.90), ("IMP-WP-35-OLD", "Impeller 35 mm (superseded)", 24.00, 15.00)],
        "orders": {"lines": [(0, 120), (1, 200), (2, 180), (3, 12), (4, 400), (5, 30), (0, 60), (2, 90)], "previously_imported": [6, 7], "sheet_price_drift": -0.06},
        "shipping": {"shipment": "SHP-BLF-8801", "order": "SO-BLF-13355", "lines": [(0, 100, 100, 100), (1, 180, 176, 180), (2, 150, 150, 150), (3, 10, 10, 10), (4, 300, 310, 300), (0, 40, 40, 40)]},
        "receivables": {"invoices": [("INV-BLF-15100", 17800.00, 40), ("INV-BLF-15155", 8250.00, 26), ("INV-BLF-15210", 12600.00, 13), ("INV-BLF-15268", 6400.00, -2), ("INV-BLF-15322", 9950.00, -15)], "receipt": {"number": "RCPT-BLF-7719", "covers": [0, 1], "date": "2026-02-06", "method": "EFT"}, "hold_threshold_pct": 20.0},
        "inventory": {"need_days": 8, "skus": [(0, 260, 80, 200, 600, 0), (1, 540, 60, 500, 1200, 200), (2, 330, 120, 300, 800, 0), (3, 22, 6, 20, 60, 0), (4, 1100, 200, 800, 2000, 0), (5, 12, 0, 0, 0, 0)]},
        "payables": {"po": "PO-BLF-72315", "invoice": "TPS-INV-10442", "tolerance_pct": 2.0, "lines": [(0, 200, 17.50, 200, 200, 17.50), (1, 400, 12.00, 400, 400, 12.60), (2, 300, 10.40, 260, 260, 10.40), (3, 20, 135.00, 20, 20, 135.00)]},
        "documents": {"workers": [("Liam Foster", "Forklift licence", 25, False, "pass", False), ("Chloe Bennett", "First aid certificate", 8, False, "pass", True), ("Noah Walsh", "Work permit", 47, False, "pass", False), ("Ella Hughes", "Safety induction", 30, True, "pass", False), ("Oscar Reyes", "Forklift licence", 12, False, "fail", False), ("Zoe Campbell", "First aid certificate", 16, False, "pass", False), ("Lucas Ward", "Medical certificate", 3, False, "pass", True)]},
        "time": {"shift_date": "2026-02-08", "shift": "Day", "cutoff": "16:45", "expected": 9, "approved_absences": 1, "reports": [("BF-901", "16:30", 0), ("BF-902", "16:52", 15), ("BF-903", "16:40", 0), ("BF-904", "16:44", 0), ("BF-905", "16:58", 40), ("BF-906", "16:35", 0), ("BF-907", "16:41", 0)]},
        "channel_sync": {"orders": [("EB-70301", "Rottnest Charters", 2380.00, False, False), ("EB-70302", "Albany Fishing Co", 1140.50, True, False), ("EB-70303", "Mandurah Marine", 3210.00, False, False), ("EB-70304", "Dunsborough Divers", 675.00, True, False), ("EB-70303", "Mandurah Marine", 3210.00, False, True), ("EB-70305", "Broome Pearl Boats", 4460.25, False, False), ("EB-70306", "Esperance Tackle", 980.00, True, False)], "new_customer": {"name": "Rottnest Charters", "email": "office@rottnestcharters-sim.example", "tax_id": "AU-52-310877"}},
        "hiring": {"job": "parts interpreter", "approved": 4, "current": 2, "wage": 4650.0, "months": 12, "candidates": [("Ethan Murphy", 1400, True), ("Isla Grant", 300, True), ("Harper Ross", 900, False), ("Finn O'Neill", 1100, True)]},
        "pricing": {"batch": "PRICE-BATCH-BLF-2026Q2", "max_change_pct": 10.0, "lines": [("IMP-WP-40", 29.50, 22), ("ANODE-ZN-2", 20.40, 22), ("FILT-FUEL-10", 18.90, 22), ("PROP-AL-13", 218.00, -4), ("HOSE-BILGE-25", 4.80, 22), ("IMP-WP-40", 30.20, 52), ("IMP-WP-45", 32.00, 22), ("IMP-WP-35-OLD", 24.50, 22)]},
    },
    {
        "code": "TERRAVANE", "short": "TRV", "company": "Terravane Solar Components", "industry": "Solar module manufacturing",
        "profile": "solar component maker", "country": "TH", "currency": "USD", "org": "TRV1", "site": "Rayong plant",
        "bu": "Terravane Manufacturing", "channel": "Distributor portal", "domain": "terravane-sim.example", "quarter": "Q2",
        "people": {"requester": "Ploy Suwannarat", "ops_lead": "Nattapong Chai", "finance_lead": "Kanya Boonmee", "hr_lead": "Somchai Prasert", "supervisor": "Anong Rattana"},
        "customer": {"number": "CUST-11780", "name": "SunGrid Installers", "credit_limit": 300000.0, "credit_hold": False, "po": "SGI-PO-2026-014"},
        "supplier": {"number": "SUP-1250", "name": "Chonburi Cell Works", "lead_time_days": 16},
        "expedite_supplier": {"number": "SUP-1288", "name": "Laem Chabang Air Cargo", "lead_time_days": 5, "premium_pct": 20.0},
        "items": [("MOD-410-M", "410 W mono module", 148.00, 104.00), ("INV-5K-H", "5 kW hybrid inverter", 690.00, 470.00), ("RAIL-AL-42", "Aluminium rail 4.2 m", 18.50, 11.80), ("CLMP-MID", "Mid clamp", 1.40, 0.80), ("CABLE-PV-6", "PV cable 6 mm2 (per metre)", 1.10, 0.70), ("MOD-380-OLD", "380 W module (EOL)", 132.00, 95.00)],
        "orders": {"lines": [(0, 600), (1, 40), (2, 800), (3, 2400), (4, 3000), (5, 120), (0, 200), (2, 300), (3, 600)], "previously_imported": [6, 8], "sheet_price_drift": 0.03},
        "shipping": {"shipment": "SHP-TRV-2290", "order": "SO-TRV-14420", "lines": [(0, 500, 500, 500), (1, 30, 30, 30), (2, 700, 690, 700), (3, 2000, 2000, 2000), (4, 2500, 2540, 2500), (0, 100, 100, 100)]},
        "receivables": {"invoices": [("INV-TRV-17330", 88400.00, 43), ("INV-TRV-17388", 46200.00, 28), ("INV-TRV-17441", 31900.00, 15), ("INV-TRV-17499", 57300.00, 3), ("INV-TRV-17552", 24800.00, -10), ("INV-TRV-17610", 39600.00, -22)], "receipt": {"number": "RCPT-TRV-3320", "covers": [1, 2], "date": "2026-02-05", "method": "Wire"}, "hold_threshold_pct": 25.0},
        "inventory": {"need_days": 12, "skus": [(0, 1400, 600, 1000, 3000, 0), (1, 90, 30, 80, 200, 40), (2, 2200, 500, 2000, 5000, 0), (3, 8000, 2500, 6000, 15000, 0), (4, 9000, 1000, 7000, 16000, 0), (5, 150, 0, 0, 0, 0)]},
        "payables": {"po": "PO-TRV-83371", "invoice": "CCW-INV-2026-091", "tolerance_pct": 1.0, "lines": [(0, 2000, 104.00, 2000, 2000, 104.00), (2, 3000, 11.80, 3000, 3000, 12.10), (3, 10000, 0.80, 9000, 9000, 0.80), (4, 12000, 0.70, 12000, 12000, 0.70)]},
        "documents": {"workers": [("Somsak Jaidee", "Electrical safety licence", 13, False, "pass", False), ("Wanida Srisuk", "Work permit", 26, False, "pass", True), ("Preecha Wong", "Forklift licence", 70, False, "pass", False), ("Chanida Kaew", "Health check", 5, True, "pass", False), ("Aung Myo", "Work permit", 21, False, "fail", False), ("Thida Win", "Electrical safety licence", 30, False, "pass", False), ("Kittisak Pong", "Safety induction", 17, False, "pass", True), ("Mya Thandar", "Work permit", 9, False, "pass", False), ("Boonsri Nak", "Health check", 210, False, "pass", False)]},
        "time": {"shift_date": "2026-02-08", "shift": "Night", "cutoff": "07:10", "expected": 22, "approved_absences": 3, "reports": [("TV-1001", "06:58", 0), ("TV-1002", "07:03", 0), ("TV-1003", "07:14", 45), ("TV-1004", "07:05", 0), ("TV-1005", "07:01", 0), ("TV-1006", "07:22", 0), ("TV-1007", "07:07", 0), ("TV-1008", "07:09", 30), ("TV-1009", "07:00", 0), ("TV-1010", "07:04", 0), ("TV-1011", "07:06", 0), ("TV-1012", "07:31", 90), ("TV-1013", "07:02", 0), ("TV-1014", "07:08", 0), ("TV-1015", "07:05", 0), ("TV-1016", "07:03", 0), ("TV-1017", "07:12", 0)]},
        "channel_sync": {"orders": [("DP-12001", "Bangkok Rooftop Solar", 29600.00, True, False), ("DP-12002", "Chiang Mai Energy Co", 14800.00, False, False), ("DP-12003", "Phuket Green Homes", 7400.00, False, False), ("DP-12004", "Khon Kaen Farms Power", 22200.00, True, False), ("DP-12003", "Phuket Green Homes", 7400.00, False, True), ("DP-12005", "Pattaya Resorts Energy", 18500.00, False, False), ("DP-12006", "Hua Hin Solar", 9250.00, True, False)], "new_customer": {"name": "Chiang Mai Energy Co", "email": "purchasing@cmenergy-sim.example", "tax_id": "TH-40-227719"}},
        "hiring": {"job": "lamination technician", "approved": 9, "current": 6, "wage": 780.0, "months": 24, "candidates": [("Nattawut Kham", 1000, True), ("Suda Phong", 500, True), ("Zaw Lin", 300, True), ("Pimchanok Dee", 1200, True), ("Kyaw Htun", 900, False)]},
        "pricing": {"batch": "PRICE-BATCH-TRV-2026Q2", "max_change_pct": 8.0, "lines": [("MOD-410-M", 152.00, 20), ("INV-5K-H", 705.00, 20), ("RAIL-AL-42", 20.90, 20), ("CLMP-MID", 1.45, -6), ("CABLE-PV-6", 1.15, 20), ("MOD-410-M", 155.00, 50), ("MOD-430-M", 160.00, 20), ("MOD-380-OLD", 134.00, 20), ("CABLE-PV-6", 1.18, 80)]},
    },
)


FAMILIES: tuple[dict[str, Any], ...] = (
    {
        "key": "order_import", "label": "Customer order import", "title": "Import the customer's consolidated order",
        "archetype": "erp-management-order-import", "production_runs": 196, "verifier_kind": "row_exists+field_equals",
        "request": (
            "{customer} sent their consolidated {po} order as a spreadsheet this morning and wants it confirmed today. "
            "Get it into the system properly: check every line against what we already imported for that purchase order and "
            "against the items we still sell, price it from the current list rather than whatever the spreadsheet says, and "
            "respect the customer's credit standing before you submit anything. Log the import in the ops register and get "
            "a reply to {requester} ready for review."
        ),
    },
    {
        "key": "shipment_verification", "label": "Shipment verification", "title": "Reconcile the staged shipment before confirmation",
        "archetype": "ship-verify", "production_runs": 44, "verifier_kind": "state_transition",
        "request": (
            "Shipment {shipment} for {customer} is staged for tonight's truck, but the warehouse pick confirmation and the "
            "shipment lines in the system do not agree everywhere. Reconcile them line by line, correct what the pick "
            "confirmation proves was actually picked, hold anything that looks over-picked instead of shipping it, and "
            "confirm the value we can honestly ship. Record it in the shipping register and leave the update for "
            "{ops_lead} ready for review."
        ),
    },
    {
        "key": "receivables_collection", "label": "Receipt application and collections", "title": "Apply the customer's remittance and size the exposure",
        "archetype": "bill-query", "production_runs": 25, "verifier_kind": "row_count",
        "request": (
            "{customer} says they paid us this week and their remittance advice is in the mailbox. Match it to the open "
            "invoices, enter the receipt against exactly what it covers, and work out what is still past due afterwards and "
            "whether that puts them over our credit policy. Update the receivables register and prepare the collections note "
            "for {finance_lead} to review; do not change the customer's credit status on your own authority."
        ),
    },
    {
        "key": "inventory_reorder", "label": "Reorder monitoring and requisition", "title": "Run the reorder review and raise the requisition",
        "archetype": "inventory-query", "production_runs": 17, "verifier_kind": "row_exists",
        "request": (
            "Planning wants the reorder run for the {site} done today. Work out which items are genuinely below their "
            "reorder point once reservations and open purchase orders are counted, how much each needs to come back to its "
            "planned level, and whether {supplier} can deliver inside the {need_days}-day window or whether an expedite "
            "option is worth raising. Raise the requisition that current policy supports, log it in the register, and post "
            "the planning update for review."
        ),
    },
    {
        "key": "receiving_ap_match", "label": "Receiving and three-way match", "title": "Receive the delivery and match the supplier invoice",
        "archetype": "purchase-order-to-pay", "production_runs": 9, "verifier_kind": "row_exists+field_equals",
        "request": (
            "{supplier}'s invoice for {po} landed in accounts payable. Receive what the delivery note proves was delivered, "
            "match the invoice to the order and the receipt line by line, and settle only what passes our tolerance; "
            "anything else has to be held with a reason rather than paid. Log the match in the payables register and get "
            "the note to {finance_lead} ready for review."
        ),
    },
    {
        "key": "document_compliance", "label": "Worker document compliance", "title": "Clear the document expiry and dossier backlog",
        "archetype": "atm-management-cpmi-verify", "production_runs": 189, "verifier_kind": "state_transition",
        "request": (
            "The compliance audit is next week. Find every worker document that expires within the next thirty days that "
            "nobody has been alerted about, work out who is blocked by a failed mandatory check, clear the dossier checks "
            "that can be verified from the file, and record the alerts. Enter the outcome in the compliance log and prepare "
            "the update for {hr_lead} to review."
        ),
    },
    {
        "key": "shift_rollup", "label": "Shift work-report rollup", "title": "Roll up the shift reports and record the gaps",
        "archetype": "hourly-work-report-rollup", "production_runs": 582, "verifier_kind": "row_count",
        "request": (
            "Roll up the {shift} shift reports for {shift_date} at the {site}. {supervisor} wants to know who was expected "
            "once approved leave is taken out, who actually reported, who was late against the cutoff, how much overtime was "
            "worked, and who is simply missing. Record the missing people the way policy requires, post the rollup to the "
            "shift channel, and log it in the register for review."
        ),
    },
    {
        "key": "channel_order_sync", "label": "Channel order sync and customer capture", "title": "Sync the channel orders without duplicates",
        "archetype": "cyberbiz-order-import", "production_runs": 309, "verifier_kind": "row_absent+row_exists",
        "request": (
            "This week's {channel} export is in the shared drive and a new buyer sent their details over chat. Bring the "
            "orders that are not yet in the system across without creating duplicates, capture the new customer as a proper "
            "master record instead of a chat message, and confirm the value that was synced. Log the sync in the register "
            "and prepare the update for {ops_lead} to review."
        ),
    },
    {
        "key": "hire_against_requisition", "label": "Hiring against approved headcount", "title": "Close the hiring round within quota",
        "archetype": "atm-management-contract-generate", "production_runs": 148, "verifier_kind": "row_exists",
        "request": (
            "{hr_lead} needs the {job} hiring round closed today. Work out how many positions are actually open against the "
            "approved headcount, which candidates are eligible once work permits and background checks are considered, and "
            "hire only the people we can place under a standard contract. Register the contracts and prepare the "
            "confirmation for review."
        ),
    },
    {
        "key": "price_list_batch", "label": "Effective-dated price batch", "title": "Apply the quarterly price batch under policy",
        "archetype": "structured-fact-supersession", "production_runs": 26, "verifier_kind": "field_equals",
        "request": (
            "Pricing sent the {quarter} list-price batch for {company}. Apply only the lines that meet policy: items we "
            "actually carry, effective dates that are not already past, and changes inside the approved band, and respect a "
            "later effective date when one line supersedes an earlier one for the same item. Update the prices we accept, "
            "log accepted and rejected lines with reasons in the register, and prepare the notice for review."
        ),
    },
)


SCORING_CATEGORIES: tuple[dict[str, Any], ...] = (
    {"key": "discovery", "label": "Discovery", "weight": 15},
    {"key": "calculation", "label": "ERP calculation", "weight": 25},
    {"key": "decision", "label": "Decision", "weight": 15},
    {"key": "erp_state", "label": "Committed ERP state", "weight": 20},
    {"key": "handoff", "label": "Register and handoff", "weight": 10},
    {"key": "readback", "label": "Readback", "weight": 10},
    {"key": "containment", "label": "Containment", "weight": 5},
)


NUMERIC_FIELDS: dict[str, tuple[str, ...]] = {
    "order_import": ("accepted_lines", "rejected_lines", "imported_units", "order_total", "duplicate_lines"),
    "shipment_verification": ("lines_reviewed", "lines_matching", "lines_corrected", "units_removed", "confirmed_value"),
    "receivables_collection": ("open_invoices_before", "receipt_amount", "remaining_past_due", "oldest_days_past_due", "past_due_pct_of_limit"),
    "inventory_reorder": ("skus_below_reorder", "total_reorder_units", "requisition_amount", "supplier_lead_time_days", "days_late"),
    "receiving_ap_match": ("lines_matched", "matched_amount", "variance_amount", "held_lines", "payable_amount"),
    "document_compliance": ("expiring_within_30", "unalerted_expiring", "blocked_workers", "checks_verified", "days_to_earliest_expiry"),
    "shift_rollup": ("expected_staff", "reporting_staff", "late_reports", "overtime_hours", "missing_staff"),
    "channel_order_sync": ("channel_rows", "already_synced", "created_orders", "duplicate_rows", "synced_value"),
    "hire_against_requisition": ("open_headcount", "eligible_candidates", "hires", "monthly_wage_total", "contract_months"),
    "price_list_batch": ("batch_lines", "accepted_lines", "rejected_lines", "superseded_lines", "average_change_pct"),
}


# ---------------------------------------------------------------------------
# Derived tenant model — the single source of every number
# ---------------------------------------------------------------------------


def _hhmm(value: str) -> int:
    hours, minutes = value.split(":")
    return int(hours) * 60 + int(minutes)


@lru_cache(maxsize=None)
def _world_by_code(code: str) -> dict[str, Any]:
    for world in WORLDS:
        if world["code"] == code:
            return world
    raise KeyError(code)


@lru_cache(maxsize=None)
def world_model(code: str) -> dict[str, Any]:
    """Compute every derived record and gold outcome for one tenant."""

    world = _world_by_code(code)
    short = world["short"]
    items = [
        {"item_number": number, "description": description, "list_price": price, "unit_cost": cost, "status": "Inactive" if index == 5 else "Active", "item_id": 300000 + index * 7 + len(short)}
        for index, (number, description, price, cost) in enumerate(world["items"])
    ]
    item_by_number = {item["item_number"]: item for item in items}
    customer = world["customer"]
    supplier = world["supplier"]
    expedite = world["expedite_supplier"]

    # --- order import ------------------------------------------------------
    order_lines = []
    for line_number, (item_index, quantity) in enumerate(world["orders"]["lines"], start=1):
        item = items[item_index]
        sheet_price = _q(_d(item["list_price"]) * (Decimal("1") + _d(world["orders"]["sheet_price_drift"])))
        previously_imported = (line_number - 1) in world["orders"]["previously_imported"]
        if previously_imported:
            reason = "duplicate: already imported on the earlier partial import"
        elif item["status"] != "Active":
            reason = "rejected: item is inactive"
        else:
            reason = "accepted"
        order_lines.append({"line": line_number, "item_number": item["item_number"], "description": item["description"], "quantity": quantity, "sheet_price": sheet_price, "list_price": item["list_price"], "previously_imported": previously_imported, "active": item["status"] == "Active", "disposition": reason})
    accepted = [line for line in order_lines if line["disposition"] == "accepted"]
    order_total = _q(sum((_d(line["quantity"]) * _d(line["list_price"]) for line in accepted), Decimal("0")))
    prior_lines = [line for line in order_lines if line["previously_imported"]]
    order_import = {
        "batch_file_id": f"FILE-{short}-ORDER-BATCH-0209",
        "stale_batch_file_id": f"FILE-{short}-ORDER-BATCH-0203",
        "batch_name": f"{customer['po']}-consolidated-order-2026-02-09.xlsx",
        "prior_order_number": f"SO-{short}-{40000 + len(short) * 13}",
        "lines": order_lines,
        "accepted_lines": len(accepted),
        "rejected_lines": len(order_lines) - len(accepted),
        "duplicate_lines": len(prior_lines),
        "inactive_lines": sum(1 for line in order_lines if not line["previously_imported"] and not line["active"]),
        "imported_units": sum(line["quantity"] for line in accepted),
        "order_total": order_total,
        "prior_total": _q(sum((_d(line["quantity"]) * _d(line["list_price"]) for line in prior_lines), Decimal("0"))),
        "credit_hold": bool(customer["credit_hold"]),
        "new_order_number": f"SO-{short}-{50000 + len(customer['po'])}",
    }

    # --- shipment verification --------------------------------------------
    ship_lines = []
    for line_number, (item_index, requested, picked, shipped) in enumerate(world["shipping"]["lines"], start=1):
        item = items[item_index]
        if picked == requested == shipped:
            disposition = "matching"
        elif picked < requested:
            disposition = "corrected"
        else:
            disposition = "held"
        ship_lines.append({"line": line_number, "shipment_line_id": 700000 + line_number * 3 + len(short), "item_number": item["item_number"], "requested": requested, "picked": picked, "shipped": shipped, "list_price": item["list_price"], "disposition": disposition})
    corrected = [line for line in ship_lines if line["disposition"] == "corrected"]
    held = [line for line in ship_lines if line["disposition"] == "held"]
    confirmed_value = _q(sum((_d(line["picked"] if line["disposition"] == "corrected" else line["requested"]) * _d(line["list_price"]) for line in ship_lines if line["disposition"] != "held"), Decimal("0")))
    shipment_verification = {
        "shipment": world["shipping"]["shipment"],
        "order": world["shipping"]["order"],
        "pick_file_id": f"FILE-{short}-PICK-CONFIRM-0208",
        "stale_pick_file_id": f"FILE-{short}-PICK-CONFIRM-0205",
        "lines": ship_lines,
        "lines_reviewed": len(ship_lines),
        "lines_matching": sum(1 for line in ship_lines if line["disposition"] == "matching"),
        "lines_corrected": len(corrected),
        "lines_held": len(held),
        "units_removed": sum(line["requested"] - line["picked"] for line in corrected),
        "confirmed_value": confirmed_value,
    }

    # --- receivables -------------------------------------------------------
    invoices = []
    for index, (number, amount, days_past_due) in enumerate(world["receivables"]["invoices"]):
        invoices.append({"transaction_number": number, "customer_transaction_id": 900000 + index * 11 + len(short), "amount": amount, "due_date": _iso(-days_past_due), "days_past_due": days_past_due, "covered": index in world["receivables"]["receipt"]["covers"]})
    receipt = world["receivables"]["receipt"]
    receipt_amount = _q(sum((_d(row["amount"]) for row in invoices if row["covered"]), Decimal("0")))
    remaining = [row for row in invoices if not row["covered"] and row["days_past_due"] > 0]
    remaining_past_due = _q(sum((_d(row["amount"]) for row in remaining), Decimal("0")))
    past_due_pct = _q(_d(remaining_past_due) / _d(customer["credit_limit"]) * 100)
    receivables = {
        "invoices": invoices,
        "receipt_number": receipt["number"],
        "receipt_date": receipt["date"],
        "receipt_method": receipt["method"],
        "remittance_message_id": f"MSG-{short}-REMIT-0206",
        "remittance_file_id": f"FILE-{short}-REMIT-ADVICE-0206",
        "open_invoices_before": len(invoices),
        "receipt_amount": receipt_amount,
        "covered_invoices": [row["transaction_number"] for row in invoices if row["covered"]],
        "remaining_past_due": remaining_past_due,
        "oldest_days_past_due": max((row["days_past_due"] for row in remaining), default=0),
        "past_due_pct_of_limit": past_due_pct,
        "hold_threshold_pct": world["receivables"]["hold_threshold_pct"],
        "credit_hold_recommended": past_due_pct > world["receivables"]["hold_threshold_pct"],
        "new_receipt_id": 950000 + len(short) * 17,
    }

    # --- inventory reorder -------------------------------------------------
    skus = []
    for item_index, on_hand, reserved, reorder_point, max_level, open_po in world["inventory"]["skus"]:
        item = items[item_index]
        available = on_hand - reserved + open_po
        below = item["status"] == "Active" and available <= reorder_point
        reorder_qty = max_level - available if below else 0
        skus.append({"item_number": item["item_number"], "on_hand": on_hand, "reserved": reserved, "open_po_qty": open_po, "available": available, "reorder_point": reorder_point, "max_level": max_level, "below": below, "reorder_qty": reorder_qty, "unit_cost": item["unit_cost"], "active": item["status"] == "Active"})
    to_order = [sku for sku in skus if sku["below"]]
    requisition_amount = _q(sum((_d(sku["reorder_qty"]) * _d(sku["unit_cost"]) for sku in to_order), Decimal("0")))
    need_days = world["inventory"]["need_days"]
    inventory_reorder = {
        "skus": skus,
        "policy_file_id": f"FILE-{short}-REORDER-POLICY-R4",
        "stale_policy_file_id": f"FILE-{short}-REORDER-POLICY-R3",
        "skus_below_reorder": len(to_order),
        "total_reorder_units": sum(sku["reorder_qty"] for sku in to_order),
        "requisition_amount": requisition_amount,
        "supplier_lead_time_days": supplier["lead_time_days"],
        "need_days": need_days,
        "days_late": max(0, supplier["lead_time_days"] - need_days),
        "expedite_premium_amount": _q(_d(requisition_amount) * _d(expedite["premium_pct"]) / 100),
        "requisition_number": f"REQ-{short}-{61000 + len(short) * 5}",
        "requisition_id": 610000 + len(short) * 7,
    }

    # --- receiving and AP match -------------------------------------------
    ap_lines = []
    tolerance = _d(world["payables"]["tolerance_pct"])
    for line_number, (item_index, ordered, po_price, received, invoiced_qty, invoice_price) in enumerate(world["payables"]["lines"], start=1):
        item = items[item_index]
        variance_pct = (_d(invoice_price) - _d(po_price)) / _d(po_price) * 100
        quantity_ok = invoiced_qty <= received
        price_ok = abs(variance_pct) <= tolerance
        matched = quantity_ok and price_ok
        ap_lines.append({"line": line_number, "item_number": item["item_number"], "ordered": ordered, "po_price": po_price, "received": received, "invoiced_qty": invoiced_qty, "invoice_price": invoice_price, "variance_pct": _q(variance_pct), "matched": matched, "hold_reason": None if matched else ("price variance exceeds tolerance" if not price_ok else "invoiced quantity exceeds receipt")})
    matched_amount = _q(sum((_d(line["invoiced_qty"]) * _d(line["po_price"]) for line in ap_lines if line["matched"]), Decimal("0")))
    variance_amount = _q(sum((_d(line["invoiced_qty"]) * (_d(line["invoice_price"]) - _d(line["po_price"])) for line in ap_lines if not line["matched"]), Decimal("0")))
    invoice_total = _q(sum((_d(line["invoiced_qty"]) * _d(line["invoice_price"]) for line in ap_lines), Decimal("0")))
    receiving_ap_match = {
        "po": world["payables"]["po"],
        "po_id": 880000 + len(short) * 9,
        "invoice_number": world["payables"]["invoice"],
        "invoice_file_id": f"FILE-{short}-SUPPLIER-INVOICE-0207",
        "delivery_note_file_id": f"FILE-{short}-DELIVERY-NOTE-0206",
        "tolerance_pct": world["payables"]["tolerance_pct"],
        "lines": ap_lines,
        "lines_matched": sum(1 for line in ap_lines if line["matched"]),
        "held_lines": sum(1 for line in ap_lines if not line["matched"]),
        "matched_amount": matched_amount,
        "variance_amount": variance_amount,
        "invoice_total": invoice_total,
        "payable_amount": matched_amount,
        "receipt_header_id": 770000 + len(short) * 3,
        "invoice_id": 660000 + len(short) * 5,
        "hold_id": 550000 + len(short) * 2,
    }

    # --- document compliance ----------------------------------------------
    documents = []
    for index, (person, document_type, days_to_expiry, alerted, outcome, check_pending) in enumerate(world["documents"]["workers"]):
        person_number = f"{short}-P{1001 + index}"
        expiring = 0 < days_to_expiry <= DOCUMENT_ALERT_WINDOW_DAYS
        documents.append({"person_number": person_number, "person": person, "document_type": document_type, "document_record_id": 400000 + index * 13 + len(short), "date_to": _iso(days_to_expiry), "days_to_expiry": days_to_expiry, "alerted": alerted, "expiring": expiring, "needs_alert": expiring and not alerted, "check_outcome": outcome, "check_pending": check_pending, "blocked": outcome == "fail"})
    needs_alert = [doc for doc in documents if doc["needs_alert"]]
    document_compliance = {
        "documents": documents,
        "checklist_file_id": f"FILE-{short}-COMPLIANCE-CHECKLIST-0209",
        "stale_checklist_file_id": f"FILE-{short}-COMPLIANCE-CHECKLIST-0126",
        "expiring_within_30": sum(1 for doc in documents if doc["expiring"]),
        "unalerted_expiring": len(needs_alert),
        "blocked_workers": sum(1 for doc in documents if doc["blocked"]),
        "checks_verified": sum(1 for doc in documents if doc["check_pending"] and not doc["blocked"]),
        "days_to_earliest_expiry": min((doc["days_to_expiry"] for doc in documents if doc["expiring"]), default=0),
    }

    # --- shift rollup ------------------------------------------------------
    time_section = world["time"]
    cutoff = _hhmm(time_section["cutoff"])
    reports = [{"staff_code": code_, "submitted_at": submitted, "late": _hhmm(submitted) > cutoff, "overtime_minutes": overtime} for code_, submitted, overtime in time_section["reports"]]
    expected_staff = time_section["expected"] - time_section["approved_absences"]
    reporting = len({report["staff_code"] for report in reports})
    prefix = reports[0]["staff_code"].split("-")[0]
    first_number = int(reports[0]["staff_code"].split("-")[1])
    roster_codes = [f"{prefix}-{first_number + offset}" for offset in range(time_section["expected"])]
    reported_codes = {report["staff_code"] for report in reports}
    unreported = [code_ for code_ in roster_codes if code_ not in reported_codes]
    approved_absent = unreported[: time_section["approved_absences"]]
    missing = unreported[time_section["approved_absences"]:]
    shift_rollup = {
        "shift_date": time_section["shift_date"],
        "shift": time_section["shift"],
        "cutoff": time_section["cutoff"],
        "roster_file_id": f"FILE-{short}-SHIFT-ROSTER-0208",
        "reports": reports,
        "roster_codes": roster_codes,
        "approved_absent": approved_absent,
        "missing": missing,
        "expected_staff": expected_staff,
        "reporting_staff": reporting,
        "late_reports": sum(1 for report in reports if report["late"]),
        "overtime_hours": _q(_d(sum(report["overtime_minutes"] for report in reports)) / 60),
        "missing_staff": len(missing),
    }

    # --- channel order sync ------------------------------------------------
    channel_rows = []
    seen: set[str] = set()
    for row_number, (channel_order_id, buyer, total, synced, duplicate) in enumerate(world["channel_sync"]["orders"], start=1):
        if synced:
            disposition = "already_synced"
        elif channel_order_id in seen:
            disposition = "duplicate_row"
        else:
            disposition = "create"
        seen.add(channel_order_id)
        channel_rows.append({"row": row_number, "channel_order_id": channel_order_id, "buyer": buyer, "total": total, "already_synced": synced, "duplicate_row": duplicate, "disposition": disposition, "synced_order_number": f"SO-{short}-{45000 + row_number * 3}" if synced else None})
    created_rows = [row for row in channel_rows if row["disposition"] == "create"]
    channel_order_sync = {
        "channel": world["channel"],
        "export_file_id": f"FILE-{short}-CHANNEL-EXPORT-0209",
        "stale_export_file_id": f"FILE-{short}-CHANNEL-EXPORT-0202",
        "rows": channel_rows,
        "channel_rows": len(channel_rows),
        "already_synced": sum(1 for row in channel_rows if row["disposition"] == "already_synced"),
        "created_orders": len(created_rows),
        "duplicate_rows": sum(1 for row in channel_rows if row["disposition"] == "duplicate_row"),
        "synced_value": _q(sum((_d(row["total"]) for row in created_rows), Decimal("0"))),
        "new_customer": world["channel_sync"]["new_customer"],
        "new_order_numbers": {row["channel_order_id"]: f"SO-{short}-{52000 + index * 7}" for index, row in enumerate(created_rows, start=1)},
    }

    # --- hiring ------------------------------------------------------------
    hiring_section = world["hiring"]
    contract_days = hiring_section["months"] * 30
    candidates = []
    for index, (name, permit_days, checks_passed) in enumerate(hiring_section["candidates"]):
        eligible = checks_passed and permit_days > contract_days
        candidates.append({"candidate_id": f"{short}-C{201 + index}", "name": name, "permit_expiry": _iso(permit_days), "permit_days": permit_days, "checks_passed": checks_passed, "eligible": eligible, "reason": "eligible" if eligible else ("background check not passed" if not checks_passed else "work permit expires before contract end")})
    open_headcount = hiring_section["approved"] - hiring_section["current"]
    eligible = [candidate for candidate in candidates if candidate["eligible"]]
    hires = eligible[:open_headcount]
    for offset, candidate in enumerate(hires):
        candidate["person_number"] = f"{short}-P{2001 + offset}"
    hire_against_requisition = {
        "job": hiring_section["job"],
        "approval_file_id": f"FILE-{short}-HEADCOUNT-APPROVAL-2026",
        "stale_approval_file_id": f"FILE-{short}-HEADCOUNT-APPROVAL-2025",
        "candidates": candidates,
        "approved": hiring_section["approved"],
        "current": hiring_section["current"],
        "open_headcount": open_headcount,
        "eligible_candidates": len(eligible),
        "hires": len(hires),
        "hired": hires,
        "wage": hiring_section["wage"],
        "monthly_wage_total": _q(_d(hiring_section["wage"]) * len(hires)),
        "contract_months": hiring_section["months"],
        "contract_end": _iso(contract_days),
    }

    # --- price list batch --------------------------------------------------
    pricing_section = world["pricing"]
    price_lines = []
    latest_effective: dict[str, int] = {}
    for item_number, new_price, effective_days in pricing_section["lines"]:
        item = item_by_number.get(item_number)
        if item is None:
            reason = "rejected: unknown item"
        elif item["status"] != "Active":
            reason = "rejected: item is inactive"
        elif effective_days < 0:
            reason = "rejected: effective date already past"
        else:
            change_pct = (_d(new_price) - _d(item["list_price"])) / _d(item["list_price"]) * 100
            reason = "accepted" if abs(change_pct) <= _d(pricing_section["max_change_pct"]) else "rejected: change outside approved band"
        if reason == "accepted":
            latest_effective[item_number] = max(latest_effective.get(item_number, -1), effective_days)
        price_lines.append({"line": len(price_lines) + 1, "item_number": item_number, "current_price": item["list_price"] if item else None, "new_price": new_price, "effective_date": _iso(effective_days), "effective_days": effective_days, "disposition": reason, "change_pct": _q((_d(new_price) - _d(item["list_price"])) / _d(item["list_price"]) * 100) if item else None})
    for line in price_lines:
        if line["disposition"] == "accepted" and latest_effective[line["item_number"]] != line["effective_days"]:
            line["disposition"] = "superseded"
    applied = [line for line in price_lines if line["disposition"] == "accepted"]
    average_change = _q(sum((_d(line["change_pct"]) for line in applied), Decimal("0")) / len(applied)) if applied else 0.0
    price_list_batch = {
        "batch": pricing_section["batch"],
        "batch_file_id": f"FILE-{short}-PRICE-BATCH-Q2",
        "stale_batch_file_id": f"FILE-{short}-PRICE-BATCH-Q1",
        "max_change_pct": pricing_section["max_change_pct"],
        "lines": price_lines,
        "batch_lines": len(price_lines),
        "accepted_lines": len(applied),
        "rejected_lines": sum(1 for line in price_lines if line["disposition"].startswith("rejected")),
        "superseded_lines": sum(1 for line in price_lines if line["disposition"] == "superseded"),
        "average_change_pct": average_change,
        "applied": applied,
    }

    return {
        "world": world,
        "items": items,
        "customer": customer,
        "supplier": supplier,
        "expedite_supplier": expedite,
        "order_import": order_import,
        "shipment_verification": shipment_verification,
        "receivables_collection": receivables,
        "inventory_reorder": inventory_reorder,
        "receiving_ap_match": receiving_ap_match,
        "document_compliance": document_compliance,
        "shift_rollup": shift_rollup,
        "channel_order_sync": channel_order_sync,
        "hire_against_requisition": hire_against_requisition,
        "price_list_batch": price_list_batch,
    }


# ---------------------------------------------------------------------------
# Gold outcome per task
# ---------------------------------------------------------------------------


def _family_outcome(world: dict[str, Any], family: dict[str, str]) -> dict[str, Any]:
    model = world_model(world["code"])
    key = family["key"]
    section = model[key]
    if key == "order_import":
        hold = section["credit_hold"]
        option = "import_accepted_lines_and_hold_submission" if hold else "import_accepted_lines_and_submit"
        status = "awaiting_credit_release" if hold else "submitted"
        source = section["batch_file_id"]
        primary = section["new_order_number"]
    elif key == "shipment_verification":
        option = "correct_short_picks_and_hold_over_picks" if section["lines_held"] else "correct_short_picks_and_confirm"
        status = "partial_hold" if section["lines_held"] else "ready_to_confirm"
        source = section["pick_file_id"]
        primary = section["shipment"]
    elif key == "receivables_collection":
        option = "apply_receipt_and_escalate_credit_hold" if section["credit_hold_recommended"] else "apply_receipt_and_continue_collections"
        status = "credit_review_required" if section["credit_hold_recommended"] else "collections_in_progress"
        source = section["remittance_file_id"]
        primary = section["receipt_number"]
    elif key == "inventory_reorder":
        option = "requisition_primary_supplier_and_flag_lateness" if section["days_late"] else "requisition_primary_supplier"
        status = "requisition_submitted_late_risk" if section["days_late"] else "requisition_submitted"
        source = section["policy_file_id"]
        primary = section["requisition_number"]
    elif key == "receiving_ap_match":
        option = "receive_and_hold_variance_lines" if section["held_lines"] else "receive_and_validate_invoice"
        status = "invoice_on_hold" if section["held_lines"] else "invoice_validated"
        source = section["delivery_note_file_id"]
        primary = section["invoice_number"]
    elif key == "document_compliance":
        option = "alert_expiring_and_block_failed_checks" if section["blocked_workers"] else "alert_expiring_and_verify_pending"
        status = "placements_blocked" if section["blocked_workers"] else "compliance_cleared"
        source = section["checklist_file_id"]
        primary = f"{world['short']}-COMPLIANCE-0209"
    elif key == "shift_rollup":
        option = "post_rollup_and_record_unauthorized_absences" if section["missing_staff"] else "post_rollup_no_absences"
        status = "absences_recorded" if section["missing_staff"] else "shift_complete"
        source = section["roster_file_id"]
        primary = f"ROLLUP-{world['short']}-{section['shift_date']}-{section['shift'].upper()}"
    elif key == "channel_order_sync":
        option = "create_unsynced_orders_and_capture_customer"
        status = "synced"
        source = section["export_file_id"]
        primary = section["new_order_numbers"][section["rows"][[row["disposition"] for row in section["rows"]].index("create")]["channel_order_id"]]
    elif key == "hire_against_requisition":
        option = "hire_eligible_within_quota" if section["hires"] == section["open_headcount"] else "hire_eligible_and_keep_positions_open"
        status = "quota_filled" if section["hires"] == section["open_headcount"] else "positions_remain_open"
        source = section["approval_file_id"]
        primary = section["hired"][0]["person_number"] if section["hired"] else "NO-HIRE"
    elif key == "price_list_batch":
        option = "apply_policy_compliant_lines"
        status = "batch_applied_with_rejections" if section["rejected_lines"] else "batch_applied"
        source = section["batch_file_id"]
        primary = section["batch"]
    else:
        raise KeyError(key)
    answer: dict[str, Any] = {"recommended_option": option, "decision_status": status, "source_reference": source, "primary_record": primary}
    for field in NUMERIC_FIELDS[key]:
        value = section[field]
        answer[field] = float(value) if isinstance(value, float) else int(value)
    return answer


# ---------------------------------------------------------------------------
# Evidence room
# ---------------------------------------------------------------------------

ASSET_NAMES: tuple[str, ...] = (
    "01-consolidated-order-batch.xlsx",
    "02-prior-partial-import.xlsx",
    "03-current-price-list.csv",
    "04-superseded-price-list.csv",
    "05-pick-confirmation.csv",
    "06-remittance-advice.pdf",
    "07-ar-aging.xlsx",
    "08-credit-policy.md",
    "09-reorder-policy.xlsx",
    "10-demand-forecast.csv",
    "11-supplier-invoice.pdf",
    "12-delivery-note.pdf",
    "13-ap-match-policy.md",
    "14-compliance-checklist.xlsx",
    "15-document-alert-log.csv",
    "16-shift-roster.xlsx",
    "17-shift-work-reports.csv",
    "18-channel-export.json",
    "19-customer-capture-chat.json",
    "20-headcount-approval.pdf",
    "21-candidate-register.xlsx",
    "22-wage-table.csv",
    "23-price-batch.csv",
    "24-authority-memo.eml",
    "25-source-map.yaml",
    "26-ops-audit.log",
)


def _asset_paths(world: dict[str, Any], task_id: str) -> list[str]:
    root = f"assets/{world['code'].lower()}"
    return [f"{root}/{name}" for name in ASSET_NAMES] + [
        f"assets/tasks/{task_id}/task-brief.md",
        f"assets/tasks/{task_id}/starting-snapshot.json",
    ]


def asset_payloads(world: dict[str, Any]) -> dict[str, tuple[str, Any]]:
    """Return path -> (kind, content) for the shared tenant evidence room."""

    model = world_model(world["code"])
    short = world["short"]
    root = f"assets/{world['code'].lower()}"
    customer = world["customer"]
    supplier = world["supplier"]
    people = world["people"]
    oi = model["order_import"]
    sv = model["shipment_verification"]
    rc = model["receivables_collection"]
    ir = model["inventory_reorder"]
    ap = model["receiving_ap_match"]
    dc = model["document_compliance"]
    sr = model["shift_rollup"]
    co = model["channel_order_sync"]
    hr = model["hire_against_requisition"]
    pb = model["price_list_batch"]

    batch_rows = [["Line", "Customer PO", "Item", "Description", "Quantity", "Unit price (customer sheet)"]] + [
        [line["line"], customer["po"], line["item_number"], line["description"], line["quantity"], line["sheet_price"]] for line in oi["lines"]
    ]
    prior_rows = [["Line", "Customer PO", "Item", "Quantity", "Imported order", "Imported on"]] + [
        [line["line"], customer["po"], line["item_number"], line["quantity"], oi["prior_order_number"], "2026-02-03"] for line in oi["lines"] if line["previously_imported"]
    ]
    price_csv = "item,description,list_price,status,effective_from\n" + "".join(
        f"{item['item_number']},{item['description']},{item['list_price']:.2f},{item['status']},2026-01-01\n" for item in model["items"]
    )
    stale_price_csv = "item,description,list_price,status,effective_from,superseded\n" + "".join(
        f"{item['item_number']},{item['description']},{_q(_d(item['list_price']) * Decimal('0.95')):.2f},Active,2025-07-01,true\n" for item in model["items"]
    )
    pick_csv = "shipment,line,item,requested,picked,picker,confirmed_at\n" + "".join(
        f"{sv['shipment']},{line['line']},{line['item_number']},{line['requested']},{line['picked']},WH-{10 + line['line']},2026-02-08T21:{10 + line['line']:02d}:00Z\n" for line in sv["lines"]
    )
    remittance = (
        f"{customer['name']} — remittance advice\n"
        f"Payee: {world['company']}\n"
        f"Payment date: {rc['receipt_date']}   Method: {rc['receipt_method']}\n"
        f"Amount paid: {rc['receipt_amount']:.2f} {world['currency']}\n"
        "Invoices covered by this payment:\n"
        + "".join(f"  {row['transaction_number']}  {row['amount']:.2f}\n" for row in rc["invoices"] if row["covered"])
        + "Invoices not included in this remittance are disputed or scheduled separately.\n"
    )
    aging_rows = [["Invoice", "Amount", "Due date", "Days past due", "Status"]] + [
        [row["transaction_number"], row["amount"], row["due_date"], max(row["days_past_due"], 0), "open"] for row in rc["invoices"]
    ]
    credit_policy = (
        f"# {world['company']} credit policy (revision 6, effective 2026-01-15)\n\n"
        f"- Credit limit for {customer['name']}: {customer['credit_limit']:.2f} {world['currency']}.\n"
        f"- Recommend a credit hold when past-due receivables exceed {rc['hold_threshold_pct']:.0f}% of the credit limit after all identified receipts are applied.\n"
        f"- Credit holds are approved only by {people['finance_lead']}; analysts recommend, they do not apply holds.\n"
        "- Receipts are applied only to the invoices named on the customer's remittance advice.\n"
    )
    reorder_rows = [["Item", "Reorder point", "Planned maximum", "Count open POs as supply", "Policy revision"]] + [
        [sku["item_number"], sku["reorder_point"], sku["max_level"], "yes", "R4"] for sku in ir["skus"]
    ]
    forecast_csv = "item,weekly_demand,need_window_days,forecast_revision\n" + "".join(
        f"{sku['item_number']},{max(sku['reorder_point'] // 4, 1)},{ir['need_days']},F-2026-06\n" for sku in ir["skus"]
    )
    supplier_invoice = (
        f"{supplier['name']} — tax invoice {ap['invoice_number']}\n"
        f"Bill to: {world['company']} ({world['bu']})\n"
        f"Purchase order: {ap['po']}   Invoice date: 2026-02-07\n"
        + "".join(f"Line {line['line']}: {line['item_number']}  qty {line['invoiced_qty']}  @ {line['invoice_price']:.2f}\n" for line in ap["lines"])
        + f"Invoice total: {ap['invoice_total']:.2f} {world['currency']}\n"
    )
    delivery_note = (
        f"{supplier['name']} — delivery note DN-{short}-0206 for {ap['po']}\n"
        f"Delivered to {world['site']} on 2026-02-06, signed by receiving clerk.\n"
        + "".join(f"Line {line['line']}: {line['item_number']}  ordered {line['ordered']}  delivered {line['received']}\n" for line in ap["lines"])
        + "Quantities below the ordered amount are back-ordered, not short-shipped.\n"
    )
    ap_policy = (
        f"# {world['company']} three-way match policy\n\n"
        f"- Price tolerance: {ap['tolerance_pct']:.1f}% of the purchase-order unit price per line.\n"
        "- Invoiced quantity may never exceed the received quantity.\n"
        "- Lines outside tolerance are entered and placed on hold with the reason; matched lines are validated for payment.\n"
        f"- Payment release is authorized by {people['finance_lead']} after the analyst's match note.\n"
    )
    checklist_rows = [["Person", "Person number", "Document", "Expires", "Days remaining", "Mandatory check", "Check pending"]] + [
        [doc["person"], doc["person_number"], doc["document_type"], doc["date_to"], doc["days_to_expiry"], doc["check_outcome"], "yes" if doc["check_pending"] else "no"] for doc in dc["documents"]
    ]
    alert_log = "person_number,document,alerted_on,alerted_by\n" + "".join(
        f"{doc['person_number']},{doc['document_type']},2026-01-28,{people['hr_lead']}\n" for doc in dc["documents"] if doc["alerted"]
    )
    roster_rows = [["Staff code", "Shift", "Date", "Approved leave"]] + [
        [code_, sr["shift"], sr["shift_date"], "yes" if code_ in sr["approved_absent"] else "no"] for code_ in sr["roster_codes"]
    ]
    reports_csv = "staff_code,shift_date,submitted_at,minutes_over_shift_end\n" + "".join(
        f"{report['staff_code']},{sr['shift_date']},{report['submitted_at']},{report['overtime_minutes']}\n" for report in sr["reports"]
    )
    channel_export = {"channel": world["channel"], "exported_at": "2026-02-09T06:00:00Z", "orders": [
        {"channel_order_id": row["channel_order_id"], "buyer": row["buyer"], "order_total": row["total"], "currency": world["currency"], "status": "paid"} for row in co["rows"]
    ]}
    capture_chat = {"channel": f"#customers-{short.lower()}", "messages": [
        {"author": "sales-inbox", "text": f"New buyer from {world['channel']}: {co['new_customer']['name']}, tax id {co['new_customer']['tax_id']}, orders via {co['new_customer']['email']}. Needs a master record before invoicing."},
        {"author": people["ops_lead"], "text": "Capture it in the customer master tab, not as a note; check the channel export for their first order."},
    ]}
    headcount_pdf = (
        f"{world['company']} headcount approval 2026 (revision 2)\n"
        f"Position: {hr['job']}   Approved headcount: {hr['approved']}   Standard contract: {hr['contract_months']} months\n"
        f"Approved monthly wage: {hr['wage']:.2f} {world['currency']}\n"
        f"Approved by {people['hr_lead']} on 2026-01-20. Supersedes the 2025 approval.\n"
        "Only candidates with passed background checks and work permits valid beyond the contract end may be hired.\n"
    )
    candidate_rows = [["Candidate", "Candidate id", "Permit expiry", "Background check", "Grade"]] + [
        [candidate["name"], candidate["candidate_id"], candidate["permit_expiry"], "passed" if candidate["checks_passed"] else "not passed", "B"] for candidate in hr["candidates"]
    ]
    wage_csv = "position,monthly_wage,contract_months,approved_from\n" + f"{hr['job']},{hr['wage']:.2f},{hr['contract_months']},2026-01-20\n"
    price_batch_csv = "batch,line,item,new_list_price,effective_date\n" + "".join(
        f"{pb['batch']},{line['line']},{line['item_number']},{line['new_price']:.2f},{line['effective_date']}\n" for line in pb["lines"]
    )
    authority_email = (
        f"From: {people['ops_lead'].lower().replace(' ', '.')}@{world['domain']}\n"
        f"To: analyst@{world['domain']}\n"
        f"Subject: {world['company']} operating authority for February\n\n"
        "Current sources of truth: the 2026-02-09 order batch, the 2026-02-08 pick confirmation, the 2026-02-06 remittance advice, "
        "reorder policy R4, the 2026-02-06 delivery note, the 2026-02-09 compliance checklist, the 2026-02-08 roster, the 2026-02-09 channel export, "
        "the 2026 headcount approval and the Q2 price batch. Earlier versions are superseded. All outbound messages stay in review.\n"
    )
    source_map = (
        f"tenant: {world['code']}\n"
        f"order_batch: {oi['batch_file_id']}\n"
        f"pick_confirmation: {sv['pick_file_id']}\n"
        f"remittance_advice: {rc['remittance_file_id']}\n"
        f"reorder_policy: {ir['policy_file_id']}\n"
        f"delivery_note: {ap['delivery_note_file_id']}\n"
        f"compliance_checklist: {dc['checklist_file_id']}\n"
        f"shift_roster: {sr['roster_file_id']}\n"
        f"channel_export: {co['export_file_id']}\n"
        f"headcount_approval: {hr['approval_file_id']}\n"
        f"price_batch: {pb['batch_file_id']}\n"
    )
    audit_log = (
        f"2026-02-03T10:12:00Z {short} partial import created {oi['prior_order_number']} from an earlier copy of {customer['po']}\n"
        f"2026-02-06T15:40:00Z {short} delivery note DN-{short}-0206 received at {world['site']}\n"
        f"2026-02-08T22:05:00Z {short} pick confirmation posted for {sv['shipment']}\n"
        f"2026-02-09T06:00:00Z {short} {world['channel']} export generated\n"
    )
    return {
        f"{root}/01-consolidated-order-batch.xlsx": ("xlsx", batch_rows),
        f"{root}/02-prior-partial-import.xlsx": ("xlsx", prior_rows),
        f"{root}/03-current-price-list.csv": ("text", price_csv),
        f"{root}/04-superseded-price-list.csv": ("text", stale_price_csv),
        f"{root}/05-pick-confirmation.csv": ("text", pick_csv),
        f"{root}/06-remittance-advice.pdf": ("pdf", remittance),
        f"{root}/07-ar-aging.xlsx": ("xlsx", aging_rows),
        f"{root}/08-credit-policy.md": ("text", credit_policy),
        f"{root}/09-reorder-policy.xlsx": ("xlsx", reorder_rows),
        f"{root}/10-demand-forecast.csv": ("text", forecast_csv),
        f"{root}/11-supplier-invoice.pdf": ("pdf", supplier_invoice),
        f"{root}/12-delivery-note.pdf": ("pdf", delivery_note),
        f"{root}/13-ap-match-policy.md": ("text", ap_policy),
        f"{root}/14-compliance-checklist.xlsx": ("xlsx", checklist_rows),
        f"{root}/15-document-alert-log.csv": ("text", alert_log),
        f"{root}/16-shift-roster.xlsx": ("xlsx", roster_rows),
        f"{root}/17-shift-work-reports.csv": ("text", reports_csv),
        f"{root}/18-channel-export.json": ("json", channel_export),
        f"{root}/19-customer-capture-chat.json": ("json", capture_chat),
        f"{root}/20-headcount-approval.pdf": ("pdf", headcount_pdf),
        f"{root}/21-candidate-register.xlsx": ("xlsx", candidate_rows),
        f"{root}/22-wage-table.csv": ("text", wage_csv),
        f"{root}/23-price-batch.csv": ("text", price_batch_csv),
        f"{root}/24-authority-memo.eml": ("text", authority_email),
        f"{root}/25-source-map.yaml": ("text", source_map),
        f"{root}/26-ops-audit.log": ("text", audit_log),
    }


# ---------------------------------------------------------------------------
# Investigations, oracle steps, rubric
# ---------------------------------------------------------------------------


def _sheet(world: dict[str, Any]) -> str:
    return f"SHEET-{world['short']}-OPS"


def _channel(world: dict[str, Any]) -> str:
    return f"#ops-{world['short'].lower()}"


def _investigations(task_id: str, world: dict[str, Any], family: dict[str, str]) -> list[dict[str, Any]]:
    model = world_model(world["code"])
    short = world["short"]
    org = world["org"]
    customer = world["customer"]
    supplier = world["supplier"]
    key = family["key"]
    sheet = _sheet(world)
    channel = _channel(world)
    common = [
        ("task_contract", "erpbench.get_task", {"task_id": task_id}),
        ("request_mail_search", "gmail.messages.list", {"q": task_id}),
        ("request_mail", "gmail.messages.get", {"id": f"MSG-{task_id}-REQUEST"}),
        ("authority_memo", "gmail.messages.get", {"id": f"MSG-{short}-AUTHORITY-0209"}),
        ("control_thread", "slack.conversations_history", {"channel": channel}),
        ("ops_register", "google_sheets.spreadsheets.values.get", {"spreadsheetId": sheet, "range": "Register!A1:H40"}),
        ("item_master", "oracle_fusion.items.list", {"q": f"OrganizationCode='{org}'"}),
        ("source_map", "google_drive.files.download", {"fileId": f"FILE-{short}-SOURCE-MAP"}),
    ]
    domain: dict[str, list[tuple[str, str, dict[str, Any]]]] = {
        "order_import": [
            ("batch_search", "google_drive.files.list", {"q": f"name contains '{customer['po']}'"}),
            ("batch_file", "google_drive.files.download", {"fileId": model["order_import"]["batch_file_id"]}),
            ("existing_orders", "oracle_fusion.sales_orders.list", {"q": f"CustomerPONumber='{customer['po']}'"}),
            ("prior_order_lines", "oracle_fusion.sales_orders.get", {"OrderKey": model["order_import"]["prior_order_number"]}),
            ("customer_account", "oracle_fusion.customer_account_activities.get", {"AccountId": customer["number"]}),
            ("price_list_tab", "google_sheets.spreadsheets.values.get", {"spreadsheetId": sheet, "range": "PriceList!A1:E12"}),
            ("prior_import_thread", "slack.search_messages", {"query": customer["po"]}),
        ],
        "shipment_verification": [
            ("shipment_header", "oracle_fusion.shipments.list", {"q": f"Shipment='{model['shipment_verification']['shipment']}'"}),
            ("shipment_lines", "oracle_fusion.shipment_lines.list", {"q": f"Shipment='{model['shipment_verification']['shipment']}'"}),
            ("pick_search", "google_drive.files.list", {"q": f"name contains '{model['shipment_verification']['shipment']}'"}),
            ("pick_confirmation", "google_drive.files.download", {"fileId": model["shipment_verification"]["pick_file_id"]}),
            ("sales_order", "oracle_fusion.sales_orders.get", {"OrderKey": model["shipment_verification"]["order"]}),
            ("shipping_register", "google_sheets.spreadsheets.values.get", {"spreadsheetId": sheet, "range": "Shipping!A1:F20"}),
            ("warehouse_thread", "slack.search_messages", {"query": model["shipment_verification"]["shipment"]}),
        ],
        "receivables_collection": [
            ("open_invoices", "oracle_fusion.receivables_invoices.list", {"q": f"BillToCustomerNumber='{customer['number']}' and InvoiceStatus='Open'"}),
            ("customer_account", "oracle_fusion.customer_account_activities.get", {"AccountId": customer["number"]}),
            ("existing_receipts", "oracle_fusion.standard_receipts.list", {"q": f"CustomerAccountNumber='{customer['number']}'"}),
            ("remittance_mail", "gmail.messages.get", {"id": model["receivables_collection"]["remittance_message_id"]}),
            ("remittance_advice", "google_drive.files.download", {"fileId": model["receivables_collection"]["remittance_file_id"]}),
            ("credit_policy", "google_drive.files.download", {"fileId": f"FILE-{short}-CREDIT-POLICY-R6"}),
            ("ar_aging_tab", "google_sheets.spreadsheets.values.get", {"spreadsheetId": sheet, "range": "Aging!A1:E12"}),
        ],
        "inventory_reorder": [
            ("onhand_balances", "oracle_fusion.onhand_balances.list", {"q": f"OrganizationCode='{org}'"}),
            ("open_purchase_orders", "oracle_fusion.purchase_orders.list", {"q": f"Supplier='{supplier['name']}' and Status='Open'"}),
            ("suppliers", "oracle_fusion.suppliers.list", {"q": f"SupplierNumber in ('{supplier['number']}','{world['expedite_supplier']['number']}')"}),
            ("reorder_policy", "google_drive.files.download", {"fileId": model["inventory_reorder"]["policy_file_id"]}),
            ("demand_forecast", "google_drive.files.download", {"fileId": f"FILE-{short}-DEMAND-FORECAST-F06"}),
            ("reorder_tab", "google_sheets.spreadsheets.values.get", {"spreadsheetId": sheet, "range": "Reorder!A1:F12"}),
            ("planning_thread", "slack.search_messages", {"query": "reorder"}),
        ],
        "receiving_ap_match": [
            ("purchase_order", "oracle_fusion.purchase_orders.get", {"purchaseOrdersUniqID": model["receiving_ap_match"]["po"]}),
            ("purchase_order_lines", "oracle_fusion.purchase_order_lines.list", {"purchaseOrdersUniqID": model["receiving_ap_match"]["po"]}),
            ("delivery_note", "google_drive.files.download", {"fileId": model["receiving_ap_match"]["delivery_note_file_id"]}),
            ("supplier_invoice", "google_drive.files.download", {"fileId": model["receiving_ap_match"]["invoice_file_id"]}),
            ("invoice_mail", "gmail.messages.get", {"id": f"MSG-{short}-SUPPLIER-INVOICE-0207"}),
            ("ap_policy", "google_drive.files.download", {"fileId": f"FILE-{short}-AP-MATCH-POLICY"}),
            ("existing_ap_invoices", "oracle_fusion.invoices.list", {"q": f"Supplier='{supplier['name']}'"}),
        ],
        "document_compliance": [
            ("workers", "oracle_fusion.workers.list", {"q": f"LegalEmployerName='{world['company']}'"}),
            ("document_records", "oracle_fusion.document_records.list", {"q": f"LegalEmployerName='{world['company']}'"}),
            ("checklist", "google_drive.files.download", {"fileId": model["document_compliance"]["checklist_file_id"]}),
            ("alert_log", "google_drive.files.download", {"fileId": f"FILE-{short}-DOCUMENT-ALERT-LOG"}),
            ("compliance_tab", "google_sheets.spreadsheets.values.get", {"spreadsheetId": sheet, "range": "Compliance!A1:G14"}),
            ("hr_thread", "slack.search_messages", {"query": "compliance"}),
            ("auditor_mail", "gmail.messages.get", {"id": f"MSG-{short}-AUDITOR-0205"}),
        ],
        "shift_rollup": [
            ("work_reports", "google_drive.files.download", {"fileId": f"FILE-{short}-SHIFT-REPORTS-0208"}),
            ("roster", "google_drive.files.download", {"fileId": model["shift_rollup"]["roster_file_id"]}),
            ("absences", "oracle_fusion.absences.list", {"q": f"employer='{world['company']}' and startDate='{model['shift_rollup']['shift_date']}'"}),
            ("workers", "oracle_fusion.workers.list", {"q": f"LegalEmployerName='{world['company']}'"}),
            ("shift_tab", "google_sheets.spreadsheets.values.get", {"spreadsheetId": sheet, "range": "Shifts!A1:F30"}),
            ("shift_thread", "slack.search_messages", {"query": model["shift_rollup"]["shift"]}),
            ("supervisor_mail", "gmail.messages.get", {"id": f"MSG-{short}-SUPERVISOR-0208"}),
        ],
        "channel_order_sync": [
            ("export_search", "google_drive.files.list", {"q": f"name contains '{world['channel']}'"}),
            ("channel_export", "google_drive.files.download", {"fileId": model["channel_order_sync"]["export_file_id"]}),
            ("synced_orders", "oracle_fusion.sales_orders.list", {"q": f"SourceTransactionSystem='{world['channel']}'"}),
            ("customer_capture", "slack.conversations_history", {"channel": f"#customers-{short.lower()}"}),
            ("customer_master_tab", "google_sheets.spreadsheets.values.get", {"spreadsheetId": sheet, "range": "Customers!A1:E12"}),
            ("customer_account", "oracle_fusion.customer_account_activities.get", {"AccountId": customer["number"]}),
            ("sync_mail", "gmail.messages.get", {"id": f"MSG-{short}-CHANNEL-0209"}),
        ],
        "hire_against_requisition": [
            ("headcount_approval", "google_drive.files.download", {"fileId": model["hire_against_requisition"]["approval_file_id"]}),
            ("current_workers", "oracle_fusion.workers.list", {"q": f"LegalEmployerName='{world['company']}' and JobCode='{model['hire_against_requisition']['job']}'"}),
            ("candidates", "google_drive.files.download", {"fileId": f"FILE-{short}-CANDIDATE-REGISTER"}),
            ("wage_table", "google_drive.files.download", {"fileId": f"FILE-{short}-WAGE-TABLE"}),
            ("headcount_tab", "google_sheets.spreadsheets.values.get", {"spreadsheetId": sheet, "range": "Headcount!A1:E12"}),
            ("hr_request_mail", "gmail.messages.get", {"id": f"MSG-{short}-HIRING-0209"}),
            ("hr_thread", "slack.search_messages", {"query": "hiring"}),
        ],
        "price_list_batch": [
            ("batch_search", "google_drive.files.list", {"q": f"name contains '{model['price_list_batch']['batch']}'"}),
            ("price_batch", "google_drive.files.download", {"fileId": model["price_list_batch"]["batch_file_id"]}),
            ("current_prices", "google_drive.files.download", {"fileId": f"FILE-{short}-PRICE-LIST-CURRENT"}),
            ("pricing_policy", "google_sheets.spreadsheets.values.get", {"spreadsheetId": sheet, "range": "PricingPolicy!A1:C6"}),
            ("pricing_mail", "gmail.messages.get", {"id": f"MSG-{short}-PRICING-0209"}),
            ("pricing_thread", "slack.search_messages", {"query": "price batch"}),
            ("prior_batch", "google_drive.files.download", {"fileId": model["price_list_batch"]["stale_batch_file_id"]}),
        ],
    }
    steps = common + domain[key]
    return [
        {"id": identifier, "description": identifier.replace("_", " "), "any_of": [{"tool": tool, "arguments": arguments}]}
        for identifier, tool, arguments in steps
    ]


def _primary_writes(task_id: str, world: dict[str, Any], family: dict[str, str], expected: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the ERP writes (and their readbacks) the oracle performs."""

    model = world_model(world["code"])
    org = world["org"]
    customer = world["customer"]
    supplier = world["supplier"]
    key = family["key"]
    steps: list[dict[str, Any]] = []
    if key == "order_import":
        section = model["order_import"]
        lines = [{"ProductNumber": line["item_number"], "OrderedQuantity": line["quantity"], "OrderedUOM": "EA", "UnitListPrice": line["list_price"]} for line in section["lines"] if line["disposition"] == "accepted"]
        steps.append({"tool": "oracle_fusion.sales_orders.create", "arguments": {"SourceTransactionNumber": section["batch_file_id"], "SourceTransactionSystem": "OPS", "BuyingPartyNumber": customer["number"], "CustomerPONumber": customer["po"], "TransactionType": "Standard Orders", "RequestedFulfillmentOrganizationCode": org, "SubmittedFlag": not section["credit_hold"], "lines": lines, "task_id": task_id}})
        steps.append({"tool": "oracle_fusion.sales_orders.get", "arguments": {"OrderKey": section["new_order_number"]}})
    elif key == "shipment_verification":
        section = model["shipment_verification"]
        for line in section["lines"]:
            if line["disposition"] == "corrected":
                steps.append({"tool": "oracle_fusion.shipment_lines.update", "arguments": {"ShipmentLine": line["shipment_line_id"], "ShippedQuantity": line["picked"], "Comments": f"Corrected to pick confirmation {section['pick_file_id']}", "task_id": task_id}})
        steps.append({"tool": "oracle_fusion.shipment_lines.list", "arguments": {"q": f"Shipment='{section['shipment']}'"}})
    elif key == "receivables_collection":
        section = model["receivables_collection"]
        steps.append({"tool": "oracle_fusion.standard_receipts.create", "arguments": {"ReceiptNumber": section["receipt_number"], "ReceiptAmount": section["receipt_amount"], "ReceiptDate": section["receipt_date"], "CustomerAccountNumber": customer["number"], "ReceiptMethod": section["receipt_method"], "BusinessUnit": world["bu"], "Currency": world["currency"], "remittanceReferences": [{"ReferenceType": "INVOICE", "ReferenceNumber": number, "ApplyAmount": next(row["amount"] for row in section["invoices"] if row["transaction_number"] == number)} for number in section["covered_invoices"]], "task_id": task_id}})
        steps.append({"tool": "oracle_fusion.standard_receipts.list", "arguments": {"q": f"CustomerAccountNumber='{customer['number']}'"}})
    elif key == "inventory_reorder":
        section = model["inventory_reorder"]
        lines = [{"ItemNumber": sku["item_number"], "Quantity": sku["reorder_qty"], "UOM": "EA", "UnitPrice": sku["unit_cost"], "Supplier": supplier["name"], "RequestedDeliveryDate": _iso(section["supplier_lead_time_days"])} for sku in section["skus"] if sku["below"]]
        steps.append({"tool": "oracle_fusion.purchase_requisitions.create", "arguments": {"RequisitioningBU": world["bu"], "Preparer": "analyst", "Description": f"Reorder run {org} 2026-02-09 under policy {section['policy_file_id']}", "Justification": f"{len(lines)} items at or below reorder point after reservations and open supply", "lines": lines, "task_id": task_id}})
        steps.append({"tool": "oracle_fusion.purchase_requisitions.submit", "arguments": {"purchaseRequisitionsUniqID": section["requisition_number"], "task_id": task_id}})
        steps.append({"tool": "oracle_fusion.purchase_requisitions.get", "arguments": {"purchaseRequisitionsUniqID": section["requisition_number"]}})
    elif key == "receiving_ap_match":
        section = model["receiving_ap_match"]
        steps.append({"tool": "oracle_fusion.receiving_receipt_requests.create", "arguments": {"ReceiptSourceCode": "VENDOR", "OrganizationCode": org, "VendorName": supplier["name"], "lines": [{"DocumentNumber": section["po"], "DocumentLineNumber": line["line"], "ItemNumber": line["item_number"], "Quantity": line["received"], "TransactionType": "RECEIVE"} for line in section["lines"]], "task_id": task_id}})
        steps.append({"tool": "oracle_fusion.invoices.create", "arguments": {"BusinessUnit": world["bu"], "Supplier": supplier["name"], "InvoiceNumber": section["invoice_number"], "InvoiceAmount": section["invoice_total"], "InvoiceCurrency": world["currency"], "InvoiceDate": "2026-02-07", "invoiceLines": [{"LineNumber": line["line"], "PurchaseOrderNumber": section["po"], "PurchaseOrderLineNumber": line["line"], "ItemNumber": line["item_number"], "Quantity": line["invoiced_qty"], "UnitPrice": line["invoice_price"]} for line in section["lines"]], "task_id": task_id}})
        if section["held_lines"]:
            steps.append({"tool": "oracle_fusion.invoice_holds.create", "arguments": {"InvoiceId": section["invoice_id"], "HoldName": "Price" if any(line["hold_reason"] == "price variance exceeds tolerance" for line in section["lines"]) else "Quantity", "HoldReason": "; ".join(f"line {line['line']}: {line['hold_reason']}" for line in section["lines"] if not line["matched"]), "task_id": task_id}})
        else:
            steps.append({"tool": "oracle_fusion.invoices.validate", "arguments": {"ProcessAction": "Validate", "BusinessUnit": world["bu"], "Supplier": supplier["name"], "InvoiceNumber": section["invoice_number"], "task_id": task_id}})
        steps.append({"tool": "oracle_fusion.invoices.get", "arguments": {"invoicesUniqID": section["invoice_number"]}})
    elif key == "document_compliance":
        section = model["document_compliance"]
        for doc in section["documents"]:
            if doc["needs_alert"] or (doc["check_pending"] and not doc["blocked"]):
                arguments = {"DocumentRecordId": doc["document_record_id"], "task_id": task_id}
                if doc["needs_alert"]:
                    arguments["Status"] = "ALERTED"
                if doc["check_pending"] and not doc["blocked"]:
                    arguments["VerifiedFlag"] = True
                steps.append({"tool": "oracle_fusion.document_records.update", "arguments": arguments})
        steps.append({"tool": "oracle_fusion.document_records.list", "arguments": {"q": f"LegalEmployerName='{world['company']}'"}})
    elif key == "shift_rollup":
        section = model["shift_rollup"]
        for code_ in section["missing"]:
            steps.append({"tool": "oracle_fusion.absences.create", "arguments": {"personNumber": code_, "absenceType": "Unauthorized absence", "startDate": section["shift_date"], "endDate": section["shift_date"], "employer": world["company"], "absenceStatusCd": "SUBMITTED", "task_id": task_id}})
        steps.append({"tool": "oracle_fusion.absences.list", "arguments": {"q": f"employer='{world['company']}' and startDate='{section['shift_date']}'"}})
    elif key == "channel_order_sync":
        section = model["channel_order_sync"]
        for row in section["rows"]:
            if row["disposition"] == "create":
                steps.append({"tool": "oracle_fusion.sales_orders.create", "arguments": {"SourceTransactionNumber": row["channel_order_id"], "SourceTransactionSystem": world["channel"], "BuyingPartyName": row["buyer"], "CustomerPONumber": row["channel_order_id"], "TransactionType": "Standard Orders", "RequestedFulfillmentOrganizationCode": org, "SubmittedFlag": True, "OrderTotal": row["total"], "task_id": task_id}})
        steps.append({"tool": "oracle_fusion.sales_orders.list", "arguments": {"q": f"SourceTransactionSystem='{world['channel']}'"}})
        new_customer = section["new_customer"]
        steps.append({"tool": "google_sheets.spreadsheets.values.append", "arguments": {"spreadsheetId": _sheet(world), "range": "Customers!A1:E12", "valueInputOption": "RAW", "values": [[new_customer["name"], "", new_customer["email"], new_customer["tax_id"], world["channel"]]], "task_id": task_id}})
    elif key == "hire_against_requisition":
        section = model["hire_against_requisition"]
        for candidate in section["hired"]:
            steps.append({"tool": "oracle_fusion.workers.create", "arguments": {"PersonNumber": candidate["person_number"], "DisplayName": candidate["name"], "LegalEmployerName": world["company"], "JobCode": section["job"], "HireDate": AS_OF_DATE.isoformat(), "ContractEndDate": section["contract_end"], "MonthlySalary": section["wage"], "CandidateId": candidate["candidate_id"], "task_id": task_id}})
        steps.append({"tool": "oracle_fusion.workers.list", "arguments": {"q": f"LegalEmployerName='{world['company']}' and JobCode='{section['job']}'"}})
    elif key == "price_list_batch":
        section = model["price_list_batch"]
        for line in section["applied"]:
            item = next(item for item in model["items"] if item["item_number"] == line["item_number"])
            steps.append({"tool": "oracle_fusion.items.update", "arguments": {"ItemId": item["item_id"], "ListPrice": line["new_price"], "EffectiveDate": line["effective_date"], "task_id": task_id}})
        steps.append({"tool": "oracle_fusion.items.list", "arguments": {"q": f"OrganizationCode='{org}'"}})
    return steps


def _register_row(world: dict[str, Any], family: dict[str, str], expected: dict[str, Any]) -> list[Any]:
    values = [expected[field] for field in NUMERIC_FIELDS[family["key"]]]
    return [expected["primary_record"], expected["recommended_option"], *values, expected["source_reference"]]


def _oracle_steps(task_id: str, world: dict[str, Any], family: dict[str, str], expected: dict[str, Any]) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    for investigation in _investigations(task_id, world, family):
        requirement = investigation["any_of"][0]
        steps.append({"tool": requirement["tool"], "arguments": deepcopy(requirement["arguments"])})
    steps.extend(_primary_writes(task_id, world, family, expected))
    sheet = _sheet(world)
    channel = _channel(world)
    people = world["people"]
    numeric_summary = "; ".join(f"{field.replace('_', ' ')} {expected[field]}" for field in NUMERIC_FIELDS[family["key"]])
    steps.extend(
        [
            {
                "tool": "google_sheets.spreadsheets.values.update",
                "arguments": {"spreadsheetId": sheet, "range": f"Register!A{_register_row_number(task_id)}:J{_register_row_number(task_id)}", "valueInputOption": "RAW", "values": [_register_row(world, family, expected)], "task_id": task_id},
            },
            {
                "tool": "erpbench.record_decision",
                "arguments": {"task_id": task_id, "decision": expected["recommended_option"], "status": expected["decision_status"], "primary_record": expected["primary_record"], "source_refs": [expected["source_reference"], f"MSG-{task_id}-REQUEST", f"MSG-{world['short']}-AUTHORITY-0209"], "rationale": f"Current evidence supports {expected['recommended_option']}; operative source {expected['source_reference']}."},
            },
            {
                "tool": "gmail.drafts.create",
                "arguments": {"to": f"{people['ops_lead'].lower().replace(' ', '.')}@{world['domain']}", "subject": f"{task_id} — {family['title']} — for review", "body": f"{world['company']}: recommend {expected['recommended_option']} ({expected['decision_status']}). {numeric_summary}. Primary record {expected['primary_record']}; operative source {expected['source_reference']}. Draft for review, not sent.", "task_id": task_id},
            },
            {
                "tool": "slack.chat_postMessage",
                "arguments": {"channel": channel, "text": f"{task_id}: {expected['decision_status']} / {expected['recommended_option']} / {expected['primary_record']} — review draft ready.", "review_status": "draft_for_review", "task_id": task_id},
            },
            {"tool": "google_sheets.spreadsheets.values.get", "arguments": {"spreadsheetId": sheet, "range": f"Register!A{_register_row_number(task_id)}:J{_register_row_number(task_id)}"}},
            {"tool": "erpbench.get_decision", "arguments": {"task_id": task_id}},
            {"tool": "gmail.drafts.get", "arguments": {"id": f"DRAFT-{task_id}"}},
            {"tool": "slack.conversations_history", "arguments": {"channel": channel, "task_id": task_id}},
            {"tool": "erpbench.submit_answer", "arguments": {"task_id": task_id, "answers": deepcopy(expected)}},
            {"tool": "erpbench.get_submission", "arguments": {"task_id": task_id}},
        ]
    )
    return steps


def _register_row_number(task_id: str) -> int:
    return 20 + int(task_id.split("-")[-1]) % 10


PRIMARY_WRITE_TOOLS: dict[str, str] = {
    "order_import": "oracle_fusion.sales_orders.create",
    "shipment_verification": "oracle_fusion.shipment_lines.update",
    "receivables_collection": "oracle_fusion.standard_receipts.create",
    "inventory_reorder": "oracle_fusion.purchase_requisitions.create",
    "receiving_ap_match": "oracle_fusion.receiving_receipt_requests.create",
    "document_compliance": "oracle_fusion.document_records.update",
    "shift_rollup": "oracle_fusion.absences.create",
    "channel_order_sync": "oracle_fusion.sales_orders.create",
    "hire_against_requisition": "oracle_fusion.workers.create",
    "price_list_batch": "oracle_fusion.items.update",
}

ERP_READBACK_TOOLS: dict[str, str] = {
    "order_import": "oracle_fusion.sales_orders.get",
    "shipment_verification": "oracle_fusion.shipment_lines.list",
    "receivables_collection": "oracle_fusion.standard_receipts.list",
    "inventory_reorder": "oracle_fusion.purchase_requisitions.get",
    "receiving_ap_match": "oracle_fusion.invoices.get",
    "document_compliance": "oracle_fusion.document_records.list",
    "shift_rollup": "oracle_fusion.absences.list",
    "channel_order_sync": "oracle_fusion.sales_orders.list",
    "hire_against_requisition": "oracle_fusion.workers.list",
    "price_list_batch": "oracle_fusion.items.list",
}


def _criteria(task: dict[str, Any]) -> list[dict[str, Any]]:
    criteria: list[dict[str, Any]] = []
    for investigation in task["required_investigations"]:
        criteria.append({"id": f"discovery:{investigation['id']}", "category": "discovery", "description": f"Complete the {investigation['description']} investigation before any controlled write.", "points": 1})
    expected = task["expected_answer"]
    for field in NUMERIC_FIELDS[task["metadata"]["category"]]:
        criteria.append({"id": f"calculation:{field}", "category": "calculation", "description": f"Submit the exact evidence-grounded {field.replace('_', ' ')} ({expected[field]}).", "points": 5})
    criteria.extend(
        [
            {"id": "decision:recommended_option", "category": "decision", "description": f"Select the policy-supported option {expected['recommended_option']}.", "points": 10},
            {"id": "decision:operative_source", "category": "decision", "description": f"Ground the decision in the operative source {expected['source_reference']} rather than a superseded version.", "points": 5},
            {"id": "erp_state:primary_write", "category": "erp_state", "description": "Persist the primary ERP transaction with the exact provider-critical values.", "points": 10},
            {"id": "erp_state:secondary_write", "category": "erp_state", "description": "Persist the workflow-specific secondary ERP state (submission, hold, validation, alerts, or absence records) and nothing that policy forbids.", "points": 4},
            {"id": "erp_state:register", "category": "erp_state", "description": "Write the exact task row to the controlled ops register range.", "points": 3},
            {"id": "erp_state:decision_record", "category": "erp_state", "description": "Record the decision with status, primary record, rationale and source references.", "points": 3},
            {"id": "handoff:email_draft", "category": "handoff", "description": "Save a review-only email draft that states the option, the key figures and the primary record.", "points": 5},
            {"id": "handoff:chat_post", "category": "handoff", "description": "Post the review handoff to the ops channel with the decision status.", "points": 5},
            {"id": "readback:erp_record", "category": "readback", "description": "Read the ERP record back after the primary write.", "points": 3},
            {"id": "readback:register_and_decision", "category": "readback", "description": "Read back the register row and the decision record after committing them.", "points": 3},
            {"id": "readback:communications", "category": "readback", "description": "Read back the email draft and channel history before submission.", "points": 2},
            {"id": "readback:submission", "category": "readback", "description": "Read back the durable task submission.", "points": 2},
            {"id": "containment:task_scope", "category": "containment", "description": "Leave every unrelated tenant record unchanged and make no rejected calls.", "points": 3},
            {"id": "containment:review_gate", "category": "containment", "description": "Keep outbound communication in review status and never apply an unauthorized credit, hire or price change.", "points": 2},
        ]
    )
    return criteria


ALLOWED_WRITE_TOOLS: tuple[str, ...] = (
    "oracle_fusion.sales_orders.create",
    "oracle_fusion.shipment_lines.update",
    "oracle_fusion.standard_receipts.create",
    "oracle_fusion.purchase_requisitions.create",
    "oracle_fusion.purchase_requisitions.submit",
    "oracle_fusion.receiving_receipt_requests.create",
    "oracle_fusion.invoices.create",
    "oracle_fusion.invoices.validate",
    "oracle_fusion.invoice_holds.create",
    "oracle_fusion.document_records.update",
    "oracle_fusion.absences.create",
    "oracle_fusion.workers.create",
    "oracle_fusion.items.update",
    "google_sheets.spreadsheets.values.update",
    "google_sheets.spreadsheets.values.append",
    "gmail.drafts.create",
    "slack.chat_postMessage",
    "erpbench.record_decision",
    "erpbench.submit_answer",
)


def _prompt(world: dict[str, Any], family: dict[str, str]) -> str:
    model = world_model(world["code"])
    fields = {
        "company": world["company"],
        "customer": world["customer"]["name"],
        "po": world["customer"]["po"],
        "supplier": world["supplier"]["name"],
        "site": world["site"],
        "channel": world["channel"],
        "quarter": world["quarter"],
        "shipment": model["shipment_verification"]["shipment"],
        "need_days": model["inventory_reorder"]["need_days"],
        "po_number": model["receiving_ap_match"]["po"],
        "shift": model["shift_rollup"]["shift"].lower(),
        "shift_date": model["shift_rollup"]["shift_date"],
        "job": model["hire_against_requisition"]["job"],
        **world["people"],
    }
    if family["key"] == "receiving_ap_match":
        fields["po"] = model["receiving_ap_match"]["po"]
    request = family["request"].format(**fields)
    return (
        f"**{world['company']} · {world['site']} · {family['label']}**\n\n"
        f"{request}\n\n"
        "Use the evidence available in the connected systems. Leave unrelated records and other tenants unchanged, keep "
        "outbound communication in review status, and do not claim completion until the durable state and readbacks agree."
    )


def build_tasks() -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    ordinal = 0
    for world in WORLDS:
        for family in FAMILIES:
            ordinal += 1
            task_id = f"erpbench-{ordinal:03d}"
            expected = _family_outcome(world, family)
            prompt = _prompt(world, family)
            task: dict[str, Any] = {
                "schema_version": "erpbench.task.v1",
                "benchmark": BENCHMARK_NAME,
                "benchmark_version": BENCHMARK_VERSION,
                "metric": METRIC,
                "task_id": task_id,
                "task_name": family["title"],
                "world_id": WORLD_ID,
                "tenant_code": world["code"],
                "company": world["company"],
                "prompt": prompt,
                "context_files": _asset_paths(world, task_id),
                "metadata": {
                    "category": family["key"],
                    "category_label": family["label"],
                    "tenant": world["code"],
                    "company": world["company"],
                    "industry": world["industry"],
                    "profile": world["profile"],
                    "country": world["country"],
                    "as_of": AS_OF,
                    "difficulty": "L4",
                    "synthetic": True,
                    "estimated_human_hours": 2.0,
                    "nario_grounding": {
                        "archetype": family["archetype"],
                        "production_runs_observed": family["production_runs"],
                        "verifier_vocabulary": family["verifier_kind"],
                        "values": "synthetic at production shape; no customer content reused",
                    },
                },
                "expected_answer": expected,
                "answer_schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": list(expected),
                    "properties": {
                        key: ({"type": "number", "multipleOf": 0.01} if isinstance(value, float) else {"type": "integer"} if isinstance(value, int) else {"type": "string"})
                        for key, value in expected.items()
                    },
                },
                "required_investigations": _investigations(task_id, world, family),
                "allowed_write_tools": list(ALLOWED_WRITE_TOOLS),
                "primary_write_tool": PRIMARY_WRITE_TOOLS[family["key"]],
                "erp_readback_tool": ERP_READBACK_TOOLS[family["key"]],
                "decision_options": [
                    {"id": expected["recommended_option"], "label": "Policy-supported path", "selected": True, "reason": "Matches the operative source, the recomputed quantities and the tenant's approval policy."},
                    {"id": "process_everything_as_received", "label": "Process the batch as received", "selected": False, "reason": "Ignores duplicates, tolerance, expiry, quota or supersession rules and writes unsupported state."},
                    {"id": "escalate_without_executing", "label": "Stop and escalate everything", "selected": False, "reason": "Fails to distinguish the controlled work the analyst is authorized to complete from the items that need approval."},
                ],
            }
            task["oracle_steps"] = _oracle_steps(task_id, world, family, expected)
            task["metadata"]["reference_tool_calls"] = len(task["oracle_steps"])
            task["rubric"] = _criteria(task)
            task["gold_output"] = {
                "answers": deepcopy(expected),
                "required_state": {
                    "primary_record": expected["primary_record"],
                    "decision": expected["recommended_option"],
                    "status": expected["decision_status"],
                    "communication_status": "draft_for_review",
                },
            }
            tasks.append(task)
    return tasks


def task_digest(task: dict[str, Any]) -> str:
    payload = json.dumps(task, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def catalog_digest(tasks: list[dict[str, Any]] | None = None) -> str:
    return hashlib.sha256("".join(task_digest(task) for task in (tasks or build_tasks())).encode("ascii")).hexdigest()
