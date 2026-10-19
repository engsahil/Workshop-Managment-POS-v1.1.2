"""Reports and dashboard tests."""
from datetime import date


def test_dashboard_figures(client, auth):
    before = client.get("/api/reports/dashboard",
                        headers=auth).json()
    cid = client.post("/api/customers", headers=auth, json={
        "name": "Dash Cust", "phone": "03001234567"}).json()["id"]
    pid = client.post("/api/products", headers=auth, json={
        "name": "DashItem", "sku": "DASH-1", "selling_price_paisa": 100000,
        "purchase_cost_paisa": 40000}).json()["id"]
    client.post("/api/inventory/receive", headers=auth, json={
        "product_id": pid, "quantity": 3, "unit_cost_paisa": 40000,
        "reference_number": "GRN-D"})
    client.post("/api/pos/invoices", headers=auth, json={
        "customer_id": cid,
        "items": [{"item_type": "product", "product_id": pid,
                   "quantity": 1, "unit_price_paisa": 100000}],
        "payments": [{"amount_paisa": 100000, "method": "cash"}]})
    d = client.get("/api/reports/dashboard", headers=auth).json()
    assert d["sales"]["revenue_paisa"] == before["sales"]["revenue_paisa"] + 100000
    # gross profit = revenue - cost of sold goods (40000)
    assert d["profit"]["gross_profit_paisa"] == \
        before["profit"]["gross_profit_paisa"] + 60000
    # fully paid sale adds nothing to receivables
    assert d["receivables"]["outstanding_paisa"] == \
        before["receivables"]["outstanding_paisa"]
    assert len(d["recent"]["invoices"]) >= 1


def test_revenue_vs_collected_distinction(client, auth):
    cid = client.post("/api/customers", headers=auth, json={
        "name": "RevCust", "phone": "03007654321"}).json()["id"]
    pid = client.post("/api/products", headers=auth, json={
        "name": "RevItem", "sku": "REV-1", "selling_price_paisa": 70000,
        "purchase_cost_paisa": 30000}).json()["id"]
    client.post("/api/inventory/receive", headers=auth, json={
        "product_id": pid, "quantity": 2, "unit_cost_paisa": 30000,
        "reference_number": "GRN-R"})
    # credit sale: revenue recognized, nothing collected
    inv = client.post("/api/pos/invoices", headers=auth, json={
        "customer_id": cid,
        "items": [{"item_type": "product", "product_id": pid,
                   "quantity": 1, "unit_price_paisa": 70000}],
        "payments": []}).json()
    d = client.get("/api/reports/dashboard", headers=auth).json()
    assert d["sales"]["revenue_paisa"] >= 70000
    assert d["receivables"]["outstanding_paisa"] >= 70000
    # collect a partial payment
    client.post(f"/api/invoices/{inv['id']}/payments", headers=auth,
                json={"amount_paisa": 20000, "method": "cash"})
    d = client.get("/api/reports/dashboard", headers=auth).json()
    assert d["receivables"]["outstanding_paisa"] >= 50000


def test_sales_trend(client, auth):
    today = date.today().isoformat()
    r = client.get(f"/api/reports/sales-trend?date_from={today}&date_to={today}",
                   headers=auth)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_sales_by_dimensions(client, auth):
    for dim in ["product", "service", "category", "cashier"]:
        r = client.get(f"/api/reports/sales-by/{dim}", headers=auth)
        assert r.status_code == 200, dim


def test_payments_summary_and_profit(client, auth):
    r = client.get("/api/reports/payments-summary", headers=auth)
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    r = client.get("/api/reports/profit", headers=auth)
    assert r.status_code == 200
    assert "net_profit_paisa" in r.json()


def test_stock_report_and_statement(client, auth):
    r = client.get("/api/reports/stock", headers=auth)
    assert r.status_code == 200
    cid = client.post("/api/customers", headers=auth, json={
        "name": "Stmt Cust", "phone": "03005556666"}).json()["id"]
    r = client.get(f"/api/reports/customer-statement/{cid}",
                   headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert "entries" in body and "outstanding_paisa" in body


def test_customer_lookup(client, auth):
    client.post("/api/customers", headers=auth, json={
        "name": "Lookup Person", "phone": "03007778888"})
    r = client.get("/api/customers/lookup?q=Lookup", headers=auth)
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    assert any(c["name"] == "Lookup Person" for c in r.json())


def test_report_date_ranges_use_local_dates(client, auth):
    today = date.today().isoformat()
    r = client.get(f"/api/reports/profit?date_from={today}&date_to={today}",
                   headers=auth)
    assert r.status_code == 200
    r = client.get("/api/reports/profit?date_from=2020-01-01&date_to=2020-01-02",
                   headers=auth)
    assert r.status_code == 200


def test_csv_export_endpoints(client, auth):
    # product catalogue exports server-side as CSV
    r = client.get("/api/products/export/csv", headers=auth)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    # full data export (admin endpoint, JSON)
    r = client.get("/api/export", headers=auth)
    assert r.status_code == 200
    assert isinstance(r.json(), dict)


def test_dashboard_date_filter_params(client, auth):
    r1 = client.get("/api/reports/dashboard?date_from=2020-01-01&date_to=2020-01-02",
                    headers=auth).json()
    assert r1["range"] == {"from": "2020-01-01", "to": "2020-01-02"}
    assert r1["sales"]["revenue_paisa"] == 0
    r2 = client.get("/api/reports/dashboard?from=2020-01-01&to=2020-01-02",
                    headers=auth).json()
    assert r2["range"] == {"from": "2020-01-01", "to": "2020-01-02"}
    assert "parts_paisa" in r2["sales"] and "services_paisa" in r2["sales"]

