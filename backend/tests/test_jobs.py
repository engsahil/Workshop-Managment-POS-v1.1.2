"""Job card workflow, estimates, approvals, mechanic commission tests."""


def setup_job(client, auth):
    """Create customer, vehicle, 2 services, a stocked product, a mechanic."""
    setup_job.n += 1
    n = setup_job.n
    cid = client.post("/api/customers", headers=auth, json={
        "name": f"Job Cust {n}", "phone": f"030099988{n:02d}"}).json()["id"]
    vid = client.post("/api/vehicles", headers=auth, json={
        "customer_id": cid, "make": "Honda", "model": "CD70",
        "year": 2015, "plate_number": f"LEF-{n}"}).json()["id"]
    s1 = client.post("/api/services", headers=auth, json={
        "name": f"Engine Tune-up {n}", "code": f"SVC-TUNE-{n}",
        "default_charge_paisa": 5000,
        "category": "Mechanical", "estimated_minutes": 60}).json()["id"]
    s2 = client.post("/api/services", headers=auth, json={
        "name": f"Oil Change {n}", "code": f"SVC-OIL-{n}",
        "default_charge_paisa": 2000,
        "category": "Mechanical", "estimated_minutes": 20}).json()["id"]
    pid = client.post("/api/products", headers=auth, json={
        "name": f"Engine Oil {n}", "sku": f"EO-{n}",
        "selling_price_paisa": 3500, "purchase_cost_paisa": 2000,
    }).json()["id"]
    client.post("/api/inventory/receive", headers=auth, json={
        "product_id": pid, "quantity": 10, "unit_cost_paisa": 2000,
        "reference_number": f"GRN-J{n}"})
    mid = client.post("/api/mechanics", headers=auth, json={
        "name": f"Mechanic A {n}", "skill": "Engine",
        "commission_type": "percent_per_job",
        "commission_value": 1000}).json()["id"]  # 10% (stored as %*100)
    return {"customer": cid, "vehicle": vid, "service1": s1,
            "service2": s2, "product": pid, "mechanic": mid}


setup_job.n = 0


def test_job_creation_and_estimate(client, auth):
    ids = setup_job(client, auth)
    r = client.post("/api/jobs", headers=auth, json={
        "customer_id": ids["customer"], "vehicle_id": ids["vehicle"],
        "reported_issue": "engine knocking",
        "complaint": "knock on acceleration",
        "est_labor_paisa": 9000, "est_parts_paisa": 3500,
        "mechanic_id": ids["mechanic"]})
    assert r.status_code == 200, r.text
    job = r.json()
    assert job["status"] == "received"
    assert job["job_number"].startswith("JB-")
    assert job["est_labor_paisa"] == 9000
    assert job["est_parts_paisa"] == 3500
    assert job["approval_status"] == "pending"  # estimate needs sign-off
    # add service + part lines
    r = client.post(f"/api/jobs/{job['id']}/services", headers=auth, json={
        "service_id": ids["service1"], "description": "Engine Tune-up",
        "quantity": 1, "unit_charge_paisa": 5000,
        "mechanic_id": ids["mechanic"]})
    assert r.status_code == 200
    r = client.post(f"/api/jobs/{job['id']}/services", headers=auth, json={
        "service_id": ids["service2"], "description": "Oil Change x2",
        "quantity": 2, "unit_charge_paisa": 2000,
        "mechanic_id": ids["mechanic"]})
    assert r.status_code == 200
    r = client.post(f"/api/jobs/{job['id']}/parts", headers=auth, json={
        "product_id": ids["product"], "quantity": 1,
        "unit_price_paisa": 3500})
    assert r.status_code == 200
    # parts deducted at line-add time, exactly once
    p = client.get(f"/api/products/{ids['product']}", headers=auth).json()
    assert p["quantity_on_hand"] == 9
    detail = client.get(f"/api/jobs/{job['id']}", headers=auth).json()
    assert len(detail["services"]) == 2
    assert len(detail["parts"]) == 1


def test_job_status_flow_with_approval(client, auth):
    ids = setup_job(client, auth)
    job = client.post("/api/jobs", headers=auth, json={
        "customer_id": ids["customer"], "vehicle_id": ids["vehicle"],
        "reported_issue": "brake squeal",
        "est_labor_paisa": 5000, "est_parts_paisa": 0,
        "mechanic_id": ids["mechanic"]}).json()
    jid = job["id"]
    # invalid transition: received -> in_progress is not allowed
    r = client.post(f"/api/jobs/{jid}/status", headers=auth,
                    json={"status": "in_progress"})
    assert r.status_code == 400
    # walk the workflow
    for st in ("inspection", "awaiting_approval"):
        r = client.post(f"/api/jobs/{jid}/status", headers=auth,
                        json={"status": st})
        assert r.json()["status"] == st, st
    # completion blocked while estimate approval pending
    client.post(f"/api/jobs/{jid}/status", headers=auth,
                json={"status": "approved"})
    client.post(f"/api/jobs/{jid}/status", headers=auth,
                json={"status": "in_progress"})
    r = client.post(f"/api/jobs/{jid}/status", headers=auth,
                    json={"status": "completed"})
    assert r.status_code == 400  # estimate not approved yet
    # customer approves the estimate
    r = client.post(f"/api/jobs/{jid}/approval", headers=auth,
                    json={"approval_status": "approved"})
    assert r.json()["approval_status"] == "approved"
    r = client.post(f"/api/jobs/{jid}/status", headers=auth,
                    json={"status": "completed"})
    assert r.json()["status"] == "completed"
    # delivery
    r = client.post(f"/api/jobs/{jid}/status", headers=auth,
                    json={"status": "ready_for_delivery"})
    assert r.json()["status"] == "ready_for_delivery"
    r = client.post(f"/api/jobs/{jid}/status", headers=auth,
                    json={"status": "delivered"})
    assert r.json()["status"] == "delivered"
    # delivered is terminal
    r = client.post(f"/api/jobs/{jid}/status", headers=auth,
                    json={"status": "completed"})
    assert r.status_code == 400


def test_job_invoice_and_no_double_deduction(client, auth):
    ids = setup_job(client, auth)
    job = client.post("/api/jobs", headers=auth, json={
        "customer_id": ids["customer"], "vehicle_id": ids["vehicle"],
        "reported_issue": "chain noise",
        "est_labor_paisa": 5000, "est_parts_paisa": 3500,
        "mechanic_id": ids["mechanic"]}).json()
    jid = job["id"]
    client.post(f"/api/jobs/{jid}/services", headers=auth, json={
        "service_id": ids["service1"], "description": "Service",
        "quantity": 1, "unit_charge_paisa": 5000,
        "mechanic_id": ids["mechanic"]})
    client.post(f"/api/jobs/{jid}/parts", headers=auth, json={
        "product_id": ids["product"], "quantity": 1,
        "unit_price_paisa": 3500})
    client.post(f"/api/jobs/{jid}/approval", headers=auth,
                json={"approval_status": "approved"})
    for st in ("inspection", "awaiting_approval", "approved",
               "in_progress", "completed", "ready_for_delivery"):
        client.post(f"/api/jobs/{jid}/status", headers=auth,
                    json={"status": st})
    inv = client.post(f"/api/jobs/{jid}/invoice", headers=auth,
                      json={"payments": [{"amount_paisa": 8500,
                                            "method": "cash"}]}).json()
    assert inv["total_paisa"] == 8500  # 5000 labor + 3500 parts
    assert inv["job_id"] == jid
    # parts NOT deducted a second time
    p = client.get(f"/api/products/{ids['product']}",
                   headers=auth).json()
    assert p["quantity_on_hand"] == 9  # still 9 (deducted once at line-add)
    # stock movement records the job as its source transaction
    mv = client.get(f"/api/inventory/movements?product_id={ids['product']}",
                    headers=auth).json()["items"]
    assert any(m["reference_type"] == "job"
               and m["reference_id"] == jid
               and m["movement_type"] == "job_consume"
               for m in mv)
    # job cannot be invoiced twice
    r = client.post(f"/api/jobs/{jid}/invoice", headers=auth,
                    json={"payments": []})
    assert r.status_code == 400


def test_job_invoice_credit_and_payment(client, auth):
    ids = setup_job(client, auth)
    job = client.post("/api/jobs", headers=auth, json={
        "customer_id": ids["customer"], "vehicle_id": ids["vehicle"],
        "reported_issue": "clutch slip",
        "est_labor_paisa": 2000, "est_parts_paisa": 0,
        "mechanic_id": ids["mechanic"]}).json()
    jid = job["id"]
    client.post(f"/api/jobs/{jid}/services", headers=auth, json={
        "service_id": ids["service2"], "description": "Oil change",
        "quantity": 1, "unit_charge_paisa": 2000,
        "mechanic_id": ids["mechanic"]})
    client.post(f"/api/jobs/{jid}/approval", headers=auth,
                json={"approval_status": "approved"})
    for st in ("inspection", "awaiting_approval", "approved",
               "in_progress", "completed", "ready_for_delivery"):
        client.post(f"/api/jobs/{jid}/status", headers=auth,
                    json={"status": st})
    inv = client.post(f"/api/jobs/{jid}/invoice", headers=auth,
                      json={"payments": []}).json()  # credit
    assert inv["status"] == "credit"
    assert inv["balance_paisa"] == 2000
    r = client.post(f"/api/invoices/{inv['id']}/payments", headers=auth,
                    json={"amount_paisa": 2000, "method": "cash"})
    assert r.json()["status"] == "paid"
    assert client.get(f"/api/customers/{ids['customer']}",
                      headers=auth).json()["balance_paisa"] == 0


def test_mechanic_commission_derived(client, auth):
    ids = setup_job(client, auth)
    job = client.post("/api/jobs", headers=auth, json={
        "customer_id": ids["customer"], "vehicle_id": ids["vehicle"],
        "reported_issue": "tune",
        "est_labor_paisa": 5000, "est_parts_paisa": 3500,
        "mechanic_id": ids["mechanic"]}).json()
    jid = job["id"]
    client.post(f"/api/jobs/{jid}/services", headers=auth, json={
        "service_id": ids["service1"], "description": "Tune-up",
        "quantity": 1, "unit_charge_paisa": 5000,
        "mechanic_id": ids["mechanic"]})
    client.post(f"/api/jobs/{jid}/parts", headers=auth, json={
        "product_id": ids["product"], "quantity": 1,
        "unit_price_paisa": 3500})
    client.post(f"/api/jobs/{jid}/approval", headers=auth,
                json={"approval_status": "approved"})
    for st in ("inspection", "awaiting_approval", "approved",
               "in_progress", "completed", "ready_for_delivery"):
        client.post(f"/api/jobs/{jid}/status", headers=auth,
                    json={"status": st})
    client.post(f"/api/jobs/{jid}/invoice", headers=auth,
                json={"payments": [{"amount_paisa": 8500,
                                      "method": "cash"}]})
    # commission = 10% of labor 5000 = 500 (parts excluded)
    perf = client.get("/api/reports/mechanic-performance",
                      headers=auth).json()
    m = [x for x in perf if x["mechanic_id"] == ids["mechanic"]]
    assert m and m[0]["commission_due_paisa"] == 500


def test_estimate_revision_reopens_approval(client, auth):
    ids = setup_job(client, auth)
    job = client.post("/api/jobs", headers=auth, json={
        "customer_id": ids["customer"], "vehicle_id": ids["vehicle"],
        "reported_issue": "electrical",
        "est_labor_paisa": 5000, "est_parts_paisa": 0,
        "mechanic_id": ids["mechanic"]}).json()
    jid = job["id"]
    client.post(f"/api/jobs/{jid}/approval", headers=auth,
                json={"approval_status": "approved"})
    # revise the estimate upward -> approval re-opened
    r = client.put(f"/api/jobs/{jid}", headers=auth,
                   json={"est_labor_paisa": 7000})
    assert r.json()["approval_status"] == "pending"


def test_customer_and_vehicle_pagination_total(client, auth):
    c_res = client.get("/api/customers?page=1&page_size=5", headers=auth).json()
    assert "total" in c_res and c_res["total"] >= 1
    v_res = client.get("/api/vehicles?page=1&page_size=5", headers=auth).json()
    assert "total" in v_res and v_res["total"] >= 1


def test_vehicle_detail_associations(client, auth):
    cid = client.post("/api/customers", headers=auth, json={
        "name": "VehAssoc Owner", "phone": "03119998877"}).json()["id"]
    vid = client.post("/api/vehicles", headers=auth, json={
        "customer_id": cid, "vehicle_type": "car",
        "registration_no": "KHI-9988", "make": "Toyota",
        "model": "Corolla", "year": 2022, "odometer": 15000}).json()["id"]
    job = client.post("/api/jobs", headers=auth, json={
        "customer_id": cid, "vehicle_id": vid, "odometer": 18500,
        "reported_issue": "brake pad check"}).json()
    jid = job["id"]
    for st in ("inspection", "awaiting_approval", "approved",
               "in_progress", "completed", "ready_for_delivery"):
        client.post(f"/api/jobs/{jid}/status", headers=auth, json={"status": st})
    sid = client.post("/api/services", headers=auth, json={
        "name": "Brake Inspection", "code": "SRV-BRK-99",
        "default_charge_paisa": 150000}).json()["id"]
    client.post(f"/api/jobs/{jid}/services", headers=auth, json={
        "service_id": sid, "description": "Brake Inspection",
        "quantity": 1, "unit_charge_paisa": 150000})
    client.post(f"/api/jobs/{jid}/invoice", headers=auth, json={
        "payments": [{"amount_paisa": 150000, "method": "cash"}]})

    v_detail = client.get(f"/api/vehicles/{vid}", headers=auth).json()
    assert v_detail["vehicle_type"] == "car"
    assert v_detail["last_odometer"] == 18500
    assert len(v_detail["history"]) >= 1
    assert len(v_detail["invoices"]) >= 1
    assert len(v_detail["odometer_history"]) >= 2
    assert [o["odometer"] for o in v_detail["odometer_history"]][:2] == [15000, 18500]

