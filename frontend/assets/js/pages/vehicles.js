// Vehicles — motorcycle & car registry, odometer & service history.
import { api } from "../core/api.js";
import { badge, confirmDialog, emptyState, esc, fmtDateTime, formData, money, openModal, toast } from "../core/ui.js";

export function openQuickVehicleModal(customers, defaultCustomerId, onCreated) {
  const custList = Array.isArray(customers) ? customers : (customers?.items || []);
  const { close, root } = openModal({
    title: "Register New Vehicle",
    body: `
      <form id="qv-form">
        <div class="form-row">
          <label><span>Owner (Customer) *</span>
            <select name="customer_id" required>
              <option value="">Select customer…</option>
              ${custList.map(c => `<option value="${c.id}" ${Number(defaultCustomerId) === c.id ? "selected" : ""}>${esc(c.name)} (${esc(c.phone || c.code)})</option>`).join("")}
            </select>
          </label>
          <label><span>Vehicle Type *</span>
            <select name="vehicle_type">
              <option value="motorcycle">Motorcycle</option>
              <option value="car">Car</option>
              <option value="other">Other</option>
            </select>
          </label>
        </div>
        <div class="form-row">
          <label><span>Registration / Plate *</span><input name="registration_no" required placeholder="ABC-1234" /></label>
          <label><span>Make</span><input name="make" placeholder="Honda / Toyota / Suzuki" /></label>
          <label><span>Model</span><input name="model" placeholder="CG125 / Corolla / Alto" /></label>
        </div>
        <div class="form-row">
          <label><span>Year</span><input name="year" type="number" min="1960" max="2100" /></label>
          <label><span>Color</span><input name="color" /></label>
          <label><span>Odometer (km)</span><input name="odometer" type="number" min="0" /></label>
        </div>
        <div class="modal-foot">
          <button type="button" class="btn btn-ghost" data-close>Cancel</button>
          <button type="submit" class="btn btn-primary" id="qv-submit">Register Vehicle</button>
        </div>
      </form>`,
  });
  const form = root.querySelector("#qv-form");
  form.onsubmit = async (e) => {
    e.preventDefault();
    const btn = root.querySelector("#qv-submit");
    btn.disabled = true;
    try {
      const fd = formData(form);
      const payload = {
        customer_id: Number(fd.customer_id),
        vehicle_type: fd.vehicle_type || "motorcycle",
        registration_no: (fd.registration_no || "").trim(),
        make: fd.make || null,
        model: fd.model || null,
        year: fd.year ? Number(fd.year) : null,
        color: fd.color || null,
        odometer: fd.odometer ? Number(fd.odometer) : null,
      };
      const created = await api.post("/api/vehicles", payload);
      toast("Vehicle registered");
      close();
      if (onCreated) await onCreated(created);
    } catch (err) {
      toast(err.message, "err");
      btn.disabled = false;
    }
  };
}

export async function renderVehicles(root, params = {}) {
  root.innerHTML = `
    <div class="toolbar">
      <input id="v-q" placeholder="Search plate, make, model, engine, chassis…" style="min-width:260px" />
      <select id="v-type">
        <option value="">All types</option>
        <option value="motorcycle">Motorcycle</option>
        <option value="car">Car</option>
        <option value="other">Other</option>
      </select>
      <button class="btn btn-ghost btn-sm" id="v-search">Filter</button>
      <span class="spacer"></span>
      <button class="btn btn-primary" id="v-new">+ Register Vehicle</button>
    </div>
    <div class="card" id="v-list"></div>
  `;

  async function load() {
    const q = encodeURIComponent(root.querySelector("#v-q").value.trim());
    const t = root.querySelector("#v-type").value;
    const cid = params.customer_id ? `&customer_id=${params.customer_id}` : "";
    const res = await api.get(`/api/vehicles?q=${q}&vehicle_type=${t}${cid}&page_size=100`);
    const list = root.querySelector("#v-list");
    if (!res.items.length) { list.innerHTML = emptyState("No vehicles registered"); return; }
    list.innerHTML = `
      <div class="table-wrap">
        <table class="tbl">
          <thead><tr><th>Type</th><th>Registration</th><th>Make / Model</th><th>Year</th><th>Color</th><th>Owner</th><th class="num">Odometer</th><th></th></tr></thead>
          <tbody>
            ${res.items.map(v => `
              <tr>
                <td>${badge(v.vehicle_type)}</td>
                <td class="mono"><strong>${esc(v.registration_no || "—")}</strong></td>
                <td>${esc([v.make, v.model].filter(Boolean).join(" ") || "—")}</td>
                <td>${v.year || "—"}</td>
                <td>${esc(v.color || "—")}</td>
                <td><a href="#/customers?id=${v.customer_id}">${esc(v.customer_name || "")}</a></td>
                <td class="num">${v.odometer != null ? v.odometer.toLocaleString() + " km" : "—"}</td>
                <td class="right">
                  <button class="btn btn-ghost btn-sm" data-hist="${v.id}">History</button>
                  <button class="btn btn-ghost btn-sm" data-edit="${v.id}">Edit</button>
                  <button class="btn btn-ghost btn-sm" data-del="${v.id}">Delete</button>
                </td>
              </tr>`).join("")}
          </tbody>
        </table>
      </div>`;
    list.querySelectorAll("[data-edit]").forEach(b => b.onclick = () => {
      const v = res.items.find(x => x.id === Number(b.dataset.edit));
      openEditor(v, load);
    });
    list.querySelectorAll("[data-hist]").forEach(b => b.onclick = () => openHistory(Number(b.dataset.hist)));
    list.querySelectorAll("[data-del]").forEach(b => b.onclick = async () => {
      if (!await confirmDialog("Delete this vehicle?")) return;
      try { await api.del(`/api/vehicles/${b.dataset.del}`); toast("Deleted"); load(); }
      catch (e) { toast(e.message, "err"); }
    });
  }

  root.querySelector("#v-search").onclick = load;
  root.querySelector("#v-q").onkeydown = (e) => { if (e.key === "Enter") load(); };
  root.querySelector("#v-type").onchange = load;
  root.querySelector("#v-new").onclick = () => openEditor(params.customer_id ? { customer_id: Number(params.customer_id) } : null, load);

  await load();
  if (params.id) openHistory(Number(params.id));
}

async function openEditor(v, onDone) {
  const isNew = !v || !v.id;
  const custs = await api.get("/api/customers?page_size=200");
  const { close, root } = openModal({
    title: isNew ? "Register Vehicle" : `Edit ${v.registration_no || "Vehicle"}`,
    body: `
      <form id="v-form">
        <div class="form-row">
          <label><span>Owner (Customer) *</span>
            <select name="customer_id" required>
              <option value="">Select customer…</option>
              ${(custs.items || []).map(c => `<option value="${c.id}" ${v?.customer_id === c.id ? "selected" : ""}>${esc(c.name)} (${esc(c.phone || c.code)})</option>`).join("")}
            </select>
          </label>
          <label><span>Vehicle Type *</span>
            <select name="vehicle_type">
              ${["motorcycle", "car", "other"].map(t => `<option value="${t}" ${(v?.vehicle_type || "motorcycle") === t ? "selected" : ""}>${t}</option>`).join("")}
            </select>
          </label>
        </div>
        <div class="form-row">
          <label><span>Registration / Plate</span><input name="registration_no" value="${esc(v?.registration_no || "")}" placeholder="ABC-1234" /></label>
          <label><span>Make</span><input name="make" value="${esc(v?.make || "")}" placeholder="Honda / Toyota / Suzuki" /></label>
          <label><span>Model</span><input name="model" value="${esc(v?.model || "")}" placeholder="CG125 / Corolla / Alto" /></label>
        </div>
        <div class="form-row">
          <label><span>Year</span><input name="year" type="number" min="1960" max="2100" value="${v?.year || ""}" /></label>
          <label><span>Color</span><input name="color" value="${esc(v?.color || "")}" /></label>
          <label><span>Fuel Type</span>
            <select name="fuel_type">
              ${["petrol", "diesel", "cng", "hybrid", "electric", "unknown"].map(f => `<option value="${f}" ${(v?.fuel_type || "petrol") === f ? "selected" : ""}>${f}</option>`).join("")}
            </select>
          </label>
        </div>
        <div class="form-row">
          <label><span>Engine No.</span><input name="engine_no" value="${esc(v?.engine_no || "")}" /></label>
          <label><span>Chassis / VIN</span><input name="chassis_no" value="${esc(v?.chassis_no || "")}" /></label>
          <label><span>Odometer (km)</span><input name="odometer" type="number" min="0" value="${v?.odometer ?? ""}" /></label>
        </div>
        <label><span>Notes</span><textarea name="notes">${esc(v?.notes || "")}</textarea></label>
        <div class="modal-foot">
          <button type="button" class="btn btn-ghost" data-close>Cancel</button>
          <button type="submit" class="btn btn-primary">${isNew ? "Register" : "Save"}</button>
        </div>
      </form>`,
  });
  root.querySelector("#v-form").onsubmit = async (e) => {
    e.preventDefault();
    const fd = formData(e.target);
    const payload = {
      customer_id: Number(fd.customer_id),
      vehicle_type: fd.vehicle_type,
      registration_no: fd.registration_no || null,
      make: fd.make || null,
      model: fd.model || null,
      year: fd.year ? Number(fd.year) : null,
      color: fd.color || null,
      fuel_type: fd.fuel_type || null,
      engine_no: fd.engine_no || null,
      chassis_no: fd.chassis_no || null,
      odometer: fd.odometer ? Number(fd.odometer) : null,
      notes: fd.notes || null,
    };
    try {
      if (isNew) await api.post("/api/vehicles", payload);
      else await api.put(`/api/vehicles/${v.id}`, payload);
      toast(isNew ? "Vehicle registered" : "Vehicle updated");
      close();
      onDone && onDone();
    } catch (err) { toast(err.message, "err"); }
  };
}

async function openHistory(vid) {
  const v = await api.get(`/api/vehicles/${vid}`);
  const jobs = v.history || [];
  const invoices = v.invoices || [];
  const odoLog = v.odometer_history || [];
  openModal({
    title: `${v.registration_no || "Vehicle"} — ${[v.make, v.model].filter(Boolean).join(" ")}`,
    size: "lg",
    body: `
      <div class="kpi-grid">
        <div class="kpi">
          <div class="k-label">Owner</div>
          <div class="k-value" style="font-size:15px">${esc(v.customer_name || "—")}</div>
          <div class="k-sub">${esc(v.vehicle_type || "motorcycle")} · ${esc(v.fuel_type || "petrol")}</div>
        </div>
        <div class="kpi info">
          <div class="k-label">Latest Odometer</div>
          <div class="k-value" style="font-size:16px">${v.last_odometer != null ? Number(v.last_odometer).toLocaleString() + " km" : "—"}</div>
          <div class="k-sub">${odoLog.length} recorded reading(s)</div>
        </div>
        <div class="kpi">
          <div class="k-label">Service Visits</div>
          <div class="k-value" style="font-size:16px">${jobs.length}</div>
          <div class="k-sub">${invoices.length} invoice(s)</div>
        </div>
      </div>

      <h4 style="margin:14px 0 6px">Service Job History</h4>
      ${!jobs.length ? emptyState("No service jobs recorded for this vehicle yet") : `
      <div class="table-wrap">
        <table class="tbl">
          <thead><tr><th>Job #</th><th>Check-in</th><th class="num">Odometer</th><th>Reported Issue</th><th class="num">Actual Total</th><th>Status</th></tr></thead>
          <tbody>
            ${jobs.map(j => `
              <tr>
                <td><strong>${esc(j.job_number)}</strong></td>
                <td class="muted">${fmtDateTime(j.checkin_at)}</td>
                <td class="num">${j.odometer != null ? Number(j.odometer).toLocaleString() + " km" : "—"}</td>
                <td>${esc(j.reported_issue || "—")}</td>
                <td class="num">${money(j.actual_total_paisa || 0)}</td>
                <td>${badge(j.status)}</td>
              </tr>`).join("")}
          </tbody>
        </table>
      </div>`}

      <h4 style="margin:16px 0 6px">Invoices Linked to Vehicle</h4>
      ${!invoices.length ? emptyState("No invoices linked to this vehicle yet") : `
      <div class="table-wrap">
        <table class="tbl">
          <thead><tr><th>Invoice #</th><th>Date</th><th class="num">Total</th><th class="num">Paid</th><th class="num">Balance</th><th>Status</th></tr></thead>
          <tbody>
            ${invoices.map(i => `
              <tr>
                <td><a href="#/invoices?id=${i.id}"><strong>${esc(i.invoice_number)}</strong></a></td>
                <td class="muted">${fmtDateTime(i.created_at)}</td>
                <td class="num">${money(i.total_paisa)}</td>
                <td class="num">${money(i.paid_paisa)}</td>
                <td class="num">${money(i.balance_paisa)}</td>
                <td>${badge(i.status)}</td>
              </tr>`).join("")}
          </tbody>
        </table>
      </div>`}
    `,
  });
}
