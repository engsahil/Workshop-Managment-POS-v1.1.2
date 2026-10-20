"""Regression tests for the defects found during the full POS audit."""
from datetime import date

from conftest import make_user, token_for


def _hdr(token):
    return {"Authorization": f"Bearer {token}"}


def _product(client, auth, name, sku, price=10000, cost=5000):
    r = client.post("/api/products", headers=auth, json={
        "name": name, "sku": sku, "selling_price_paisa": price,
        "purchase_cost_paisa": cost})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _receive(client, auth, pid, qty, ref=None):
    r = client.post("/api/inventory/receive", headers=auth, json={
        "product_id": pid, "quantity": qty, "unit_cost_paisa": 5000,
        "reference_number": ref})
    assert r.status_code == 200, r.text


def _cash_invoice(client, headers, pid, qty=1, price=10000):
    r = client.post("/api/pos/invoices", headers=headers, json={
        "items": [{"item_type": "product", "product_id": pid,
                   "quantity": qty, "unit_price_paisa": price}],
        "payments": [{"amount_paisa": price * qty, "method": "cash"}]})
    assert r.status_code == 200, r.text
    return r.json()


def test_adjust_stock_respects_negative_stock_policy(client, auth):
    pid = _product(client, auth, "Audit NoStock Part", "AUD-NOSTOCK")
    r = client.post("/api/inventory/adjust", headers=auth, json={
        "product_id": pid, "delta": -1, "movement_type": "adjust",
        "reason": "audit test"})
    assert r.status_code == 400
    assert "Insufficient stock" in r.json()["detail"]
    assert client.get(f"/api/products/{pid}", headers=auth).json()["quantity_on_hand"] == 0


def test_manual_receive_is_labelled_manual_not_purchase(client, auth):
    pid = _product(client, auth, "Audit Manual Receive", "AUD-MANUAL")
    _receive(client, auth, pid, 2, ref="GRN-MANUAL-1")
    p = client.get(f"/api/products/{pid}", headers=auth).json()
    movement = p["movements"][0]
    assert movement["movement_type"] == "receive"
    assert movement["reference_type"] == "manual_receive"


def test_duplicate_vehicle_registration_rejected(client, auth):
    cid = client.post("/api/customers", headers=auth, json={
        "name": "Audit Duplicate Vehicle", "phone": "03004000001"}).json()["id"]
    payload = {"customer_id": cid, "registration_no": "leB-1234",
               "make": "Honda", "model": "CD70"}
    r = client.post("/api/vehicles", headers=auth, json=payload)
    assert r.status_code == 200, r.text
    payload["registration_no"] = "leb-1234"
    r = client.post("/api/vehicles", headers=auth, json=payload)
    assert r.status_code == 400
    assert "already registered" in r.json()["detail"]


def test_cashier_cannot_mutate_catalog_or_stock(client, db_session):
    make_user(db_session, "audit_cashier", "cashier")
    h = _hdr(token_for(client, "audit_cashier"))
    assert client.post("/api/products", headers=h, json={
        "name": "Nope", "selling_price_paisa": 100}).status_code == 403
    assert client.post("/api/categories", headers=h, json={
        "name": "Nope"}).status_code == 403
    assert client.post("/api/services", headers=h, json={
        "name": "Nope", "code": "NOPE-1"}).status_code == 403
    assert client.post("/api/mechanics", headers=h, json={
        "name": "Nope"}).status_code == 403
    assert client.post("/api/inventory/receive", headers=h, json={
        "product_id": 1, "quantity": 1}).status_code == 403
    assert client.get("/api/expenses", headers=h).status_code == 403


def test_cashier_shift_ledger_is_limited_to_own_shift(client, db_session):
    make_user(db_session, "audit_shift_a", "cashier")
    make_user(db_session, "audit_shift_b", "cashier")
    ha = _hdr(token_for(client, "audit_shift_a"))
    hb = _hdr(token_for(client, "audit_shift_b"))
    a = client.post("/api/shifts/open", headers=ha, json={
        "opening_cash_paisa": 10000, "notes": "till A"}).json()
    b = client.post("/api/shifts/open", headers=hb, json={
        "opening_cash_paisa": 20000}).json()
    assert a["opening_notes"] == "till A"
    r = client.get(f"/api/shifts/{a['id']}/ledger", headers=ha)
    assert r.status_code == 200
    r = client.get(f"/api/shifts/{b['id']}/ledger", headers=ha)
    assert r.status_code == 403


def test_shift_expected_cash_includes_cash_expense_and_sale(client, db_session, auth):
    make_user(db_session, "audit_shift_mgr", "manager")
    hm = _hdr(token_for(client, "audit_shift_mgr"))
    cat = client.post("/api/expense-categories", headers=hm, json={
        "name": "Audit Shift Expenses"}).json()["id"]
    shift = client.post("/api/shifts/open", headers=hm, json={
        "opening_cash_paisa": 50000}).json()
    r = client.post("/api/expenses", headers=hm, json={
        "category_id": cat, "amount_paisa": 5000, "method": "cash",
        "description": "audit shift expense"})
    assert r.status_code == 200, r.text
    pid = _product(client, auth, "Audit Shift Sale", "AUD-SHIFT-SALE")
    _receive(client, auth, pid, 2)
    _cash_invoice(client, hm, pid, 1, 10000)
    cur = client.get("/api/shifts/current", headers=hm).json()
    assert cur["id"] == shift["id"]
    assert cur["expected_cash_paisa"] == 50000 - 5000 + 10000
    ledger = client.get(f"/api/shifts/{shift['id']}/ledger", headers=hm).json()
    assert any(e["amount_paisa"] == 5000 for e in ledger["expenses"])


def test_last_admin_cannot_be_demoted(client, auth):
    me = client.get("/api/auth/me", headers=auth).json()
    r = client.put(f"/api/users/{me['id']}", headers=auth, json={"role": "cashier"})
    assert r.status_code == 400
    assert "administrator must remain" in r.json()["detail"].lower()
    assert client.get("/api/auth/me", headers=auth).json()["role"] == "admin"


def test_sales_by_brand_and_invalid_dimension(client, auth):
    brand = client.post("/api/brands", headers=auth, json={
        "name": "AuditBrand"}).json()
    pid = client.post("/api/products", headers=auth, json={
        "name": "Audit Brand Part", "sku": "AUD-BRAND",
        "brand_id": brand["id"], "selling_price_paisa": 20000,
        "purchase_cost_paisa": 9000}).json()["id"]
    _receive(client, auth, pid, 2)
    _cash_invoice(client, auth, pid, 1, 20000)
    today = date.today().isoformat()
    r = client.get(f"/api/reports/sales-by/brand?date_from={today}&date_to={today}",
                   headers=auth)
    assert r.status_code == 200
    assert any(row["name"] == "AuditBrand" for row in r.json())
    r = client.get("/api/reports/sales-by/not-a-dimension", headers=auth)
    assert r.status_code == 400


def test_dashboard_reports_refunds(client, auth):
    pid = _product(client, auth, "Audit Refund Part", "AUD-REFUND", price=12000)
    _receive(client, auth, pid, 3)
    inv = _cash_invoice(client, auth, pid, 1, 12000)
    item_id = inv["items"][0]["id"]
    before = client.get("/api/reports/dashboard", headers=auth).json()
    r = client.post("/api/invoices/returns", headers=auth, json={
        "invoice_id": inv["id"],
        "items": [{"invoice_item_id": item_id, "quantity": 1}],
        "restock_action": "restock", "refund_method": "cash"})
    assert r.status_code == 200, r.text
    rid = r.json()["id"]
    r = client.post(f"/api/invoices/returns/{rid}/decide", headers=auth,
                    json={"status": "approved"})
    assert r.status_code == 200, r.text
    after = client.get("/api/reports/dashboard", headers=auth).json()
    assert after["sales"]["refunds_paisa"] - before["sales"]["refunds_paisa"] == 12000
    assert after["collections"]["total_paisa"] == before["collections"]["total_paisa"]
    assert (after["collections"]["refunds_paisa"]
            - before["collections"]["refunds_paisa"]) == 12000
    assert (after["collections"]["net_paisa"]
            == after["collections"]["total_paisa"] - after["collections"]["refunds_paisa"])
    inv_after = client.get(f"/api/invoices/{inv['id']}", headers=auth).json()
    assert inv_after["balance_paisa"] == 0
    # and the return row now carries the refund split used by customer balances
    rows = client.get("/api/invoices/returns", headers=auth).json()["items"]
    row = next(x for x in rows if x["id"] == rid)
    assert row["refund_amount_paisa"] == 12000
    assert row["credit_amount_paisa"] == 0


def test_void_blocked_after_return(client, auth):
    pid = _product(client, auth, "Audit Void Return", "AUD-VOID-RET")
    _receive(client, auth, pid, 2)
    inv = _cash_invoice(client, auth, pid, 1, 10000)
    rid = client.post("/api/invoices/returns", headers=auth, json={
        "invoice_id": inv["id"],
        "items": [{"invoice_item_id": inv["items"][0]["id"], "quantity": 1}],
        "refund_method": "cash"}).json()["id"]
    client.post(f"/api/invoices/returns/{rid}/decide", headers=auth,
                json={"status": "approved"})
    r = client.post(f"/api/invoices/{inv['id']}/void", headers=auth,
                    json={"reason": "audit"})
    assert r.status_code == 400
    assert "returns" in r.json()["detail"].lower()


def test_unlinked_purchase_return_respects_total_received(client, auth):
    sup = client.post("/api/suppliers", headers=auth, json={
        "name": "Audit Return Supplier"}).json()
    pid = _product(client, auth, "Audit PR Part", "AUD-PR")
    po = client.post("/api/purchases", headers=auth, json={
        "supplier_id": sup["id"],
        "items": [{"product_id": pid, "quantity": 5, "unit_cost_paisa": 5000}]}).json()
    client.post(f"/api/purchases/{po['id']}/receive", headers=auth, json={})
    r = client.post("/api/purchase-returns", headers=auth, json={
        "supplier_id": sup["id"],
        "items": [{"product_id": pid, "quantity": 6}]})
    assert r.status_code == 400
    r = client.post("/api/purchase-returns", headers=auth, json={
        "supplier_id": sup["id"],
        "items": [{"product_id": pid, "quantity": 2}]})
    assert r.status_code == 200, r.text
    r = client.post("/api/purchase-returns", headers=auth, json={
        "supplier_id": sup["id"],
        "items": [{"product_id": pid, "quantity": 4}]})
    assert r.status_code == 400


def test_daily_summary_aliases_and_for_date(client, auth):
    r = client.get("/api/notifications/daily-summary?for_date=2020-01-01",
                   headers=auth)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["date"] == "2020-01-01"
    for key in ("invoices_count", "sales_total_paisa", "credit_sales_count",
                "credit_sales_paisa", "collected_paisa", "expenses_total_paisa",
                "net_cash_flow_paisa", "jobs_completed_count",
                "out_of_stock_count", "refunds_paisa"):
        assert key in body
    assert body["invoices_count"] == 0
    assert body["sales_total_paisa"] == 0


def test_mechanic_cannot_read_financial_reports(client, db_session):
    make_user(db_session, "audit_mechanic", "mechanic")
    h = _hdr(token_for(client, "audit_mechanic"))
    assert client.get("/api/reports/dashboard", headers=h).status_code == 403
    assert client.get("/api/reports/profit", headers=h).status_code == 403
    assert client.get("/api/jobs", headers=h).status_code == 200
    assert client.get("/api/notifications/daily-summary",
                      headers=h).status_code == 403
    assert client.get("/api/reports/daily-summary", headers=h).status_code == 403


# ------------------------------------------------------------------ batch 6/7
def test_refund_cannot_exceed_amount_collected(client, auth):
    pid = _product(client, auth, "Audit Credit Refund", "AUD-CREDIT-REF",
                   price=10000, cost=4000)
    _receive(client, auth, pid, 2)
    cid = client.post("/api/customers", headers=auth, json={
        "name": "Audit Credit Refund Cust", "phone": "03004000002"}).json()["id"]
    inv = client.post("/api/pos/invoices", headers=auth, json={
        "customer_id": cid,
        "items": [{"item_type": "product", "product_id": pid,
                   "quantity": 1, "unit_price_paisa": 10000}],
        "payments": []}).json()
    assert inv["paid_paisa"] == 0
    line_id = inv["items"][0]["id"]
    ret = client.post("/api/invoices/returns", headers=auth, json={
        "invoice_id": inv["id"],
        "items": [{"invoice_item_id": line_id, "quantity": 1}],
        "refund_method": "cash"}).json()
    r = client.post(f"/api/invoices/returns/{ret['id']}/decide", headers=auth,
                    json={"status": "approved"})
    assert r.status_code == 400
    assert "credit return" in r.json()["detail"].lower()
    # the failed decision must not have been half-applied
    row = next(x for x in client.get("/api/invoices/returns", headers=auth)
               .json()["items"] if x["id"] == ret["id"])
    assert row["status"] == "pending"
    # the same return approved as store credit is accepted
    ret2 = client.post("/api/invoices/returns", headers=auth, json={
        "invoice_id": inv["id"],
        "items": [{"invoice_item_id": line_id, "quantity": 1}],
        "refund_method": "credit"}).json()
    r = client.post(f"/api/invoices/returns/{ret2['id']}/decide", headers=auth,
                    json={"status": "approved"})
    assert r.status_code == 200, r.text
    inv_after = client.get(f"/api/invoices/{inv['id']}", headers=auth).json()
    assert inv_after["credited_amount_paisa"] == 10000


def test_fractional_product_quantity_rejected_without_stock_change(client, auth):
    pid = _product(client, auth, "Audit Fractional Part", "AUD-FRACTION")
    _receive(client, auth, pid, 3)
    r = client.post("/api/pos/invoices", headers=auth, json={
        "items": [{"item_type": "product", "product_id": pid,
                   "quantity": 1.5, "unit_price_paisa": 10000}],
        "payments": [{"amount_paisa": 15000, "method": "cash"}]})
    assert r.status_code == 400
    assert "whole units" in r.json()["detail"]
    assert client.get(f"/api/products/{pid}",
                      headers=auth).json()["quantity_on_hand"] == 3


def test_supplier_statement_agrees_with_supplier_balance(client, auth, db_session):
    from app.models import PurchaseReturn

    sup = client.post("/api/suppliers", headers=auth, json={
        "name": "Audit Ledger Supplier"}).json()
    pid = _product(client, auth, "Audit Ledger Part", "AUD-LEDGER")
    po = client.post("/api/purchases", headers=auth, json={
        "supplier_id": sup["id"],
        "items": [{"product_id": pid, "quantity": 10,
                   "unit_cost_paisa": 5000}]}).json()
    client.post(f"/api/purchases/{po['id']}/receive", headers=auth, json={})
    client.post(f"/api/purchases/{po['id']}/payments", headers=auth, json={
        "amount_paisa": 20000, "method": "cash"})
    client.post("/api/purchase-returns", headers=auth, json={
        "supplier_id": sup["id"],
        "items": [{"product_id": pid, "quantity": 2}]})
    cancelled = client.post("/api/purchases", headers=auth, json={
        "supplier_id": sup["id"],
        "items": [{"product_id": pid, "quantity": 1,
                   "unit_cost_paisa": 5000}]}).json()
    client.post(f"/api/purchases/{cancelled['id']}/cancel", headers=auth)
    # a pending return is listed but must not move the balance
    db_session.add(PurchaseReturn(return_number="AUD-PENDING-RET",
                                  supplier_id=sup["id"], total_paisa=5000,
                                  status="pending"))
    db_session.commit()

    balance = next(s for s in client.get("/api/suppliers", headers=auth).json()
                   if s["id"] == sup["id"])["balance_paisa"]
    assert balance == 50000 - 20000 - 10000
    stmt = client.get(f"/api/reports/supplier-statement/{sup['id']}",
                      headers=auth).json()
    assert sum(r["balance_impact"] for r in stmt["entries"]) == balance == stmt["balance_paisa"]
    pending = next(r for r in stmt["entries"] if r["ref"] == "AUD-PENDING-RET")
    assert pending["status"] == "pending" and pending["balance_impact"] == 0
    cancelled_row = next(r for r in stmt["entries"] if r["ref"] == cancelled["po_number"])
    assert cancelled_row["status"] == "cancelled"
    assert cancelled_row["balance_impact"] == 0


def test_job_service_validation_and_optional_description(client, auth):
    cust = client.post("/api/customers", headers=auth, json={
        "name": "Audit Job Service Cust", "phone": "03004000003"}).json()
    veh = client.post("/api/vehicles", headers=auth, json={
        "customer_id": cust["id"], "registration_no": "AUD-JS-1"}).json()
    svc = client.post("/api/services", headers=auth, json={
        "name": "Audit Tune Up", "code": "AUD-SVC-1",
        "default_charge_paisa": 4000}).json()
    job = client.post("/api/jobs", headers=auth, json={
        "customer_id": cust["id"], "vehicle_id": veh["id"],
        "reported_issue": "service line validation"}).json()

    r = client.post(f"/api/jobs/{job['id']}/services", headers=auth, json={
        "service_id": svc["id"], "quantity": 1, "unit_charge_paisa": 4000})
    assert r.status_code == 200, r.text
    detail = client.get(f"/api/jobs/{job['id']}", headers=auth).json()
    assert detail["services"][0]["description"] == "Audit Tune Up"
    line_id = detail["services"][0]["id"]

    # free-text lines still require a description
    r = client.post(f"/api/jobs/{job['id']}/services", headers=auth, json={
        "quantity": 1, "unit_charge_paisa": 1000})
    assert r.status_code == 400
    assert "description" in r.json()["detail"].lower()

    r = client.put(f"/api/jobs/services/{line_id}", headers=auth, json={
        "quantity": 0})
    assert r.status_code == 422  # schema rejects a zero quantity
    r = client.put(f"/api/jobs/services/{line_id}", headers=auth, json={
        "description": ""})
    assert r.status_code == 400
    assert "description" in r.json()["detail"].lower()
    # the failed updates did not change the line
    still = client.get(f"/api/jobs/{job['id']}", headers=auth).json()["services"][0]
    assert still["quantity"] == 1 and still["description"] == "Audit Tune Up"


def test_mechanic_commission_matches_reports_endpoint(client, auth):
    cust = client.post("/api/customers", headers=auth, json={
        "name": "Audit Commission Cust", "phone": "03004000004"}).json()
    veh = client.post("/api/vehicles", headers=auth, json={
        "customer_id": cust["id"], "registration_no": "AUD-COMM-1"}).json()
    mech = client.post("/api/mechanics", headers=auth, json={
        "name": "Audit Commission Mech",
        "commission_type": "percent_per_job",
        "commission_value": 1000}).json()  # 10.00 %
    job = client.post("/api/jobs", headers=auth, json={
        "customer_id": cust["id"], "vehicle_id": veh["id"],
        "reported_issue": "commission", "mechanic_id": mech["id"]}).json()
    client.post(f"/api/jobs/{job['id']}/services", headers=auth, json={
        "description": "Commission labor", "quantity": 1,
        "unit_charge_paisa": 5000, "mechanic_id": mech["id"]})
    client.post(f"/api/jobs/{job['id']}/status", headers=auth,
                json={"status": "inspection"})
    client.post(f"/api/jobs/{job['id']}/status", headers=auth,
                json={"status": "completed"})

    listed = next(m for m in client.get("/api/mechanics", headers=auth).json()
                  if m["id"] == mech["id"])
    perf = next(m for m in client.get("/api/reports/mechanic-performance",
                                      headers=auth).json()
                if m["mechanic_id"] == mech["id"])
    assert listed["commission_due_paisa"] == perf["commission_due_paisa"] == 500


def test_audit_log_honours_page_size(client, auth):
    client.post("/api/customers", headers=auth, json={
        "name": "Audit Page Cust", "phone": "03004000005"})
    r = client.get("/api/audit?page_size=1", headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert body["page_size"] == 1
    assert len(body["items"]) == 1
    r = client.get("/api/audit?page_size=9999", headers=auth)
    assert r.json()["page_size"] == 200


def test_business_settings_persist_receipt_fields(client, auth):
    payload = {"business_name": "Audit Workshop",
               "alt_phone": "03009999999", "tax_ntn": "NTN-1234567",
               "invoice_footer": "Warranty valid for 30 days"}
    r = client.put("/api/settings/business", headers=auth, json=payload)
    assert r.status_code == 200, r.text
    body = client.get("/api/settings/business", headers=auth).json()
    for key, value in payload.items():
        assert body[key] == value
    # receipt print data consumes the same values
    pid = _product(client, auth, "Audit Receipt Part", "AUD-RECEIPT")
    _receive(client, auth, pid, 1)
    inv = _cash_invoice(client, auth, pid, 1, 10000)
    receipt = client.get(f"/api/invoices/{inv['id']}/print-data",
                         headers=auth).json()
    assert receipt["business"]["tax_ntn"] == "NTN-1234567"
    assert receipt["business"]["invoice_footer"] == "Warranty valid for 30 days"


def test_utcnow_is_naive_utc():
    from datetime import datetime, timezone
    from app.core.security import utcnow
    now = utcnow()
    assert now.tzinfo is None
    delta = abs((now - datetime.now(timezone.utc).replace(tzinfo=None)).total_seconds())
    assert delta < 5


def test_stock_adjustment_validation(client, auth):
    pid = _product(client, auth, "Audit Adjust Guard", "AUD-ADJ-GUARD")
    _receive(client, auth, pid, 2)
    r = client.post("/api/inventory/adjust", headers=auth, json={
        "product_id": pid, "delta": 0, "movement_type": "adjust",
        "reason": "no-op"})
    assert r.status_code == 400
    assert "not be zero" in r.json()["detail"]
    r = client.post("/api/inventory/adjust", headers=auth, json={
        "product_id": pid, "delta": 1, "movement_type": "bogus",
        "reason": "typo"})
    assert r.status_code == 422
    assert client.get(f"/api/products/{pid}",
                      headers=auth).json()["quantity_on_hand"] == 2


def test_stocked_product_cannot_become_a_service(client, auth):
    pid = _product(client, auth, "Audit Convert Guard", "AUD-CONV")
    _receive(client, auth, pid, 1)
    r = client.put(f"/api/products/{pid}", headers=auth,
                   json={"is_service": True})
    assert r.status_code == 400
    assert "stock on hand" in r.json()["detail"]
    assert client.get(f"/api/products/{pid}",
                      headers=auth).json()["is_service"] is False


def test_claim_rejects_missing_references(client, auth):
    r = client.post("/api/claims", headers=auth, json={
        "customer_id": 999999, "description": "ghost customer"})
    assert r.status_code == 400
    r = client.post("/api/claims", headers=auth, json={
        "item_type": "banana", "description": "bad item type"})
    assert r.status_code == 422
    clm = client.post("/api/claims", headers=auth, json={
        "description": "valid claim"}).json()
    r = client.put(f"/api/claims/{clm['id']}", headers=auth,
                   json={"customer_id": 999999})
    assert r.status_code == 400
    assert client.get(f"/api/claims/{clm['id']}",
                      headers=auth).json()["customer_id"] is None


def test_mechanic_cannot_generate_job_invoice(client, db_session, auth):
    from conftest import make_user, token_for
    make_user(db_session, "audit_mech_billing", "mechanic")
    h = _hdr(token_for(client, "audit_mech_billing"))
    cust = client.post("/api/customers", headers=auth, json={
        "name": "Audit Mech Billing Cust", "phone": "03004000006"}).json()
    veh = client.post("/api/vehicles", headers=auth, json={
        "customer_id": cust["id"], "registration_no": "AUD-MECH-1"}).json()
    job = client.post("/api/jobs", headers=auth, json={
        "customer_id": cust["id"], "vehicle_id": veh["id"],
        "reported_issue": "billing permission"}).json()
    client.post(f"/api/jobs/{job['id']}/services", headers=auth, json={
        "description": "Audit labor", "quantity": 1, "unit_charge_paisa": 2000})
    r = client.post(f"/api/jobs/{job['id']}/invoice", headers=h, json={
        "payments": [{"amount_paisa": 2000, "method": "cash"}]})
    assert r.status_code == 403
    assert client.get(f"/api/jobs/{job['id']}",
                      headers=auth).json()["invoice_id"] is None


def test_duplicate_customer_phone_detected_across_formats(client, auth):
    a = client.post("/api/customers", headers=auth, json={
        "name": "Audit Phone A", "phone": "0300-1111111"})
    assert a.status_code == 200, a.text
    b = client.post("/api/customers", headers=auth, json={
        "name": "Audit Phone B", "phone": "03001111111"})
    assert b.status_code == 409
    other = client.post("/api/customers", headers=auth, json={
        "name": "Audit Phone C", "phone": "0300-2222222"})
    assert other.status_code == 200, other.text
    r = client.put(f"/api/customers/{other.json()['id']}", headers=auth,
                   json={"phone": "+92 300 1111111"})
    assert r.status_code == 409
    assert "+92" not in client.get(
        f"/api/customers/{other.json()['id']}", headers=auth).json()["phone"]


def test_cancelled_job_cannot_be_invoiced_and_stock_is_restored(client, auth):
    cust = client.post("/api/customers", headers=auth, json={
        "name": "Audit Cancel Cust", "phone": "03004000007"}).json()
    veh = client.post("/api/vehicles", headers=auth, json={
        "customer_id": cust["id"], "registration_no": "AUD-CANCEL-1"}).json()
    pid = _product(client, auth, "Audit Cancel Part", "AUD-CANCEL-PART")
    _receive(client, auth, pid, 3)
    job = client.post("/api/jobs", headers=auth, json={
        "customer_id": cust["id"], "vehicle_id": veh["id"],
        "reported_issue": "cancel flow"}).json()
    r = client.post(f"/api/jobs/{job['id']}/parts", headers=auth, json={
        "product_id": pid, "quantity": 2, "unit_price_paisa": 10000})
    assert r.status_code == 200, r.text
    assert client.get(f"/api/products/{pid}",
                      headers=auth).json()["quantity_on_hand"] == 1
    r = client.post(f"/api/jobs/{job['id']}/status", headers=auth,
                    json={"status": "inspection"})
    assert r.status_code == 200, r.text
    r = client.post(f"/api/jobs/{job['id']}/status", headers=auth,
                    json={"status": "cancelled"})
    assert r.status_code == 200, r.text
    assert client.get(f"/api/products/{pid}",
                      headers=auth).json()["quantity_on_hand"] == 3
    r = client.post(f"/api/jobs/{job['id']}/invoice", headers=auth,
                    json={"payments": []})
    assert r.status_code == 400
    assert "cancelled" in r.json()["detail"].lower()


def test_business_settings_full_payload_round_trips(client, auth):
    """The settings form spreads the current business object back into the PUT.

    Saving must therefore accept the whole GET payload unchanged (the UI sends
    every field it received, plus the edited ones) without dropping values.
    """
    before = client.get("/api/settings/business", headers=auth).json()
    payload = {k: v for k, v in before.items() if k != "app_version"}
    payload.update({
        "business_name": "Round Trip Workshop",
        "tagline": "Tagline",
        "phone": "0300-9999999",
        "alt_phone": "0301-8888888",
        "email": "shop@example.com",
        "address": "12 Test Road",
        "business_hours": "9am - 9pm",
        "tax_ntn": "NTN-1234567",
        "invoice_footer": "Thanks for visiting",
        "tax_enabled": True,
        "tax_rate_percent": 5,
        "low_stock_default": 4,
    })
    r = client.put("/api/settings/business", headers=auth, json=payload)
    assert r.status_code == 200, r.text
    after = client.get("/api/settings/business", headers=auth).json()
    for key, value in payload.items():
        assert after[key] == value, key
    assert after["app_version"] == "1.2.2"

    # the spread payload also survives a second save with only one field changed
    payload["business_name"] = "Round Trip Workshop 2"
    r = client.put("/api/settings/business", headers=auth, json=payload)
    assert r.status_code == 200, r.text
    again = client.get("/api/settings/business", headers=auth).json()
    assert again["business_name"] == "Round Trip Workshop 2"
    assert again["invoice_footer"] == "Thanks for visiting"
    assert again["tax_ntn"] == "NTN-1234567"


def test_unknown_mechanic_id_is_400_not_500(client, auth):
    """A stale mechanic id used to reach the FK and blow up as a 500."""
    cust = client.post("/api/customers", headers=auth, json={
        "name": "Audit Mech Cust", "phone": "03007000001"}).json()
    veh = client.post("/api/vehicles", headers=auth, json={
        "customer_id": cust["id"], "registration_no": "AUD-MECH-2"}).json()
    job = client.post("/api/jobs", headers=auth, json={
        "customer_id": cust["id"], "vehicle_id": veh["id"],
        "reported_issue": "mechanic validation"}).json()

    r = client.post(f"/api/jobs/{job['id']}/services", headers=auth, json={
        "description": "Line work", "quantity": 1, "unit_charge_paisa": 1000,
        "mechanic_id": 999999})
    assert r.status_code == 400, r.text
    assert "mechanic" in r.json()["detail"].lower()

    mech = client.post("/api/mechanics", headers=auth, json={
        "name": "Audit Real Mechanic", "skill": "Engine"}).json()
    r = client.post(f"/api/jobs/{job['id']}/services", headers=auth, json={
        "description": "Line work", "quantity": 1, "unit_charge_paisa": 1000,
        "mechanic_id": mech["id"]})
    assert r.status_code == 200, r.text
    sid = r.json()["id"]

    r = client.put(f"/api/jobs/services/{sid}", headers=auth, json={
        "description": "Line work", "quantity": 1, "unit_charge_paisa": 1000,
        "mechanic_id": 999999})
    assert r.status_code == 400, r.text
    r = client.put(f"/api/jobs/services/{sid}", headers=auth, json={
        "mechanic_id": mech["id"]})
    assert r.status_code == 200, r.text

    r = client.put(f"/api/jobs/{job['id']}", headers=auth,
                   json={"mechanic_id": 999999})
    assert r.status_code == 400, r.text
    r = client.put(f"/api/jobs/{job['id']}", headers=auth,
                   json={"mechanic_id": mech["id"]})
    assert r.status_code == 200, r.text
    assert r.json()["mechanic_name"] == "Audit Real Mechanic"
