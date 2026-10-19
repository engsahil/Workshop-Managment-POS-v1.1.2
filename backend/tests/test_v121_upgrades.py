"""Comprehensive v1.2.1 regression test suite.

Covers:
1. Frontend module & router contract (named `pages` export in `pages/index.js`,
   valid imports/exports across all 20 page modules, unique routes, and JS syntax check).
2. Complete alignment of all frontend `/api/*` calls with registered FastAPI OpenAPI routes
   (specifically verifying `returns.js` uses `/api/invoices/returns`,
   `/api/invoices/returns/{rid}/decide`, and `/api/claims`).
3. End-to-end Sale Returns & Refunds + Warranty Claims workflow (partial return,
   remaining returnable quantity validation, refund calculation, and claim CRUD + delete).
4. White + Off-White + Beach/Sand theme tokens and Light/Dark mode support.
5. Installable PWA manifest (`/manifest.webmanifest`), PNG icons (`192x192`, `512x512`,
   `maskable`), and production-safe Service Worker (`/sw.js`).
"""
import pathlib
import re
import shutil
import struct
import subprocess

from app.core.config import APP_VERSION, FRONTEND_DIR
from app.main import app


def test_version_is_current(client):
    assert APP_VERSION == "1.2.2"
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "version": "1.2.2"}


def test_frontend_module_and_router_contract():
    pages_dir = FRONTEND_DIR / "assets" / "js" / "pages"
    core_dir = FRONTEND_DIR / "assets" / "js" / "core"
    index_js = (pages_dir / "index.js").read_text(encoding="utf-8")
    app_js = (core_dir / "app.js").read_text(encoding="utf-8")

    # 1. app.js imports named `{ pages }` and pages/index.js exports named `export const pages`
    assert re.search(r'import\s+\{\s*pages\s*\}\s+from\s+"\.\./pages/index\.js"', app_js)
    assert re.search(r"export\s+const\s+pages\s*=\s*\[", index_js)
    assert "export default pages;" in index_js

    # 2. Every symbol imported by pages/index.js is exported by its target module
    imports = re.findall(r'import\s+\{([^}]+)\}\s+from\s+"\./([^"]+)"', index_js)
    assert len(imports) >= 20
    for syms_raw, rel_file in imports:
        target = pages_dir / rel_file
        assert target.is_file(), f"Missing page module: {rel_file}"
        content = target.read_text(encoding="utf-8")
        for sym in [s.strip() for s in syms_raw.split(",") if s.strip()]:
            assert re.search(
                rf"export\s+(?:async\s+)?function\s+{re.escape(sym)}\b|export\s+const\s+{re.escape(sym)}\b",
                content,
            ), f"Symbol {sym} not exported by {rel_file}"

    # 3. Route keys in pages/index.js are unique and cover all NAV_ITEMS in app.js
    route_keys = re.findall(r'route:\s*"([^"]+)"', index_js)
    assert len(route_keys) == len(set(route_keys)), "Duplicate route keys in pages/index.js"
    nav_paths = re.findall(r'path:\s*"/([^"]+)"', app_js)
    for nav_route in nav_paths:
        assert nav_route in route_keys, f"NAV_ITEMS route /{nav_route} missing from pages/index.js"

    # 4. Syntax check + full ES-module graph runtime import check with Node.js
    node_bin = shutil.which("node")
    if node_bin:
        js_files = list((FRONTEND_DIR / "assets" / "js").rglob("*.js")) + [FRONTEND_DIR / "sw.js"]
        for jf in js_files:
            proc = subprocess.run([node_bin, "--check", str(jf)], capture_output=True, text=True)
            assert proc.returncode == 0, f"JS syntax error in {jf.name}: {proc.stderr}"

        esm_script = f"""
import {{ pages }} from "{(pages_dir / 'index.js').as_posix()}";
import {{ appState, refreshHeaderContext, openDailySummaryModal }} from "{(core_dir / 'app.js').as_posix()}";
if (!Array.isArray(pages) || pages.length < 20) throw new Error("pages registry invalid");
if (typeof refreshHeaderContext !== "function") throw new Error("refreshHeaderContext missing");
if (typeof openDailySummaryModal !== "function") throw new Error("openDailySummaryModal missing");
for (const entry of pages) {{
  const fn = await entry.load();
  if (typeof fn !== "function") throw new Error("Invalid loader for " + entry.route);
}}
"""
        esm_proc = subprocess.run(
            [node_bin, "--experimental-default-type=module", "-e", esm_script],
            capture_output=True,
            text=True,
        )
        assert esm_proc.returncode == 0, f"ESM runtime import failed: {esm_proc.stderr}"


def test_all_frontend_api_calls_match_backend_openapi_routes():
    schema = app.openapi()
    paths = schema["paths"]
    backend_routes = []
    for path, ops in paths.items():
        methods = {m.upper() for m in ops.keys()}
        pattern = "^" + re.sub(r"\{[^}]+\}", r"[^/]+", path) + "$"
        backend_routes.append((methods, path, re.compile(pattern)))

    js_root = FRONTEND_DIR / "assets" / "js"
    call_re = re.compile(r'api\.(get|post|put|del)\(\s*[`"\']([^`"\']+)[`"\']')
    mismatches = []
    total_checked = 0

    for p in sorted(js_root.rglob("*.js")):
        text = p.read_text(encoding="utf-8")
        for line_no, line in enumerate(text.splitlines(), 1):
            for m in call_re.finditer(line):
                verb = m.group(1).upper()
                if verb == "DEL":
                    verb = "DELETE"
                raw_url = m.group(2)
                clean_url = re.sub(r"\$\{(q|qs)\}$", "", raw_url)
                clean_url = re.sub(r"\$\{[^}]+\}", "1", clean_url).split("?")[0]
                if not clean_url.startswith("/api/"):
                    continue
                total_checked += 1
                matched = any(
                    verb in methods and regex.match(clean_url)
                    for methods, _, regex in backend_routes
                )
                if not matched:
                    mismatches.append((p.name, line_no, verb, raw_url))

    assert total_checked >= 140
    assert mismatches == [], f"Frontend API calls do not match backend routes: {mismatches}"

    # Specifically verify returns.js never calls dead `/api/returns`
    returns_js = (js_root / "pages" / "returns.js").read_text(encoding="utf-8")
    assert '"/api/invoices/returns' in returns_js or "`/api/invoices/returns" in returns_js
    assert not re.search(r'api\.(get|post|put|del)\(\s*[`"\']/api/returns\b', returns_js)


def test_returns_and_warranty_claims_full_workflow(client, auth):
    # 1. Create product with stock=5 and sell 3 units on a POS invoice
    pr = client.post(
        "/api/products",
        headers=auth,
        json={
            "sku": "V121-RET-01",
            "name": "v1.2.1 Ceramic Brake Pad Set",
            "unit": "set",
            "purchase_cost_paisa": 150000,
            "selling_price_paisa": 250000,
            "reorder_level": 1,
            "warranty_days": 90,
        },
    )
    assert pr.status_code == 200, pr.text
    prod = pr.json()
    rec = client.post(
        "/api/inventory/receive",
        headers=auth,
        json={
            "product_id": prod["id"],
            "quantity": 5,
            "unit_cost_paisa": 150000,
            "notes": "Initial v1.2.1 test stock",
        },
    )
    assert rec.status_code == 200, rec.text

    inv_res = client.post(
        "/api/pos/invoices",
        headers=auth,
        json={
            "items": [
                {
                    "item_type": "product",
                    "product_id": prod["id"],
                    "quantity": 3,
                    "unit_price_paisa": 250000,
                }
            ],
            "payments": [{"amount_paisa": 750000, "method": "cash"}],
        },
    )
    assert inv_res.status_code == 200, inv_res.text
    inv = inv_res.json()
    line = inv["items"][0]
    assert line["returned_quantity"] == 0.0
    assert line["returnable_quantity"] == 3.0

    # 2. Submit a return of 1 unit and approve it
    ret_res = client.post(
        "/api/invoices/returns",
        headers=auth,
        json={
            "invoice_id": inv["id"],
            "restock_action": "restock",
            "refund_method": "cash",
            "reason": "Customer ordered 1 extra set",
            "items": [{"invoice_item_id": line["id"], "quantity": 1}],
        },
    )
    assert ret_res.status_code == 200, ret_res.text
    ret_data = ret_res.json()
    assert ret_data["total_paisa"] == 250000

    # Verify GET /api/invoices/returns returns customer_name and invoice_number
    list_res = client.get("/api/invoices/returns?page_size=20", headers=auth)
    assert list_res.status_code == 200
    found = next((x for x in list_res.json()["items"] if x["id"] == ret_data["id"]), None)
    assert found is not None
    assert found["invoice_number"] == inv["invoice_number"]
    assert found["customer_name"] == "Walk-in Customer"

    # Approve the return
    dec_res = client.post(
        f"/api/invoices/returns/{ret_data['id']}/decide",
        headers=auth,
        json={"status": "approved", "notes": "Verified sealed box"},
    )
    assert dec_res.status_code == 200

    # 3. Re-fetch invoice and verify returned_quantity=1.0, returnable_quantity=2.0
    inv_after = client.get(f"/api/invoices/{inv['id']}", headers=auth).json()
    line_after = inv_after["items"][0]
    assert line_after["returned_quantity"] == 1.0
    assert line_after["returnable_quantity"] == 2.0

    # Attempting to return 3 units when only 2 remain returnable fails with 400
    over_ret = client.post(
        "/api/invoices/returns",
        headers=auth,
        json={
            "invoice_id": inv["id"],
            "restock_action": "restock",
            "refund_method": "cash",
            "items": [{"invoice_item_id": line["id"], "quantity": 3}],
        },
    )
    assert over_ret.status_code == 400

    # 4. Warranty claim create -> get -> update -> delete lifecycle
    clm_res = client.post(
        "/api/claims",
        headers=auth,
        json={
            "invoice_id": inv["id"],
            "item_type": "product",
            "product_id": prod["id"],
            "description": "Squeaking noise on front-left pad",
            "inspection_notes": "Checked rotor alignment",
            "action_taken": "Replaced pad set under warranty",
            "status": "open",
        },
    )
    assert clm_res.status_code == 200, clm_res.text
    clm = clm_res.json()
    assert clm["is_within_warranty"] is True

    get_clm = client.get(f"/api/claims/{clm['id']}", headers=auth)
    assert get_clm.status_code == 200
    assert get_clm.json()["claim_number"] == clm["claim_number"]

    upd_clm = client.put(
        f"/api/claims/{clm['id']}",
        headers=auth,
        json={"status": "resolved", "resolution": "replaced", "cost_paisa": 150000},
    )
    assert upd_clm.status_code == 200
    assert upd_clm.json()["status"] == "resolved"

    del_clm = client.delete(f"/api/claims/{clm['id']}", headers=auth)
    assert del_clm.status_code == 200
    assert del_clm.json()["ok"] is True
    assert client.get(f"/api/claims/{clm['id']}", headers=auth).status_code == 404


def test_white_offwhite_beach_theme_and_pwa_assets(client):
    # 1. Verify CSS theme palette in app.css
    css = (FRONTEND_DIR / "assets" / "css" / "app.css").read_text(encoding="utf-8")
    for token in ("#FFFFFF", "#FAF9F6", "#F4F0E8", "#DCCBB2", "#BBA486", "#292824", "#706C64", "#E8E2D8"):
        assert token.lower() in css.lower(), f"Missing White/Off-White/Beach theme color {token} in app.css"
    assert 'html[data-theme="light"]' in css
    assert 'html[data-theme="dark"]' in css

    # 2. Verify /manifest.webmanifest
    m_res = client.get("/manifest.webmanifest")
    assert m_res.status_code == 200
    assert "application/manifest+json" in m_res.headers.get("content-type", "")
    manifest = m_res.json()
    assert manifest["name"] == "Auto Workshop Management POS"
    assert manifest["display"] == "standalone"
    assert manifest["start_url"] == "/"
    assert manifest["scope"] == "/"
    assert manifest["theme_color"].upper() == "#FAF9F6"
    assert manifest["background_color"].upper() == "#FFFFFF"
    assert len(manifest["icons"]) >= 3

    # 3. Verify PNG icons exist, serve HTTP 200, and have valid PNG headers + dimensions
    for icon_entry in manifest["icons"]:
        ic_res = client.get(icon_entry["src"])
        assert ic_res.status_code == 200
        raw = ic_res.content
        assert raw[:8] == b"\x89PNG\r\n\x1a\n"
        width, height = struct.unpack(">II", raw[16:24])
        expected_w, expected_h = [int(x) for x in icon_entry["sizes"].split("x")]
        assert (width, height) == (expected_w, expected_h)

    # 4. Verify /sw.js service worker safety rules and headers
    sw_res = client.get("/sw.js")
    assert sw_res.status_code == 200
    assert "javascript" in sw_res.headers.get("content-type", "")
    assert sw_res.headers.get("service-worker-allowed") == "/"
    sw_text = sw_res.text
    assert 'url.pathname.startsWith("/api/")' in sw_text
    assert 'request.headers.get("Authorization")' in sw_text
