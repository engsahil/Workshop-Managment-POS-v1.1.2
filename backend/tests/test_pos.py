"""POS, invoices, payments, returns tests."""


def setup_product(client, auth, name, price=100000, cost=60000, stock=0):
    r = client.post("/api/products", headers=auth, json={
        "name": name, "sku": name.upper().replace(" ", "-"),
        "selling_price_paisa": price, "purchase_cost_paisa": cost})
    assert r.status_code == 200, r.text
    pid = r.json()["id"]
    if stock:
        rr = client.post("/api/inventory/receive", headers=auth, json={
            "product_id": pid, "quantity": stock,
            "unit_cost_paisa": cost, "reference_number": f"GRN-{name}"})
        assert rr.status_code == 200, rr.text
    return pid


def test_pos_invoice_cash(client, auth):
    pid = setup_product(client, auth, "Spark Plug", 25000, 12000, stock=10)
    r = client.post("/api/pos/invoices", headers=auth, json={
        "customer_id": None,
        "items": [{"item_type": "product", "product_id": pid,
                   "quantity": 2, "unit_price_paisa": 25000}],
        "payments": [{"amount_paisa": 50000, "method": "cash"}],
        "notes": "sale test"})
    assert r.status_code == 200, r.text
    inv = r.json()
    assert inv["total_paisa"] == 50000
    assert inv["status"] == "paid"
    assert inv["paid_paisa"] == 50000
    assert inv["balance_paisa"] == 0
    assert inv["invoice_number"].startswith("INV-")
    # stock deducted exactly once
    p = client.get(f"/api/products/{pid}", headers=auth).json()
    assert p["quantity_on_hand"] == 8


def test_split_payments(client, auth):
    pid = setup_product(client, auth, "Split Item", 30000, 10000, stock=5)
    r = client.post("/api/pos/invoices", headers=auth, json={
        "items": [{"item_type": "product", "product_id": pid,
                   "quantity": 1, "unit_price_paisa": 30000}],
        "payments": [{"amount_paisa": 20000, "method": "cash"},
                     {"amount_paisa": 10000, "method": "card"}]})
    inv = r.json()
    assert inv["status"] == "paid"
    assert inv["paid_paisa"] == 30000
    # method summary is a compact string like "cash:200.00,card:100.00"
    assert "cash:200.00" in inv["payment_method_summary"]
    assert "card:100.00" in inv["payment_method_summary"]


def test_partial_payment_and_credit(client, auth):
    pid = setup_product(client, auth, "Credit Item", 40000, 15000, stock=5)
    r = client.post("/api/pos/invoices", headers=auth, json={
        "items": [{"item_type": "product", "product_id": pid,
                   "quantity": 1, "unit_price_paisa": 40000}],
        "payments": [{"amount_paisa": 15000, "method": "cash"}]})
    inv = r.json()
    assert inv["status"] == "partial"
    assert inv["balance_paisa"] == 25000


def test_credit_sale_without_permission_fails(client, db_session, auth):
    from conftest import make_user, token_for
    make_user(db_session, "cash3", "cashier")
    t = token_for(client, "cash3")
    h = {"Authorization": f"Bearer {t}"}
    pid = setup_product(client, auth, "CredItem", 10000, 4000, stock=3)
    r = client.post("/api/pos/invoices", headers=h, json={
        "items": [{"item_type": "product", "product_id": pid,
                   "quantity": 1, "unit_price_paisa": 10000}],
        "payments": []})  # no payment -> credit sale
    assert r.status_code == 403


def test_customer_balance_updates(client, auth):
    cust = client.post("/api/customers", headers=auth, json={
        "name": "Bal Customer", "phone": "03001112222"}).json()
    pid = setup_product(client, auth, "BalItem", 50000, 20000, stock=5)
    # full credit sale (no payment)
    inv = client.post("/api/pos/invoices", headers=auth, json={
        "customer_id": cust["id"],
        "items": [{"item_type": "product", "product_id": pid,
                   "quantity": 2, "unit_price_paisa": 50000}],
        "payments": []}).json()
    assert inv["status"] == "credit"
    assert client.get(f"/api/customers/{cust['id']}", headers=auth).json()[
        "balance_paisa"] == 100000
    # partial payment
    client.post(f"/api/invoices/{inv['id']}/payments", headers=auth, json={
        "amount_paisa": 40000, "method": "cash"})
    assert client.get(f"/api/customers/{cust['id']}", headers=auth).json()[
        "balance_paisa"] == 60000


def test_discount_and_tax(client, auth):
    # enable 18% tax in business settings
    r = client.put("/api/settings/business", headers=auth, json={
        "tax_enabled": True, "tax_rate_percent": 18})
    assert r.status_code == 200
    pid = setup_product(client, auth, "TaxItem", 100000, 60000, stock=5)
    r = client.post("/api/pos/invoices", headers=auth, json={
        "items": [{"item_type": "product", "product_id": pid,
                   "quantity": 1, "unit_price_paisa": 100000}],
        "invoice_discount_paisa": 10000,
        "payments": [{"amount_paisa": 106200, "method": "cash"}]})
    inv = r.json()
    # 100000 - 10000 = 90000; +18% GST = 106200
    assert inv["subtotal_paisa"] == 100000
    assert inv["discount_paisa"] == 10000
    assert inv["tax_paisa"] == 16200
    assert inv["total_paisa"] == 106200
    # disable tax again for other tests
    client.put("/api/settings/business", headers=auth,
               json={"tax_enabled": False})


def test_payment_does_not_exceed_due(client, auth):
    pid = setup_product(client, auth, "Overpay", 10000, 5000, stock=2)
    r = client.post("/api/pos/invoices", headers=auth, json={
        "items": [{"item_type": "product", "product_id": pid,
                   "quantity": 1, "unit_price_paisa": 10000}],
        "payments": [{"amount_paisa": 20000, "method": "cash"}]})
    assert r.status_code == 400


def test_return_workflow(client, auth):
    pid = setup_product(client, auth, "RetItem", 20000, 8000, stock=10)
    inv = client.post("/api/pos/invoices", headers=auth, json={
        "items": [{"item_type": "product", "product_id": pid,
                   "quantity": 3, "unit_price_paisa": 20000}],
        "payments": [{"amount_paisa": 60000, "method": "cash"}]}).json()
    line = inv["items"][0]
    r = client.post("/api/invoices/returns", headers=auth, json={
        "invoice_id": inv["id"],
        "items": [{"invoice_item_id": line["id"], "quantity": 1}],
        "refund_method": "cash"})
    assert r.status_code == 200, r.text
    ret = r.json()
    assert ret["total_paisa"] == 20000
    rid = ret["id"]
    # approve -> stock restored + refund recorded
    r = client.post(f"/api/invoices/returns/{rid}/decide", headers=auth,
                    json={"status": "approved"})
    assert r.status_code == 200
    p = client.get(f"/api/products/{pid}", headers=auth).json()
    assert p["quantity_on_hand"] == 8  # 10 - 3 + 1
    # invoice collected reduced by refund
    inv2 = client.get(f"/api/invoices/{inv['id']}", headers=auth).json()
    assert inv2["paid_paisa"] == 40000


def test_return_requires_financial_role(client, db_session, auth):
    from conftest import make_user, token_for
    make_user(db_session, "cash6", "cashier")
    t = token_for(client, "cash6")
    h = {"Authorization": f"Bearer {t}"}
    pid = setup_product(client, auth, "RetPerm", 10000, 4000, stock=5)
    inv = client.post("/api/pos/invoices", headers=auth, json={
        "items": [{"item_type": "product", "product_id": pid,
                   "quantity": 1, "unit_price_paisa": 10000}],
        "payments": [{"amount_paisa": 10000, "method": "cash"}]}).json()
    r = client.post("/api/invoices/returns", headers=h, json={
        "invoice_id": inv["id"],
        "items": [{"invoice_item_id": inv["items"][0]["id"],
                   "quantity": 1}],
        "refund_method": "cash"})
    assert r.status_code == 403


def test_double_return_prevented(client, auth):
    pid = setup_product(client, auth, "DblRet", 10000, 4000, stock=5)
    inv = client.post("/api/pos/invoices", headers=auth, json={
        "items": [{"item_type": "product", "product_id": pid,
                   "quantity": 1, "unit_price_paisa": 10000}],
        "payments": [{"amount_paisa": 10000, "method": "cash"}]}).json()
    line = inv["items"][0]
    ret = client.post("/api/invoices/returns", headers=auth, json={
        "invoice_id": inv["id"],
        "items": [{"invoice_item_id": line["id"], "quantity": 1}],
        "refund_method": "cash"}).json()
    client.post(f"/api/invoices/returns/{ret['id']}/decide", headers=auth,
                json={"status": "approved"})
    r = client.post("/api/invoices/returns", headers=auth, json={
        "invoice_id": inv["id"],
        "items": [{"invoice_item_id": line["id"], "quantity": 1}],
        "refund_method": "cash"})
    assert r.status_code == 400  # nothing left to return


def test_void_restores_stock_and_revenue_excluded(client, auth):
    before = client.get("/api/reports/dashboard",
                        headers=auth).json()["sales"]["revenue_paisa"]
    pid = setup_product(client, auth, "VoidItem", 15000, 7000, stock=10)
    inv = client.post("/api/pos/invoices", headers=auth, json={
        "items": [{"item_type": "product", "product_id": pid,
                   "quantity": 2, "unit_price_paisa": 15000}],
        "payments": [{"amount_paisa": 30000, "method": "cash"}]}).json()
    r = client.post(f"/api/invoices/{inv['id']}/void", headers=auth,
                    json={"reason": "customer cancelled"})
    assert r.status_code == 200
    assert r.json()["status"] == "void"
    p = client.get(f"/api/products/{pid}", headers=auth).json()
    assert p["quantity_on_hand"] == 10  # restored
    d = client.get("/api/reports/dashboard", headers=auth).json()
    # voided invoice contributes nothing to revenue
    assert d["sales"]["revenue_paisa"] == before


def test_invoice_list_date_filter(client, auth):
    pid = setup_product(client, auth, "FilterItem", 10000, 5000, stock=5)
    r = client.post("/api/pos/invoices", headers=auth, json={
        "items": [{"item_type": "product", "product_id": pid,
                   "quantity": 1, "unit_price_paisa": 10000}],
        "payments": [{"amount_paisa": 10000, "method": "cash"}]})
    assert r.status_code == 200
    r = client.get("/api/invoices?date_from=2020-01-01", headers=auth)
    assert r.json()["total"] >= 1
    r = client.get("/api/invoices?date_from=2099-01-01", headers=auth)
    assert r.json()["total"] == 0


def test_receipt_print_data(client, auth):
    pid = setup_product(client, auth, "RcptItem", 5000, 2000, stock=5)
    inv = client.post("/api/pos/invoices", headers=auth, json={
        "items": [{"item_type": "product", "product_id": pid,
                   "quantity": 1, "unit_price_paisa": 5000}],
        "payments": [{"amount_paisa": 5000, "method": "cash"}]}).json()
    r = client.get(f"/api/invoices/{inv['id']}/print-data", headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert body["business"]["business_name"]
    assert len(body["items"]) == 1
