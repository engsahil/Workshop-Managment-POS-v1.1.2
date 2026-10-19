"""Inventory, products, stock movement tests."""


def test_product_crud(client, auth):
    r = client.post("/api/products", headers=auth, json={
        "name": "Brake Pad", "sku": "BP-001", "barcode": "111",
        "purchase_cost_paisa": 30000, "selling_price_paisa": 55000,
        "min_stock": 4, "unit": "pcs"})
    assert r.status_code == 200, r.text
    pid = r.json()["id"]
    r = client.get(f"/api/products/{pid}", headers=auth)
    assert r.json()["name"] == "Brake Pad"
    r = client.put(f"/api/products/{pid}", headers=auth,
                   json={"selling_price_paisa": 58000})
    assert r.json()["selling_price_paisa"] == 58000
    r = client.get("/api/products?q=Brake", headers=auth)
    assert r.json()["total"] == 1
    r = client.get("/api/products?q=nothing-matches", headers=auth)
    assert r.json()["total"] == 0


def test_sku_uniqueness(client, auth):
    client.post("/api/products", headers=auth, json={
        "name": "A", "sku": "UNIQ-1", "selling_price_paisa": 1000})
    r = client.post("/api/products", headers=auth, json={
        "name": "B", "sku": "UNIQ-1", "selling_price_paisa": 1000})
    assert r.status_code == 400


def test_stock_receive_and_movement(client, auth):
    pid = client.post("/api/products", headers=auth, json={
        "name": "Chain Lube", "sku": "CL-1",
        "selling_price_paisa": 120000, "purchase_cost_paisa": 80000,
        "min_stock": 2}).json()["id"]
    r = client.post("/api/inventory/receive", headers=auth, json={
        "product_id": pid, "quantity": 5, "unit_cost_paisa": 80000,
        "reference_number": "GRN-1"})
    assert r.status_code == 200
    p = client.get(f"/api/products/{pid}", headers=auth).json()
    assert p["quantity_on_hand"] == 5
    mv = client.get(f"/api/inventory/movements?product_id={pid}",
                    headers=auth)
    assert mv.json()["items"][0]["movement_type"] == "receive"
    assert mv.json()["items"][0]["quantity_after"] == 5


def test_negative_stock_prevented(client, auth):
    pid = client.post("/api/products", headers=auth, json={
        "name": "NegItem", "sku": "NEG-1",
        "selling_price_paisa": 10000,
        "purchase_cost_paisa": 4000}).json()["id"]
    client.post("/api/inventory/receive", headers=auth, json={
        "product_id": pid, "quantity": 5, "unit_cost_paisa": 4000,
        "reference_number": "GRN-N"})
    r = client.post("/api/pos/invoices", headers=auth, json={
        "items": [{"item_type": "product", "product_id": pid,
                   "quantity": 9, "unit_price_paisa": 10000}],
        "payments": [{"amount_paisa": 90000, "method": "cash"}]})
    assert r.status_code == 400
    assert "Insufficient stock" in r.json()["detail"]
    p = client.get(f"/api/products/{pid}", headers=auth).json()
    assert p["quantity_on_hand"] == 5  # unchanged


def test_adjustment_and_damage(client, auth):
    pid = client.post("/api/products", headers=auth, json={
        "name": "AdjItem", "sku": "ADJ-1",
        "selling_price_paisa": 10000,
        "purchase_cost_paisa": 4000}).json()["id"]
    client.post("/api/inventory/receive", headers=auth, json={
        "product_id": pid, "quantity": 5, "unit_cost_paisa": 4000,
        "reference_number": "GRN-A"})
    r = client.post("/api/inventory/adjust", headers=auth, json={
        "product_id": pid, "delta": -1, "movement_type": "damage",
        "reason": "damaged in store"})
    assert r.status_code == 200
    p = client.get(f"/api/products/{pid}", headers=auth).json()
    assert p["quantity_on_hand"] == 4
    r = client.post("/api/inventory/adjust", headers=auth, json={
        "product_id": pid, "delta": 2, "movement_type": "adjust",
        "reason": "count correction"})
    p = client.get(f"/api/products/{pid}", headers=auth).json()
    assert p["quantity_on_hand"] == 6


def test_low_stock_alert(client, auth):
    pid = client.post("/api/products", headers=auth, json={
        "name": "LowItem", "sku": "LOW-1",
        "selling_price_paisa": 10000,
        "purchase_cost_paisa": 4000}).json()["id"]
    client.post("/api/inventory/receive", headers=auth, json={
        "product_id": pid, "quantity": 2, "unit_cost_paisa": 4000,
        "reference_number": "GRN-L"})
    client.put(f"/api/products/{pid}", headers=auth,
               json={"min_stock": 10})
    r = client.get("/api/inventory/low-stock", headers=auth)
    assert any(p["id"] == pid for p in r.json())
    n = client.get("/api/notifications", headers=auth).json()
    assert n["unread_count"] >= 1


def test_inventory_valuation(client, auth):
    r = client.get("/api/inventory/valuation", headers=auth)
    assert r.status_code == 200
    assert "valuation_paisa" in r.json()


def test_csv_export(client, auth):
    client.post("/api/products", headers=auth, json={
        "name": "ExportItem", "sku": "EXP-1",
        "selling_price_paisa": 1000})
    r = client.get("/api/products/export/csv", headers=auth)
    assert r.status_code == 200
    assert "ExportItem" in r.text
