"""Authentication, authorization and user management tests."""
from fastapi.testclient import TestClient

from conftest import make_user, token_for


def test_setup_status_and_admin_creation(client):
    r = client.get("/api/auth/setup-status")
    assert r.status_code == 200
    assert r.json()["needs_setup"] is True
    r = client.post("/api/auth/setup", json={
        "username": "admin", "full_name": "Admin",
        "password": "admin123", "password_confirm": "admin123"})
    assert r.status_code == 200
    assert r.json()["user"]["role"] == "admin"
    # second setup attempt is refused
    r2 = client.post("/api/auth/setup", json={
        "username": "admin2", "full_name": "A2",
        "password": "admin123", "password_confirm": "admin123"})
    assert r2.status_code == 403


def test_login_wrong_password(client):
    r = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    assert r.status_code == 401


def test_login_ok(client, admin_token):
    assert admin_token
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    assert r.json()["role"] == "admin"


def test_no_token_rejected(client):
    r = client.get("/api/customers")
    assert r.status_code == 401


def test_bad_token_rejected(client):
    r = client.get("/api/customers", headers={"Authorization": "Bearer garbage"})
    assert r.status_code == 401


def test_cashier_cannot_access_admin_users(client, db_session):
    make_user(db_session, "cashier1", "cashier")
    t = token_for(client, "cashier1")
    h = {"Authorization": f"Bearer {t}"}
    r = client.get("/api/users", headers=h)
    assert r.status_code == 403
    # but cashier CAN open a shift (POS function)
    r = client.post("/api/shifts/open", headers=h, json={"opening_cash_paisa": 1000})
    assert r.status_code == 200


def test_cashier_cannot_void_invoice(client, db_session, auth):
    make_user(db_session, "cashier2", "cashier")
    t = token_for(client, "cashier2")
    h = {"Authorization": f"Bearer {t}"}
    # create a stocked product + invoice as admin first
    pid = client.post("/api/products", headers=auth, json={
        "name": "Oil Filter", "selling_price_paisa": 50000,
        "purchase_cost_paisa": 20000}).json()["id"]
    client.post("/api/inventory/receive", headers=auth, json={
        "product_id": pid, "quantity": 5, "unit_cost_paisa": 20000,
        "reference_number": "GRN-VOID"})
    inv = client.post("/api/pos/invoices", headers=auth, json={
        "items": [{"item_type": "product", "product_id": pid,
                   "quantity": 1, "unit_price_paisa": 50000}],
        "payments": [{"amount_paisa": 50000, "method": "cash"}]}).json()
    r = client.post(f"/api/invoices/{inv['id']}/void", headers=h, json={"reason": "test"})
    assert r.status_code == 403


def test_manager_can_void(client, db_session, auth):
    make_user(db_session, "mgr1", "manager")
    t = token_for(client, "mgr1")
    h = {"Authorization": f"Bearer {t}"}
    pid = client.post("/api/products", headers=auth, json={
        "name": "MgrItem", "selling_price_paisa": 50000,
        "purchase_cost_paisa": 20000}).json()["id"]
    client.post("/api/inventory/receive", headers=auth, json={
        "product_id": pid, "quantity": 5, "unit_cost_paisa": 20000,
        "reference_number": "GRN-MGR"})
    inv = client.post("/api/pos/invoices", headers=auth, json={
        "items": [{"item_type": "product", "product_id": pid,
                   "quantity": 1, "unit_price_paisa": 50000}],
        "payments": [{"amount_paisa": 50000, "method": "cash"}]}).json()
    r = client.post(f"/api/invoices/{inv['id']}/void", headers=h, json={"reason": "test void"})
    assert r.status_code == 200
    assert r.json()["status"] == "void"


def test_password_change_and_reset(client, db_session, auth):
    u = make_user(db_session, "user1", "cashier")
    t = token_for(client, "user1")
    h = {"Authorization": f"Bearer {t}"}
    r = client.post("/api/auth/change-password", headers=h, json={
        "current_password": "pass1234", "new_password": "newpass123"})
    assert r.status_code == 200
    # old password no longer works
    r = client.post("/api/auth/login", json={"username": "user1", "password": "pass1234"})
    assert r.status_code == 401
    # admin resets
    r = client.post(f"/api/auth/users/{u.id}/reset-password",
                    headers=auth, json={"new_password": "reset987"})
    assert r.status_code == 200
    t2 = token_for(client, "user1", "reset987")
    assert t2


def test_user_crud_and_deactivation(client, db_session, auth):
    r = client.post("/api/users", headers=auth, json={
        "username": "userone", "full_name": "User One",
        "password": "pass1234", "role": "cashier"})
    assert r.status_code == 200
    uid = r.json()["id"]
    r = client.put(f"/api/users/{uid}", headers=auth, json={"is_active": False})
    assert r.status_code == 200
    # deactivated user cannot log in
    r = client.post("/api/auth/login", json={"username": "u1", "password": "pass1234"})
    assert r.status_code == 401
