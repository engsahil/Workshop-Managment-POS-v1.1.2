"""System-level tests: audit log, backups, settings, legal, errors."""
from pathlib import Path


def test_audit_log_written(client, auth):
    client.post("/api/customers", headers=auth, json={
        "name": "Audit Cust", "phone": "03000000001"})
    r = client.get("/api/audit", headers=auth)
    assert r.status_code == 200
    actions = [e["action"] for e in r.json()["items"]]
    assert "customer.create" in actions
    # filter by action
    r = client.get("/api/audit?action=customer.create", headers=auth)
    assert all(e["action"] == "customer.create" for e in r.json()["items"])


def test_audit_requires_admin(client, db_session, auth):
    from conftest import make_user, token_for
    make_user(db_session, "cash5", "cashier")
    t = token_for(client, "cash5")
    r = client.get("/api/audit", headers={"Authorization": f"Bearer {t}"})
    assert r.status_code == 403


def test_backup_create_list_download_restore(client, auth):
    r = client.post("/api/backups", headers=auth, json={"notes": "test"})
    assert r.status_code == 200
    fn = r.json()["filename"]
    r = client.get("/api/backups", headers=auth)
    names = [b["filename"] for b in r.json()["items"]]
    assert fn in names
    # download
    r = client.get(f"/api/backups/{fn}/download", headers=auth)
    assert r.status_code == 200
    assert len(r.content) > 0
    # validate
    r = client.post(f"/api/backups/validate?filename={fn}", headers=auth)
    assert r.status_code == 200
    # restore (same DB) succeeds
    r = client.post(f"/api/backups/{fn}/restore", headers=auth, json={})
    assert r.status_code == 200


def test_backup_filename_traversal_rejected(client, auth):
    r = client.post("/api/backups/..%2F..%2Fx.db/restore", headers=auth,
                    json={})
    assert 400 <= r.status_code < 500
    r = client.get("/api/backups/..%2F..%2Fx.db/download", headers=auth)
    assert 400 <= r.status_code < 500


def test_settings_crud(client, auth):
    r = client.put("/api/settings/business", headers=auth, json={
        "business_name": "Test Workshop", "phone": "021-1234",
        "address": "Test Address", "tax_rate_percent": 18})
    assert r.status_code == 200
    assert r.json()["business_name"] == "Test Workshop"
    r = client.get("/api/settings/business", headers=auth)
    assert r.json()["tax_rate_percent"] == 18
    # logo upload + persistence round-trip
    import io
    png = (b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)
    r = client.post("/api/settings/logo", headers=auth,
                    files={"logo": ("logo.png", io.BytesIO(png),
                                    "image/png")})
    assert r.status_code == 200, r.text
    path = r.json()["path"]
    r = client.put("/api/settings/business", headers=auth,
                   json={"logo_path": path})
    assert r.status_code == 200
    r = client.get("/api/settings/business", headers=auth)
    assert r.json()["logo_path"] == path
    # uploaded file is served back
    r = client.get(f"/api/files/{path}")
    assert r.status_code == 200


def test_legal_pages_editable(client, auth):
    r = client.get("/api/settings/legal/privacy_policy")
    assert r.status_code == 200
    assert "content" in r.json()
    r = client.put("/api/settings/legal/privacy_policy", headers=auth,
                   json={"title": "Privacy Policy",
                         "content": "Updated privacy policy v2"})
    assert r.status_code == 200
    r = client.get("/api/settings/legal/privacy_policy")
    assert r.json()["content"] == "Updated privacy policy v2"
    # unknown key is rejected
    r = client.get("/api/settings/legal/nonexistent", headers=auth)
    assert r.status_code == 404


def test_404_and_validation_errors(client, auth):
    r = client.get("/api/nonexistent-endpoint", headers=auth)
    assert r.status_code == 404
    assert r.json()["detail"] == "Not found"
    r = client.post("/api/customers", headers=auth, json={"name": ""})
    assert r.status_code == 422
    r = client.get("/api/customers/999999", headers=auth)
    assert r.status_code == 404


def test_database_file_created_in_data_dir():
    from app.core.config import DATA_DIR
    assert (Path(DATA_DIR) / "auto_workshop.db").exists()


def test_sqlite_foreign_keys_enforced():
    import sqlite3
    from app.core.config import DATABASE_URL
    path = DATABASE_URL.replace("sqlite:///", "")
    con = sqlite3.connect(path)
    try:
        assert con.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        con.close()


def test_stock_never_negative_invariant(client, auth):
    pid = client.post("/api/products", headers=auth, json={
        "name": "InvariantItem", "sku": "INV-1",
        "selling_price_paisa": 1000, "purchase_cost_paisa": 500}).json()["id"]
    client.post("/api/inventory/receive", headers=auth, json={
        "product_id": pid, "quantity": 2, "unit_cost_paisa": 500,
        "reference_number": "GRN-I"})
    # try to sell more than stock
    r = client.post("/api/pos/invoices", headers=auth, json={
        "items": [{"item_type": "product", "product_id": pid,
                   "quantity": 5, "unit_price_paisa": 1000}],
        "payments": [{"amount_paisa": 5000, "method": "cash"}]})
    assert r.status_code == 400
    p = client.get(f"/api/products/{pid}", headers=auth).json()
    assert p["quantity_on_hand"] == 2


def test_version_and_schema_upgrade_idempotent(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["version"] == "1.2.2"
    from app.core.database import get_engine, upgrade_schema
    upgrade_schema(get_engine())

