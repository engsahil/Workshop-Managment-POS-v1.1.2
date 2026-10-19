"""Expenses, shifts, reconciliation tests."""
from datetime import date


def test_expense_categories_and_entry(client, auth):
    r = client.post("/api/expense-categories", headers=auth,
                    json={"name": "Test Rent Cat"})
    assert r.status_code == 200
    cat_id = r.json()["id"]
    r = client.post("/api/expenses", headers=auth, json={
        "category_id": cat_id, "amount_paisa": 4500000,
        "expense_date": str(date.today()),
        "description": "monthly rent"})
    assert r.status_code == 200, r.text
    exp = r.json()
    assert exp["amount_paisa"] == 4500000
    # payment method must be one of the allowed methods
    r = client.post("/api/expenses", headers=auth, json={
        "category_id": cat_id, "amount_paisa": 100000,
        "expense_date": str(date.today()), "method": "gold"})
    assert r.status_code == 422


def test_expense_date_filter(client, auth):
    cat_id = client.post("/api/expense-categories", headers=auth,
                         json={"name": "Test Utilities Cat"}).json()["id"]
    client.post("/api/expenses", headers=auth, json={
        "category_id": cat_id, "amount_paisa": 250000,
        "expense_date": "2020-05-05"})
    r = client.get("/api/expenses?date_from=2020-05-05&date_to=2020-05-05",
                   headers=auth)
    assert r.json()["total"] >= 1
    r = client.get("/api/expenses?date_from=2030-01-01", headers=auth)
    assert r.json()["total"] == 0


def test_shift_open_close_reconciliation(client, db_session, auth):
    from conftest import make_user, token_for
    make_user(db_session, "cash4", "cashier")
    t = token_for(client, "cash4")
    h = {"Authorization": f"Bearer {t}"}
    r = client.post("/api/shifts/open", headers=h,
                    json={"opening_cash_paisa": 100000})
    assert r.status_code == 200
    shift_id = r.json()["id"]
    # a sale tagged with this shift
    pid = client.post("/api/products", headers=auth, json={
        "name": "ShiftItem", "sku": "SH-1", "selling_price_paisa": 30000,
        "purchase_cost_paisa": 10000}).json()["id"]
    client.post("/api/inventory/receive", headers=auth, json={
        "product_id": pid, "quantity": 5, "unit_cost_paisa": 10000,
        "reference_number": "GRN-S"})
    r = client.post("/api/pos/invoices", headers=h, json={
        "items": [{"item_type": "product", "product_id": pid,
                   "quantity": 1, "unit_price_paisa": 30000}],
        "payments": [{"amount_paisa": 30000, "method": "cash"}],
        "shift_id": shift_id})
    assert r.status_code == 200
    # reconciliation report lists shifts; find ours
    rep = client.get("/api/reports/shift-reconciliation",
                     headers=auth).json()
    row = [s for s in rep if s["id"] == shift_id][0]
    assert row["expected_cash_paisa"] == 130000  # opening + sale
    # cannot open a second shift while one is open
    r = client.post("/api/shifts/open", headers=h,
                    json={"opening_cash_paisa": 0})
    assert r.status_code == 400
    # close with counted cash 130000 -> variance 0
    r = client.post(f"/api/shifts/{shift_id}/close", headers=h, json={
        "counted_cash_paisa": 130000})
    assert r.json()["difference_paisa"] == 0
    assert r.json()["status"] == "closed"
    # cannot close twice
    r = client.post(f"/api/shifts/{shift_id}/close", headers=h,
                    json={"counted_cash_paisa": 0})
    assert r.status_code == 400
    # after closing, a new shift can be opened
    r = client.post("/api/shifts/open", headers=h,
                    json={"opening_cash_paisa": 0})
    assert r.status_code == 200
