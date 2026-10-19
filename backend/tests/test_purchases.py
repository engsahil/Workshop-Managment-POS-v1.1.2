"""Suppliers, purchase orders, receiving, supplier statements."""


def test_supplier_crud(client, auth):
    r = client.post("/api/suppliers", headers=auth, json={
        "name": "Auto Parts Co", "contact_person": "Ali",
        "phone": "021-1111111", "email": "ali@autoparts.pk",
        "address": "Sindh Industrial Area"})
    assert r.status_code == 200
    sid = r.json()["id"]
    r = client.put(f"/api/suppliers/{sid}", headers=auth,
                   json={"phone": "021-9999999"})
    assert r.json()["phone"] == "021-9999999"
    r = client.get("/api/suppliers?q=Auto", headers=auth)
    assert isinstance(r.json(), list)
    assert any(s["id"] == sid for s in r.json())


def test_po_create_receive_once(client, auth):
    sid = client.post("/api/suppliers", headers=auth, json={
        "name": "SupOne", "phone": "03001110001"}).json()["id"]
    pid = client.post("/api/products", headers=auth, json={
        "name": "PO Item", "sku": "POI-1", "selling_price_paisa": 9000,
        "purchase_cost_paisa": 6000}).json()["id"]
    po = client.post("/api/purchases", headers=auth, json={
        "supplier_id": sid, "notes": "stock up",
        "items": [{"product_id": pid, "quantity": 20,
                   "unit_cost_paisa": 6000}]}).json()
    assert po["total_paisa"] == 120000
    assert po["status"] == "ordered"
    # receiving adds stock exactly once
    r = client.post(f"/api/purchases/{po['id']}/receive", headers=auth,
                    json={"invoice_number": "SUP-INV-1"})
    assert r.status_code == 200
    assert r.json()["status"] == "received"
    p = client.get(f"/api/products/{pid}", headers=auth).json()
    assert p["quantity_on_hand"] == 20
    # second receive is refused
    r = client.post(f"/api/purchases/{po['id']}/receive", headers=auth,
                    json={})
    assert r.status_code == 400
    assert "already been received" in r.json()["detail"]
    # stock still 20 (not 40)
    p = client.get(f"/api/products/{pid}", headers=auth).json()
    assert p["quantity_on_hand"] == 20


def test_partial_receive(client, auth):
    sid = client.post("/api/suppliers", headers=auth, json={
        "name": "SupTwo", "phone": "03002220002"}).json()["id"]
    pid = client.post("/api/products", headers=auth, json={
        "name": "PO Item2", "sku": "POI-2", "selling_price_paisa": 9000,
        "purchase_cost_paisa": 6000}).json()["id"]
    po = client.post("/api/purchases", headers=auth, json={
        "supplier_id": sid,
        "items": [{"product_id": pid, "quantity": 10,
                   "unit_cost_paisa": 6000}]}).json()
    r = client.post(f"/api/purchases/{po['id']}/receive", headers=auth,
                    json={"items": [
                        {"product_id": pid, "quantity": 6}]})
    assert r.status_code == 200
    assert r.json()["status"] == "partial"
    p = client.get(f"/api/products/{pid}", headers=auth).json()
    assert p["quantity_on_hand"] == 6


def test_supplier_balance_and_statement(client, auth):
    sid = client.post("/api/suppliers", headers=auth, json={
        "name": "SupCred", "phone": "03003330003"}).json()["id"]
    pid = client.post("/api/products", headers=auth, json={
        "name": "PO Item3", "sku": "POI-3", "selling_price_paisa": 9000,
        "purchase_cost_paisa": 6000}).json()["id"]
    po = client.post("/api/purchases", headers=auth, json={
        "supplier_id": sid,
        "items": [{"product_id": pid, "quantity": 10,
                   "unit_cost_paisa": 6000}]}).json()
    # pay half up front
    r = client.post(f"/api/purchases/{po['id']}/payments",
                    headers=auth, json={"amount_paisa": 30000,
                                          "method": "cash"})
    assert r.status_code == 200
    # 60000 total, 30000 paid -> supplier balance 30000
    sup = [s for s in client.get("/api/suppliers",
                                  headers=auth).json()
           if s["id"] == sid][0]
    assert sup["balance_paisa"] == 30000
    stmt = client.get(f"/api/reports/supplier-statement/{sid}",
                      headers=auth).json()
    assert stmt["balance_paisa"] == 30000
    assert len(stmt["entries"]) >= 1


def test_po_cannot_receive_twice_even_with_different_args(client, auth):
    sid = client.post("/api/suppliers", headers=auth, json={
        "name": "SupThree", "phone": "03004440004"}).json()["id"]
    pid = client.post("/api/products", headers=auth, json={
        "name": "PO Item4", "sku": "POI-4", "selling_price_paisa": 1000,
        "purchase_cost_paisa": 500}).json()["id"]
    po = client.post("/api/purchases", headers=auth, json={
        "supplier_id": sid,
        "items": [{"product_id": pid, "quantity": 5,
                   "unit_cost_paisa": 500}]}).json()
    client.post(f"/api/purchases/{po['id']}/receive", headers=auth, json={})
    # any second attempt fails regardless of payload
    r = client.post(f"/api/purchases/{po['id']}/receive", headers=auth,
                    json={"invoice_number": "X"})
    assert r.status_code == 400


def test_purchase_return_deducts_stock_and_balance(client, auth):
    sid = client.post("/api/suppliers", headers=auth, json={
        "name": "SupRet", "phone": "03005550005"}).json()["id"]
    pid = client.post("/api/products", headers=auth, json={
        "name": "PO RetItem", "sku": "POI-5", "selling_price_paisa": 2000,
        "purchase_cost_paisa": 1000}).json()["id"]
    po = client.post("/api/purchases", headers=auth, json={
        "supplier_id": sid,
        "items": [{"product_id": pid, "quantity": 6,
                   "unit_cost_paisa": 1000}]}).json()
    client.post(f"/api/purchases/{po['id']}/receive", headers=auth, json={})
    r = client.post("/api/purchase-returns", headers=auth, json={
        "purchase_id": po["id"],
        "items": [{"product_id": pid, "quantity": 2, "unit_cost_paisa": 1000}],
        "method": "credit"})
    assert r.status_code == 200, r.text
    assert r.json()["total_paisa"] == 2000
    p = client.get(f"/api/products/{pid}", headers=auth).json()
    assert p["quantity_on_hand"] == 4
    # returning more than remaining received (4) is rejected
    r2 = client.post("/api/purchase-returns", headers=auth, json={
        "purchase_id": po["id"],
        "items": [{"product_id": pid, "quantity": 5, "unit_cost_paisa": 1000}]})
    assert r2.status_code == 400

