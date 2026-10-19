// Workshop Service Jobs — check-in, estimates, approvals, status workflow, labor, parts, final billing & printable job card.
import { api } from "../core/api.js";
import { appState, refreshHeaderContext } from "../core/app.js";
import { badge, confirmDialog, emptyState, esc, fmtDate, fmtDateTime, formData, money, openModal, printDocument, toast, toPaisa } from "../core/ui.js";
import { openQuickCustomerModal } from "./customers.js";
import { openQuickVehicleModal } from "./vehicles.js";

const STATUSES = [
  "received", "inspection", "awaiting_approval", "approved",
  "in_progress", "waiting_for_parts", "on_hold", "completed",
  "ready_for_delivery", "delivered", "cancelled",
];

const TRANSITIONS = {
  received: ["inspection", "cancelled"],
  inspection: ["awaiting_approval", "approved", "in_progress", "received", "cancelled"],
  awaiting_approval: ["approved", "rejected", "inspection", "cancelled"],
  approved: ["in_progress", "waiting_for_parts", "on_hold", "cancelled"],
  in_progress: ["waiting_for_parts", "on_hold", "completed", "cancelled"],
  waiting_for_parts: ["in_progress", "on_hold", "cancelled"],
  on_hold: ["in_progress", "waiting_for_parts", "cancelled"],
  completed: ["ready_for_delivery", "delivered", "in_progress"],
  ready_for_delivery: ["delivered", "in_progress"],
  delivered: [],
  cancelled: [],
};

function buildJobCardPrintHtml(job) {
  const biz = appState.business || {};
  const estTotal = (job.est_labor_paisa || 0) + (job.est_parts_paisa || 0);
  const actTotal = (job.actual_labor_paisa || 0) + (job.actual_parts_paisa || 0);
  return `
    <div>
      <div style="display:flex;justify-content:space-between;align-items:flex-start;border-bottom:2px solid #292824;padding-bottom:12px;margin-bottom:14px">
        <div>
          <h2 style="margin:0;font-size:18px">${esc(biz.business_name || "Auto Workshop")}</h2>
          <div style="font-size:12px;color:#706C64">${esc(biz.address || "")} ${biz.phone ? " · " + esc(biz.phone) : ""}</div>
        </div>
        <div style="text-align:right">
          <div style="font-size:16px;font-weight:700">SERVICE JOB CARD</div>
          <div style="font-size:13px;font-weight:600">${esc(job.job_number)}</div>
          <div style="font-size:11px;color:#706C64">Check-in: ${fmtDateTime(job.checkin_at)}</div>
        </div>
      </div>

      <table style="margin-bottom:14px">
        <tbody>
          <tr>
            <td style="width:50%;vertical-align:top">
              <strong>Customer Details</strong><br/>
              Name: ${esc(job.customer_name || "—")}<br/>
              Phone: ${esc(job.customer_phone || "—")}<br/>
              Address: ${esc(job.customer_address || "—")}
            </td>
            <td style="width:50%;vertical-align:top">
              <strong>Vehicle &amp; Assignment</strong><br/>
              Vehicle: ${esc(job.vehicle_label || job.registration_no || "—")}<br/>
              Odometer: ${job.odometer != null ? Number(job.odometer).toLocaleString() + " km" : "—"} · Fuel: ${esc(job.fuel_level || "—")}<br/>
              Mechanic: ${esc(job.mechanic_name || "Unassigned")} · Status: ${esc((job.status || "").replace(/_/g, " ").toUpperCase())}
            </td>
          </tr>
        </tbody>
      </table>

      <table style="margin-bottom:14px">
        <thead>
          <tr><th>Reported Issue / Customer Complaint</th><th>Inspection &amp; Diagnosis</th><th>Condition / Existing Damage</th></tr>
        </thead>
        <tbody>
          <tr>
            <td>${esc(job.reported_issue || job.complaint || "—")}</td>
            <td>${esc(job.inspection || "—")}</td>
            <td>${esc([job.vehicle_condition, job.existing_damage].filter(Boolean).join(" | ") || "—")}</td>
          </tr>
        </tbody>
      </table>

      <h3 style="font-size:13px;margin:12px 0 4px">Labor / Services Performed</h3>
      <table>
        <thead><tr><th>Description</th><th class="num">Qty</th><th class="num">Rate</th><th class="num">Discount</th><th class="num">Line Total</th></tr></thead>
        <tbody>
          ${(job.services || []).length === 0
            ? `<tr><td colspan="5" style="text-align:center;color:#706C64">No labor lines recorded</td></tr>`
            : job.services.map(s => `
              <tr>
                <td>${esc(s.description)}</td>
                <td class="num">${s.quantity}</td>
                <td class="num">${money(s.unit_charge_paisa)}</td>
                <td class="num">${money(s.discount_paisa)}</td>
                <td class="num">${money(s.line_total_paisa)}</td>
              </tr>`).join("")}
        </tbody>
      </table>

      <h3 style="font-size:13px;margin:12px 0 4px">Parts Issued</h3>
      <table>
        <thead><tr><th>Part</th><th>SKU</th><th class="num">Qty</th><th class="num">Unit Price</th><th class="num">Line Total</th></tr></thead>
        <tbody>
          ${(job.parts || []).length === 0
            ? `<tr><td colspan="5" style="text-align:center;color:#706C64">No parts issued</td></tr>`
            : job.parts.map(p => `
              <tr>
                <td>${esc(p.product_name || "")}</td>
                <td>${esc(p.sku || "—")}</td>
                <td class="num">${p.quantity}</td>
                <td class="num">${money(p.unit_price_paisa)}</td>
                <td class="num">${money(p.line_total_paisa)}</td>
              </tr>`).join("")}
        </tbody>
      </table>

      <div style="display:flex;justify-content:space-between;margin-top:16px;padding-top:10px;border-top:1px solid #D5C8B6;font-size:12.5px">
        <div>
          <div>Estimated Total: <strong>${money(estTotal)}</strong> (${esc((job.approval_status || "not_required").replace(/_/g, " "))})</div>
          <div>Warranty: <strong>${job.warranty_days || 0} day(s)</strong></div>
          ${job.customer_notes ? `<div>Notes: ${esc(job.customer_notes)}</div>` : ""}
        </div>
        <div style="text-align:right">
          <div>Labor Subtotal: ${money(job.actual_labor_paisa || 0)}</div>
          <div>Parts Subtotal: ${money(job.actual_parts_paisa || 0)}</div>
          <div style="font-size:15px;font-weight:700;margin-top:4px">Total Charges: ${money(actTotal)}</div>
        </div>
      </div>

      <div style="display:flex;justify-content:space-between;margin-top:36px;font-size:12px">
        <div style="border-top:1px solid #706C64;width:200px;padding-top:4px;text-align:center">Customer Signature</div>
        <div style="border-top:1px solid #706C64;width:200px;padding-top:4px;text-align:center">Workshop Supervisor</div>
      </div>
    </div>
  `;
}

export async function renderJobs(root, params = {}) {
  root.innerHTML = `
    <div class="toolbar">
      <input id="j-q" placeholder="Search job #, customer, plate, issue…" style="min-width:240px" />
      <select id="j-status">
        <option value="">All statuses</option>
        ${STATUSES.map(s => `<option value="${s}">${s.replace(/_/g, " ")}</option>`).join("")}
      </select>
      <button class="btn btn-ghost btn-sm" id="j-filter">Filter</button>
      <span class="spacer"></span>
      <button class="btn btn-primary" id="j-new">+ New Job Card</button>
    </div>
    <div class="card" id="j-list"></div>
  `;

  async function load() {
    const q = encodeURIComponent(root.querySelector("#j-q").value.trim());
    const st = root.querySelector("#j-status").value;
    const res = await api.get(`/api/jobs?q=${q}&status=${st}&page_size=100`);
    const list = root.querySelector("#j-list");
    if (!res.items.length) { list.innerHTML = emptyState("No service jobs match your filter"); return; }
    list.innerHTML = `
      <div class="table-wrap">
        <table class="tbl">
          <thead>
            <tr>
              <th>Job #</th><th>Customer</th><th>Vehicle</th><th>Reported Issue</th>
              <th>Mechanic</th><th>Estimate</th><th>Actual</th><th>Approval</th><th>Status</th><th></th>
            </tr>
          </thead>
          <tbody>
            ${res.items.map(j => `
              <tr>
                <td class="mono"><strong>${esc(j.job_number)}</strong><div class="muted" style="font-size:11px">${fmtDateTime(j.checkin_at)}</div></td>
                <td>${esc(j.customer_name || "—")}<div class="muted" style="font-size:11px">${esc(j.customer_phone || "")}</div></td>
                <td>${esc(j.vehicle_label || "—")}</td>
                <td>${esc(j.reported_issue || "—")}</td>
                <td>${esc(j.mechanic_name || "Unassigned")}</td>
                <td class="num">${money(j.est_total_paisa)}</td>
                <td class="num"><strong>${money(j.actual_total_paisa)}</strong></td>
                <td>${badge(j.approval_status)}</td>
                <td>${badge(j.status)}</td>
                <td class="right"><button class="btn btn-ghost btn-sm" data-open="${j.id}">Open</button></td>
              </tr>`).join("")}
          </tbody>
        </table>
      </div>`;
    list.querySelectorAll("[data-open]").forEach(b => b.onclick = () => openJobDetail(Number(b.dataset.open), load));
  }

  root.querySelector("#j-filter").onclick = load;
  root.querySelector("#j-q").onkeydown = (e) => { if (e.key === "Enter") load(); };
  root.querySelector("#j-status").onchange = load;
  root.querySelector("#j-new").onclick = () => openNewJob(load);

  await load();
  if (params.new) openNewJob(load);
  if (params.id) openJobDetail(Number(params.id), load);
}

async function openNewJob(onDone) {
  const [custRes, vehRes, mechs] = await Promise.all([
    api.get("/api/customers?page_size=200"),
    api.get("/api/vehicles?page_size=200"),
    api.get("/api/mechanics"),
  ]);
  let customers = custRes.items || (Array.isArray(custRes) ? custRes : []);
  let allVehicles = vehRes.items || (Array.isArray(vehRes) ? vehRes : []);

  const { close, root } = openModal({
    title: "New Service Job Card (Vehicle Check-In)",
    size: "lg",
    body: `
      <form id="nj-form">
        <div class="form-row">
          <label>
            <span class="flex-between">
              <span>Customer *</span>
              <button type="button" class="btn btn-ghost btn-sm" id="nj-add-cust" style="padding:1px 7px;font-size:11px">+ New Customer</button>
            </span>
            <select name="customer_id" id="nj-cust" required>
              <option value="">Select customer…</option>
              ${customers.map(c => `<option value="${c.id}">${esc(c.name)} (${esc(c.phone || c.code)})</option>`).join("")}
            </select>
          </label>
          <label>
            <span class="flex-between">
              <span>Vehicle *</span>
              <button type="button" class="btn btn-ghost btn-sm" id="nj-add-veh" style="padding:1px 7px;font-size:11px">+ New Vehicle</button>
            </span>
            <select name="vehicle_id" id="nj-veh" required>
              <option value="">Select customer first…</option>
            </select>
          </label>
          <label><span>Assigned Mechanic</span>
            <select name="mechanic_id">
              <option value="">Unassigned</option>
              ${(mechs || []).map(m => `<option value="${m.id}">${esc(m.name)} (${esc(m.skill || "")})</option>`).join("")}
            </select>
          </label>
        </div>
        <div class="form-row">
          <label><span>Odometer (km)</span><input name="odometer" type="number" min="0" /></label>
          <label><span>Fuel Level</span>
            <select name="fuel_level">
              <option value="">—</option><option>Empty</option><option>1/4</option><option>1/2</option><option>3/4</option><option>Full</option>
            </select>
          </label>
          <label><span>Priority</span>
            <select name="priority">
              <option value="normal">Normal</option><option value="low">Low</option>
              <option value="high">High</option><option value="urgent">Urgent</option>
            </select>
          </label>
        </div>
        <label><span>Customer Complaint / Reported Issue *</span><textarea name="reported_issue" required placeholder="Describe the issue reported by the customer…"></textarea></label>
        <div class="form-row">
          <label><span>Initial Inspection Notes</span><textarea name="inspection"></textarea></label>
          <label><span>Vehicle Condition &amp; Existing Damage</span><textarea name="existing_damage" placeholder="Scratches, dents, accessories…"></textarea></label>
        </div>
        <div class="form-row">
          <label><span>Estimated Labor (PKR)</span><input name="est_labor" type="number" step="0.01" min="0" value="0" /></label>
          <label><span>Estimated Parts (PKR)</span><input name="est_parts" type="number" step="0.01" min="0" value="0" /></label>
          <label><span>Expected Completion Date</span><input name="est_completion_date" type="date" /></label>
        </div>
        <div class="modal-foot">
          <button type="button" class="btn btn-ghost" data-close>Cancel</button>
          <button type="submit" class="btn btn-primary" id="nj-submit">Create Job Card</button>
        </div>
      </form>`,
  });

  const custSel = root.querySelector("#nj-cust");
  const vehSel = root.querySelector("#nj-veh");

  function refreshVehicleSelect(cid, selectedVid = null) {
    const vs = allVehicles.filter(v => Number(v.customer_id) === Number(cid));
    vehSel.innerHTML = vs.length
      ? vs.map(v => `<option value="${v.id}" ${Number(selectedVid) === v.id ? "selected" : ""}>${esc(v.registration_no || "No plate")} — ${esc([v.make, v.model].filter(Boolean).join(" "))}</option>`).join("")
      : `<option value="">No vehicles registered for this customer — click "+ New Vehicle"</option>`;
  }

  custSel.onchange = () => refreshVehicleSelect(custSel.value);

  root.querySelector("#nj-add-cust").onclick = () => {
    openQuickCustomerModal((createdCust) => {
      customers.unshift(createdCust);
      custSel.innerHTML = `<option value="">Select customer…</option>` +
        customers.map(c => `<option value="${c.id}" ${c.id === createdCust.id ? "selected" : ""}>${esc(c.name)} (${esc(c.phone || c.code)})</option>`).join("");
      custSel.value = String(createdCust.id);
      refreshVehicleSelect(createdCust.id);
    });
  };

  root.querySelector("#nj-add-veh").onclick = () => {
    openQuickVehicleModal(customers, custSel.value, (createdVeh) => {
      allVehicles.unshift(createdVeh);
      if (!custSel.value) custSel.value = String(createdVeh.customer_id);
      refreshVehicleSelect(custSel.value, createdVeh.id);
    });
  };

  root.querySelector("#nj-form").onsubmit = async (e) => {
    e.preventDefault();
    const btn = root.querySelector("#nj-submit");
    btn.disabled = true;
    const fd = formData(e.target);
    try {
      const created = await api.post("/api/jobs", {
        customer_id: Number(fd.customer_id),
        vehicle_id: Number(fd.vehicle_id),
        mechanic_id: fd.mechanic_id ? Number(fd.mechanic_id) : null,
        odometer: fd.odometer ? Number(fd.odometer) : null,
        fuel_level: fd.fuel_level || null,
        priority: fd.priority || "normal",
        reported_issue: fd.reported_issue,
        complaint: fd.reported_issue,
        inspection: fd.inspection || null,
        existing_damage: fd.existing_damage || null,
        est_labor_paisa: toPaisa(fd.est_labor),
        est_parts_paisa: toPaisa(fd.est_parts),
        est_completion_date: fd.est_completion_date || null,
      });
      if (created.odometer_warning) toast(created.odometer_warning, "warn", 6000);
      toast(`Job ${created.job_number} created`);
      close();
      onDone && onDone();
      openJobDetail(created.id, onDone);
    } catch (err) {
      toast(err.message, "err");
      btn.disabled = false;
    }
  };
}

async function openJobDetail(jid, onListRefresh) {
  const [job, catalogSvcs, mechs] = await Promise.all([
    api.get(`/api/jobs/${jid}`),
    api.get("/api/services"),
    api.get("/api/mechanics"),
  ]);
  const allowedNext = TRANSITIONS[job.status] || [];
  const { close, root } = openModal({
    title: `${job.job_number} — ${job.vehicle_label || ""}`,
    size: "lg",
    body: `
      <div class="flex-between mb-2">
        <div>
          <strong>${esc(job.customer_name)}</strong> (${esc(job.customer_phone || "no phone")}) ·
          Plate <span class="mono">${esc(job.registration_no || "—")}</span> ·
          Odometer ${job.odometer != null ? job.odometer + " km" : "—"} ·
          Mechanic: <strong>${esc(job.mechanic_name || "Unassigned")}</strong>
        </div>
        <div class="flex">
          <button type="button" class="btn btn-ghost btn-sm" id="jd-print">Print Job Card</button>
          ${badge(job.approval_status)} ${badge(job.status)}
        </div>
      </div>

      <div class="card" style="padding:12px;margin-bottom:12px">
        <div class="form-row">
          <div><span class="muted">Reported Issue:</span><div>${esc(job.reported_issue || "—")}</div></div>
          <div><span class="muted">Inspection Notes:</span><div>${esc(job.inspection || "—")}</div></div>
          <div><span class="muted">Existing Damage:</span><div>${esc(job.existing_damage || "—")}</div></div>
        </div>
        <div style="margin-top:10px;display:flex;gap:8px;flex-wrap:wrap">
          <button type="button" class="btn btn-ghost btn-sm" id="jd-edit-notes">Edit Inspection / Notes / Mechanic</button>
        </div>
      </div>

      <!-- Workflow & approval controls -->
      <div class="toolbar">
        <span class="muted">Transition status:</span>
        ${allowedNext.length === 0 ? `<span class="muted">Terminal status</span>` : allowedNext.map(s => `
          <button class="btn btn-ghost btn-sm" data-next="${s}">Move to ${s.replace(/_/g, " ")}</button>`).join("")}
        <span class="spacer"></span>
        <select id="jd-approval">
          ${["not_required", "pending", "approved", "rejected"].map(a => `<option value="${a}" ${job.approval_status === a ? "selected" : ""}>Approval: ${a.replace(/_/g, " ")}</option>`).join("")}
        </select>
        ${!job.invoice_id && (job.services.length + job.parts.length > 0)
          ? `<button class="btn btn-primary btn-sm" id="jd-bill">Generate Final Bill</button>`
          : job.invoice_id ? `<a class="btn btn-success btn-sm" href="#/invoices?id=${job.invoice_id}" data-close>View Invoice</a>` : ""}
      </div>

      <div class="grid-2">
        <!-- Services / Labor -->
        <div class="card">
          <div class="card-head">
            <h4 class="card-title">Labor / Services (${money(job.actual_labor_paisa)})</h4>
          </div>
          ${job.services.length === 0 ? emptyState("No labor lines added") : `
          <div class="table-wrap">
            <table class="tbl">
              <thead><tr><th>Service</th><th class="num">Qty</th><th class="num">Charge</th><th class="num">Total</th><th></th></tr></thead>
              <tbody>
                ${job.services.map(s => `
                  <tr>
                    <td>${esc(s.description)}</td>
                    <td class="num">${s.quantity}</td>
                    <td class="num">${money(s.unit_charge_paisa)}</td>
                    <td class="num">${money(s.line_total_paisa)}</td>
                    <td class="right"><button class="btn btn-ghost btn-sm" data-delsvc="${s.id}">Remove</button></td>
                  </tr>`).join("")}
              </tbody>
            </table>
          </div>`}
          <form id="add-svc-form" class="mt-2">
            <div class="form-row">
              <select name="service_id" id="svc-pick">
                <option value="">Custom service…</option>
                ${catalogSvcs.map(s => `<option value="${s.id}" data-charge="${s.default_charge_paisa}" data-name="${esc(s.name)}">${esc(s.name)} (${money(s.default_charge_paisa)})</option>`).join("")}
              </select>
              <input name="description" id="svc-desc" placeholder="Description *" required />
              <input name="charge" id="svc-charge" type="number" step="0.01" min="0" placeholder="Charge (PKR)" required />
              <button class="btn btn-primary btn-sm" type="submit">+ Add Labor</button>
            </div>
          </form>
        </div>

        <!-- Parts consumed -->
        <div class="card">
          <div class="card-head">
            <h4 class="card-title">Parts Consumed (${money(job.actual_parts_paisa)})</h4>
          </div>
          ${job.parts.length === 0 ? emptyState("No parts consumed") : `
          <div class="table-wrap">
            <table class="tbl">
              <thead><tr><th>Part</th><th class="num">Qty</th><th class="num">Price</th><th class="num">Total</th><th></th></tr></thead>
              <tbody>
                ${job.parts.map(p => `
                  <tr>
                    <td>${esc(p.product_name)} <span class="mono muted">${esc(p.sku || "")}</span></td>
                    <td class="num">${p.quantity}</td>
                    <td class="num">${money(p.unit_price_paisa)}</td>
                    <td class="num">${money(p.line_total_paisa)}</td>
                    <td class="right"><button class="btn btn-ghost btn-sm" data-delpart="${p.id}">Restore</button></td>
                  </tr>`).join("")}
              </tbody>
            </table>
          </div>`}
          <form id="add-part-form" class="mt-2">
            <div class="form-row">
              <input id="part-search" placeholder="Search stock part…" />
              <select name="product_id" id="part-pick" required><option value="">Search above…</option></select>
              <input name="quantity" type="number" min="1" value="1" style="max-width:80px" required />
              <button class="btn btn-primary btn-sm" type="submit">+ Issue Part</button>
            </div>
          </form>
        </div>
      </div>

      <div class="card mt-3">
        <h4 class="card-title" style="margin-bottom:8px">Status Timeline</h4>
        <div class="muted" style="font-size:12px">
          ${job.history.map(h => `${fmtDateTime(h.created_at)}: <strong>${esc(h.from_status || "start")} to ${esc(h.to_status)}</strong> ${h.notes ? `(${esc(h.notes)})` : ""}`).join(" · ")}
        </div>
      </div>
    `,
  });

  const reload = async () => { close(); onListRefresh && onListRefresh(); await openJobDetail(jid, onListRefresh); };

  root.querySelector("#jd-print").onclick = () => {
    printDocument(buildJobCardPrintHtml(job), false);
  };

  root.querySelector("#jd-edit-notes").onclick = () => {
    const m = openModal({
      title: `Update ${job.job_number}`,
      body: `
        <form id="je-form">
          <div class="form-row">
            <label><span>Assigned Mechanic</span>
              <select name="mechanic_id">
                <option value="">Unassigned</option>
                ${(mechs || []).map(x => `<option value="${x.id}" ${job.mechanic_id === x.id ? "selected" : ""}>${esc(x.name)}</option>`).join("")}
              </select>
            </label>
            <label><span>Warranty Days</span><input name="warranty_days" type="number" min="0" value="${job.warranty_days || 0}" /></label>
          </div>
          <label><span>Reported Issue / Complaint</span><textarea name="reported_issue">${esc(job.reported_issue || "")}</textarea></label>
          <label><span>Inspection &amp; Work Performed Notes</span><textarea name="inspection">${esc(job.inspection || "")}</textarea></label>
          <label><span>Vehicle Condition / Existing Damage</span><textarea name="existing_damage">${esc(job.existing_damage || "")}</textarea></label>
          <label><span>Customer Notes</span><textarea name="customer_notes">${esc(job.customer_notes || "")}</textarea></label>
          <div class="modal-foot">
            <button type="button" class="btn btn-ghost" data-close>Cancel</button>
            <button type="submit" class="btn btn-primary">Save Notes</button>
          </div>
        </form>`,
    });
    m.root.querySelector("#je-form").onsubmit = async (e) => {
      e.preventDefault();
      const fd = formData(e.target);
      try {
        await api.put(`/api/jobs/${jid}`, {
          mechanic_id: fd.mechanic_id ? Number(fd.mechanic_id) : null,
          warranty_days: fd.warranty_days ? Number(fd.warranty_days) : 0,
          reported_issue: fd.reported_issue || null,
          inspection: fd.inspection || null,
          existing_damage: fd.existing_damage || null,
          customer_notes: fd.customer_notes || null,
        });
        toast("Job updated");
        m.close();
        reload();
      } catch (err) { toast(err.message, "err"); }
    };
  };

  root.querySelectorAll("[data-next]").forEach(b => b.onclick = async () => {
    const next = b.dataset.next;
    try {
      await api.post(`/api/jobs/${jid}/status`, { status: next });
      toast(`Moved to ${next.replace(/_/g, " ")}`);
      reload();
    } catch (e) { toast(e.message, "err"); }
  });

  root.querySelector("#jd-approval").onchange = async (e) => {
    try {
      await api.post(`/api/jobs/${jid}/approval`, { approval_status: e.target.value });
      toast("Approval updated");
      reload();
    } catch (err) { toast(err.message, "err"); }
  };

  const svcPick = root.querySelector("#svc-pick");
  svcPick.onchange = () => {
    const opt = svcPick.selectedOptions[0];
    if (opt && opt.value) {
      root.querySelector("#svc-desc").value = opt.dataset.name;
      root.querySelector("#svc-charge").value = (Number(opt.dataset.charge) / 100).toFixed(2);
    }
  };
  root.querySelector("#add-svc-form").onsubmit = async (e) => {
    e.preventDefault();
    const fd = formData(e.target);
    try {
      await api.post(`/api/jobs/${jid}/services`, {
        service_id: fd.service_id ? Number(fd.service_id) : null,
        description: fd.description,
        quantity: 1,
        unit_charge_paisa: toPaisa(fd.charge),
      });
      toast("Labor added");
      reload();
    } catch (err) { toast(err.message, "err"); }
  };
  root.querySelectorAll("[data-delsvc]").forEach(b => b.onclick = async () => {
    await api.del(`/api/jobs/services/${b.dataset.delsvc}`);
    reload();
  });

  const pSearch = root.querySelector("#part-search");
  const pPick = root.querySelector("#part-pick");
  const loadParts = async (q = "") => {
    const res = await api.get(`/api/products?q=${encodeURIComponent(q)}&include_services=false&page_size=50`);
    pPick.innerHTML = (res.items || []).map(p =>
      `<option value="${p.id}" ${p.quantity_on_hand <= 0 ? "disabled" : ""}>${esc(p.name)} — ${money(p.selling_price_paisa)} (${p.quantity_on_hand} in stock)</option>`
    ).join("") || `<option value="">No stock parts found</option>`;
  };
  loadParts();
  pSearch.oninput = () => loadParts(pSearch.value);

  root.querySelector("#add-part-form").onsubmit = async (e) => {
    e.preventDefault();
    const fd = formData(e.target);
    try {
      await api.post(`/api/jobs/${jid}/parts`, {
        product_id: Number(fd.product_id),
        quantity: Number(fd.quantity),
      });
      toast("Part issued from stock");
      reload();
    } catch (err) { toast(err.message, "err"); }
  };
  root.querySelectorAll("[data-delpart]").forEach(b => b.onclick = async () => {
    await api.del(`/api/jobs/parts/${b.dataset.delpart}`);
    toast("Part returned to stock");
    reload();
  });

  const billBtn = root.querySelector("#jd-bill");
  if (billBtn) {
    billBtn.onclick = () => {
      const totalPaisa = job.actual_total_paisa || 0;
      const m = openModal({
        title: `Generate Final Invoice — ${job.job_number}`,
        body: `
          <form id="jbill-form">
            <div class="kpi-grid">
              <div class="kpi"><div class="k-label">Labor Subtotal</div><div class="k-value" style="font-size:16px">${money(job.actual_labor_paisa)}</div></div>
              <div class="kpi"><div class="k-label">Parts Subtotal</div><div class="k-value" style="font-size:16px">${money(job.actual_parts_paisa)}</div></div>
              <div class="kpi success"><div class="k-label">Job Total</div><div class="k-value" style="font-size:16px">${money(totalPaisa)}</div></div>
            </div>
            <div class="form-row">
              <label><span>Invoice Discount (PKR)</span><input name="discount" id="jb-disc" type="number" step="0.01" min="0" value="0" /></label>
              <label><span>Payment Method</span>
                <select name="method" id="jb-method">
                  <option value="cash">Cash</option>
                  <option value="card">Card</option>
                  <option value="bank_transfer">Bank Transfer</option>
                  <option value="jazzcash">JazzCash</option>
                  <option value="easypaisa">Easypaisa</option>
                </select>
              </label>
              <label><span>Amount Received Now (PKR)</span>
                <input name="paid_amount" id="jb-paid" type="number" step="0.01" min="0" value="${(totalPaisa / 100).toFixed(2)}" />
              </label>
            </div>
            <label style="display:flex;align-items:center;gap:8px">
              <input type="checkbox" name="is_credit" id="jb-credit" style="width:auto" />
              <span style="margin:0">Allow remaining unpaid balance on customer credit account</span>
            </label>
            <div class="modal-foot">
              <button type="button" class="btn btn-ghost" data-close>Cancel</button>
              <button type="submit" class="btn btn-primary">Issue Invoice</button>
            </div>
          </form>`,
      });
      const discInput = m.root.querySelector("#jb-disc");
      const paidInput = m.root.querySelector("#jb-paid");
      discInput.oninput = () => {
        const net = Math.max(0, totalPaisa - toPaisa(discInput.value || 0));
        paidInput.value = (net / 100).toFixed(2);
      };
      m.root.querySelector("#jbill-form").onsubmit = async (e) => {
        e.preventDefault();
        const fd = formData(e.target);
        try {
          const discPaisa = toPaisa(fd.discount || 0);
          const paidPaisa = toPaisa(fd.paid_amount || 0);
          const payments = paidPaisa > 0 ? [{ amount_paisa: paidPaisa, method: fd.method || "cash" }] : [];
          const inv = await api.post(`/api/jobs/${jid}/invoice`, {
            invoice_discount_paisa: discPaisa,
            payments,
            is_credit: !!fd.is_credit || paidPaisa < Math.max(0, totalPaisa - discPaisa),
          });
          toast(`Invoice ${inv.invoice_number} created`);
          m.close();
          close();
          refreshHeaderContext();
          location.hash = `#/invoices?id=${inv.id}`;
        } catch (err) { toast(err.message, "err"); }
      };
    };
  }
}
