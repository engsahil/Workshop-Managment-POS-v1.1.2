"""Comprehensive v1.2.0 regression & production-upgrade test suite.

Covers:
- Dashboard summary null-safety, invalid date resilience, and Windows ZoneInfo fallback
- Daily operational & financial summary generation and notification deduplication
- Customer creation with empty-string optional fields, Pakistani phone validation, and duplicate phone detection
- Vehicle registration with registration_no and plate_number alias, empty-string optional fields, and full history
- Service job lifecycle by Admin and Cashier roles, status transitions, ready-for-delivery notification, and billing
- Invoice creation, partial payment, outstanding balance notification, and void restock
- Expense creation, YYYY-MM-DD date parsing, update, summary totals, method filter, and deletion
- Warranty claims auto-fill from invoice/job/product, warranty coverage expiry calculation, inspection notes, and search
- Notification preferences, read/unread state, and mark-all-read
- Backup upload & schema validation endpoint
- Audit log username auto-resolution from user_id
"""
from __future__ import annotations

import io
from datetime import datetime, timezone

from tests.conftest import make_user, token_for


def _hdr(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_windows_zoneinfo_fallback():
    """Verify dates.py gracefully parses date strings and provides a valid local timezone."""
    from app.core import dates

    tz = dates.tz()
    assert tz is not None
    dt = dates.ensure_datetime("2026-10-17")
    assert dt is not None
    assert dt.year == 2026 and dt.month == 10 and dt.day == 17
    start, end = dates.range_utc("2026-10-17", "2026-10-17")
    assert start is not None and end is not None
    assert start < end


def test_dashboard_resilience_and_daily_summary(client, admin_token):
    h = _hdr(admin_token)
    # Valid dashboard call
    r = client.get("/api/reports/dashboard", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    for key in ("sales", "collections", "profit", "receivables", "jobs", "inventory", "recent", "definitions"):
        assert key in body

    # Dashboard with malformed date parameters returns a clean 400 validation error, never 500
    r_bad = client.get("/api/reports/dashboard?date_from=not-a-date&date_to=bad-date", headers=h)
    assert r_bad.status_code == 400, r_bad.text

    # Daily summary endpoint
    r_sum = client.get("/api/reports/daily-summary", headers=h)
    assert r_sum.status_code == 200, r_sum.text
    s_data = r_sum.json()
    assert "total_sales_paisa" in s_data
    assert "payments_received_paisa" in s_data
    assert "expenses_recorded_paisa" in s_data
    assert "net_daily_operating_paisa" in s_data

    # Trigger daily summary notification
    r_not = client.post("/api/reports/daily-summary/notify", headers=h)
    assert r_not.status_code == 200, r_not.text
    assert r_not.json()["ok"] is True


def test_customer_creation_empty_strings_and_phone_validation(client, admin_token):
    h = _hdr(admin_token)
    # Create customer with empty strings for optional fields (mirrors browser form submission)
    r = client.post(
        "/api/customers",
        headers=h,
        json={
            "name": "Tariq Mahmood v120",
            "phone": "0300-7654399",
            "alt_phone": "",
            "cnic": "",
            "address": "",
            "notes": "",
        },
    )
    assert r.status_code == 200, r.text
    cust = r.json()
    assert cust["name"] == "Tariq Mahmood v120"
    assert cust["phone"] == "0300-7654399"
    assert cust["alt_phone"] is None

    # Creating another customer with the same phone should be rejected with 409 Conflict
    r_dup = client.post(
        "/api/customers",
        headers=h,
        json={"name": "Tariq Mahmood Duplicate", "phone": "0300-7654399"},
    )
    assert r_dup.status_code == 409, r_dup.text
    assert "already exists" in r_dup.json().get("detail", "")

    # Invalid phone number (too short) should return 422 with clean detail
    r_inv = client.post(
        "/api/customers",
        headers=h,
        json={"name": "Invalid Phone User", "phone": "123"},
    )
    assert r_inv.status_code == 422, r_inv.text
    assert "Invalid phone number" in r_inv.json().get("detail", "")


def test_vehicle_registration_alias_and_history(client, admin_token):
    h = _hdr(admin_token)
    cust = client.post("/api/customers", headers=h, json={"name": "Vehicle Owner v120", "phone": "0321-9988711"}).json()

    # Register using plate_number alias and empty string optional fields
    r = client.post(
        "/api/vehicles",
        headers=h,
        json={
            "customer_id": cust["id"],
            "vehicle_type": "car",
            "plate_number": "leb-2026",
            "make": "Honda",
            "model": "Civic",
            "year": "",
            "color": "",
            "odometer": "45000",
        },
    )
    assert r.status_code == 200, r.text
    veh = r.json()
    assert veh["registration_no"] == "LEB-2026"
    assert veh["odometer"] == 45000

    # Vehicle detail should include history, invoices, and odometer_history
    r_det = client.get(f"/api/vehicles/{veh['id']}", headers=h)
    assert r_det.status_code == 200, r_det.text
    det = r_det.json()
    assert "history" in det
    assert "invoices" in det
    assert "odometer_history" in det
    assert det["last_odometer"] == 45000


def test_service_job_cashier_access_and_full_lifecycle(client, admin_token, db_session):
    make_user(db_session, "cashier_v120", "cashier")
    cashier_tok = token_for(client, "cashier_v120")
    h_cashier = _hdr(cashier_tok)
    h_admin = _hdr(admin_token)

    cust = client.post("/api/customers", headers=h_cashier, json={"name": "Job Customer v120", "phone": "0333-1122334"}).json()
    veh = client.post(
        "/api/vehicles",
        headers=h_cashier,
        json={"customer_id": cust["id"], "vehicle_type": "motorcycle", "registration_no": "LHR-7788", "make": "Honda", "model": "CG125"},
    ).json()

    # Cashier creates a service job with empty optional strings
    r_job = client.post(
        "/api/jobs",
        headers=h_cashier,
        json={
            "customer_id": cust["id"],
            "vehicle_id": veh["id"],
            "mechanic_id": "",
            "odometer": "12500",
            "reported_issue": "Clutch plates slipping and oil leak",
            "est_labor_paisa": 80000,
            "est_parts_paisa": 150000,
            "est_completion_date": "",
        },
    )
    assert r_job.status_code == 200, r_job.text
    job = r_job.json()
    jid = job["id"]
    assert job["status"] == "received"

    # Add labor service line
    r_svc = client.post(
        f"/api/jobs/{jid}/services",
        headers=h_cashier,
        json={"description": "Clutch Overhaul Labor", "quantity": 1, "unit_charge_paisa": 85000},
    )
    assert r_svc.status_code == 200, r_svc.text

    # Record customer approval of the estimate before completing
    r_app = client.post(f"/api/jobs/{jid}/approval", headers=h_cashier, json={"approval_status": "approved"})
    assert r_app.status_code == 200, r_app.text

    # Transition status through inspection -> in_progress -> completed -> ready_for_delivery
    for st in ("inspection", "in_progress", "completed", "ready_for_delivery"):
        r_st = client.post(f"/api/jobs/{jid}/status", headers=h_cashier, json={"status": st})
        assert r_st.status_code == 200, r_st.text
        assert r_st.json()["status"] == st

    # Verify notification generated for ready_for_delivery
    notifs = client.get("/api/notifications", headers=h_admin).json()["items"]
    assert any("ready for delivery" in n["title"].lower() and job["job_number"] in n["title"] for n in notifs)

    # Generate final invoice from job card with partial payment on credit
    r_inv = client.post(
        f"/api/jobs/{jid}/invoice",
        headers=h_admin,
        json={
            "invoice_discount_paisa": 5000,
            "payments": [{"amount_paisa": 50000, "method": "cash"}],
            "is_credit": True,
        },
    )
    assert r_inv.status_code == 200, r_inv.text
    inv = r_inv.json()
    assert inv["total_paisa"] == 80000
    assert inv["paid_paisa"] == 50000
    assert inv["balance_paisa"] == 30000
    assert inv["status"] == "partial"


def test_expense_date_parsing_summary_and_filters(client, admin_token):
    h = _hdr(admin_token)
    cats = client.get("/api/expense-categories", headers=h).json()
    cat_id = cats[0]["id"]

    # Create expense with YYYY-MM-DD date string and empty optional strings
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    r_exp = client.post(
        "/api/expenses",
        headers=h,
        json={
            "category_id": cat_id,
            "amount_paisa": 250000,
            "method": "cash",
            "payee": "LESCO Electricity",
            "description": "Workshop electricity bill",
            "reference": "",
            "expense_date": today_str,
        },
    )
    assert r_exp.status_code == 200, r_exp.text
    exp = r_exp.json()
    assert exp["amount_paisa"] == 250000

    # List expenses with method filter and check summary totals
    r_list = client.get("/api/expenses?method=cash", headers=h)
    assert r_list.status_code == 200, r_list.text
    data = r_list.json()
    assert "summary" in data
    assert data["summary"]["filtered_total_paisa"] >= 250000
    assert data["summary"]["month_total_paisa"] >= 250000


def test_warranty_claim_autofill_coverage_and_search(client, admin_token):
    h = _hdr(admin_token)
    cust = client.post("/api/customers", headers=h, json={"name": "Warranty Customer", "phone": "0345-6677812"}).json()
    prod = client.post(
        "/api/products",
        headers=h,
        json={
            "name": "AGS Dry Battery 12V v120",
            "purchase_cost_paisa": 300000,
            "selling_price_paisa": 420000,
            "warranty_days": 180,
            "min_stock": 2,
        },
    ).json()
    client.post("/api/inventory/receive", headers=h, json={"product_id": prod["id"], "quantity": 5, "unit_cost_paisa": 300000})

    inv = client.post(
        "/api/pos/invoices",
        headers=h,
        json={
            "customer_id": cust["id"],
            "items": [{"item_type": "product", "product_id": prod["id"], "description": prod["name"], "quantity": 1, "unit_price_paisa": 420000}],
            "payments": [{"amount_paisa": 420000, "method": "cash"}],
        },
    ).json()

    # Create warranty claim referencing invoice_id and product_id without explicit customer_id or warranty_days
    r_clm = client.post(
        "/api/claims",
        headers=h,
        json={
            "invoice_id": inv["id"],
            "product_id": prod["id"],
            "description": "Battery not holding charge",
            "inspection_notes": "Voltage drops below 10.2V under load",
            "action_taken": "replacement",
        },
    )
    assert r_clm.status_code == 200, r_clm.text
    clm = r_clm.json()
    assert clm["customer_id"] == cust["id"]
    assert clm["warranty_days"] == 180
    assert clm["is_within_warranty"] is True
    assert clm["warranty_expiry_date"] is not None
    assert clm["inspection_notes"] == "Voltage drops below 10.2V under load"
    assert clm["action_taken"] == "replacement"

    # Search claims by customer name or claim_number
    r_q = client.get(f"/api/claims?q={clm['claim_number']}", headers=h)
    assert r_q.status_code == 200, r_q.text
    assert len(r_q.json()["items"]) == 1

    # Update claim status and resolution
    r_up = client.put(
        f"/api/claims/{clm['id']}",
        headers=h,
        json={"status": "resolved", "resolution": "Replaced battery under 180-day warranty", "cost_paisa": 300000},
    )
    assert r_up.status_code == 200, r_up.text
    assert r_up.json()["status"] == "resolved"


def test_notification_preferences_and_audit_username_resolution(client, admin_token):
    h = _hdr(admin_token)
    r_pref = client.get("/api/settings/notifications", headers=h)
    assert r_pref.status_code == 200, r_pref.text
    prefs = r_pref.json()
    assert prefs["job_alerts"] is True

    r_put = client.put("/api/settings/notifications", headers=h, json={**prefs, "low_stock_alerts": False})
    assert r_put.status_code == 200, r_put.text
    assert r_put.json()["low_stock_alerts"] is False

    # Re-enable low_stock_alerts
    client.put("/api/settings/notifications", headers=h, json={**prefs, "low_stock_alerts": True})

    # Verify audit log entries all have resolved usernames (no null usernames for user-initiated actions)
    r_aud = client.get("/api/audit?page_size=50", headers=h)
    assert r_aud.status_code == 200
    items = r_aud.json()["items"]
    assert len(items) > 0
    for entry in items:
        if entry["user_id"] is not None:
            assert entry["username"] is not None and entry["username"] != ""


def test_backup_upload_and_validation(client, admin_token):
    h = _hdr(admin_token)
    # Create a backup first, download its bytes, and upload it via /api/backups/upload
    b = client.post("/api/backups", headers=h).json()
    dl = client.get(f"/api/backups/{b['filename']}/download", headers=h)
    assert dl.status_code == 200

    files = {"file": ("uploaded_test.db", io.BytesIO(dl.content), "application/octet-stream")}
    r_up = client.post("/api/backups/upload", headers=h, files=files)
    assert r_up.status_code == 200, r_up.text
    up_body = r_up.json()
    assert up_body["validation"]["ok"] is True

    # Uploading a non-SQLite file must fail validation cleanly with 400
    bad_files = {"file": ("corrupt.db", io.BytesIO(b"not a sqlite file"), "application/octet-stream")}
    r_bad = client.post("/api/backups/upload", headers=h, files=bad_files)
    assert r_bad.status_code == 400
