// Customers — list, search, create/edit, statement, advance & credit repayment.
import { api } from "../core/api.js";
import { badge, confirmDialog, emptyState, esc, fmtDateTime, formData, money, openModal, toast, toPaisa } from "../core/ui.js";

export function openQuickCustomerModal(onCreated) {
  const { close, root } = openModal({
    title: "New Customer",
    body: `
      <form id="qc-form">
        <div class="form-row">
          <label><span>Full Name *</span><input name="name" required placeholder="e.g. Muhammad Ali" /></label>
          <label><span>Phone Number</span><input name="phone" placeholder="0300-1234567" /></label>
        </div>
        <div class="form-row">
          <label><span>Alternate Phone</span><input name="alt_phone" placeholder="Optional" /></label>
          <label><span>CNIC</span><input name="cnic" placeholder="42101-1234567-1" /></label>
        </div>
        <label><span>Address</span><input name="address" placeholder="Street / Area / City" /></label>
        <label><span>Notes</span><textarea name="notes"></textarea></label>
        <div class="modal-foot">
          <button type="button" class="btn btn-ghost" data-close>Cancel</button>
          <button type="submit" class="btn btn-primary" id="qc-submit">Save Customer</button>
        </div>
      </form>`,
  });
  const form = root.querySelector("#qc-form");
  form.onsubmit = async (e) => {
    e.preventDefault();
    const btn = root.querySelector("#qc-submit");
    btn.disabled = true;
    try {
      const fd = formData(form);
      const payload = {
        name: (fd.name || "").trim(),
        phone: fd.phone || null,
        alt_phone: fd.alt_phone || null,
        cnic: fd.cnic || null,
        address: fd.address || null,
        notes: fd.notes || null,
      };
      const created = await api.post("/api/customers", payload);
      toast("Customer saved");
      close();
      if (onCreated) await onCreated(created);
    } catch (err) {
      toast(err.message, "err");
      btn.disabled = false;
    }
  };
}

export async function renderCustomers(root, params = {}) {
  root.innerHTML = `
    <div class="toolbar">
      <input id="c-q" placeholder="Search name, phone, code…" style="min-width:260px" />
      <button class="btn btn-ghost btn-sm" id="c-search">Search</button>
      <span class="spacer"></span>
      <button class="btn btn-primary" id="c-new">+ New Customer</button>
    </div>
    <div class="card" id="c-list"></div>
  `;

  const qEl = root.querySelector("#c-q");

  async function load() {
    const q = encodeURIComponent(qEl.value.trim());
    const res = await api.get(`/api/customers?q=${q}&page_size=100`);
    const list = root.querySelector("#c-list");
    if (!res.items.length) {
      list.innerHTML = emptyState("No customers found");
      return;
    }
    list.innerHTML = `
      <div class="table-wrap">
        <table class="tbl">
          <thead>
            <tr>
              <th>Code</th><th>Name</th><th>Phone</th><th>Address</th>
              <th class="num">Vehicles</th><th class="num">Outstanding</th><th class="num">Advance</th><th></th>
            </tr>
          </thead>
          <tbody>
            ${res.items.map(c => `
              <tr>
                <td class="mono muted">${esc(c.code)}</td>
                <td><strong>${esc(c.name)}</strong></td>
                <td>${esc(c.phone || "—")}${c.alt_phone ? `<div class="muted" style="font-size:11px">${esc(c.alt_phone)}</div>` : ""}</td>
                <td class="muted">${esc(c.address || "—")}</td>
                <td class="num">${c.vehicle_count}</td>
                <td class="num">${c.balance_paisa > 0 ? `<span class="badge credit">${money(c.balance_paisa)}</span>` : money(0)}</td>
                <td class="num">${c.advance_paisa > 0 ? `<span class="badge paid">${money(c.advance_paisa)}</span>` : money(0)}</td>
                <td class="right">
                  <button class="btn btn-ghost btn-sm" data-view="${c.id}">Statement</button>
                  <button class="btn btn-ghost btn-sm" data-edit="${c.id}">Edit</button>
                  <button class="btn btn-ghost btn-sm" data-del="${c.id}">Delete</button>
                </td>
              </tr>`).join("")}
          </tbody>
        </table>
      </div>`;

    list.querySelectorAll("[data-edit]").forEach(b => b.onclick = () => {
      const c = res.items.find(x => x.id === Number(b.dataset.edit));
      openEditor(c, load);
    });
    list.querySelectorAll("[data-view]").forEach(b => b.onclick = () => openProfile(Number(b.dataset.view), load));
    list.querySelectorAll("[data-del]").forEach(b => b.onclick = async () => {
      if (!await confirmDialog("Delete this customer? Customers with invoices or vehicles cannot be deleted.")) return;
      try {
        await api.del(`/api/customers/${b.dataset.del}`);
        toast("Customer deleted");
        load();
      } catch (e) { toast(e.message, "err"); }
    });
  }

  root.querySelector("#c-search").onclick = load;
  qEl.onkeydown = (e) => { if (e.key === "Enter") load(); };
  root.querySelector("#c-new").onclick = () => openEditor(null, load);

  await load();
  if (params.id) openProfile(Number(params.id), load);
}

function openEditor(cust, onDone) {
  const isNew = !cust;
  const { close, root } = openModal({
    title: isNew ? "New Customer" : `Edit ${cust.name}`,
    body: `
      <form id="c-form">
        <div class="form-row">
          <label><span>Full Name *</span><input name="name" required value="${esc(cust?.name || "")}" /></label>
          <label><span>Phone</span><input name="phone" value="${esc(cust?.phone || "")}" placeholder="0300-1234567" /></label>
        </div>
        <div class="form-row">
          <label><span>Alternate Phone</span><input name="alt_phone" value="${esc(cust?.alt_phone || "")}" /></label>
          <label><span>CNIC</span><input name="cnic" value="${esc(cust?.cnic || "")}" placeholder="42101-1234567-1" /></label>
        </div>
        <label><span>Address</span><input name="address" value="${esc(cust?.address || "")}" /></label>
        <label><span>Notes</span><textarea name="notes">${esc(cust?.notes || "")}</textarea></label>
        <div class="modal-foot">
          <button type="button" class="btn btn-ghost" data-close>Cancel</button>
          <button type="submit" class="btn btn-primary" id="c-save-btn">${isNew ? "Create Customer" : "Save Changes"}</button>
        </div>
      </form>`,
  });
  const form = root.querySelector("#c-form");
  form.onsubmit = async (e) => {
    e.preventDefault();
    const saveBtn = root.querySelector("#c-save-btn");
    saveBtn.disabled = true;
    try {
      const fd = formData(form);
      const payload = {
        name: (fd.name || "").trim(),
        phone: fd.phone || null,
        alt_phone: fd.alt_phone || null,
        cnic: fd.cnic || null,
        address: fd.address || null,
        notes: fd.notes || null,
      };
      if (isNew) await api.post("/api/customers", payload);
      else await api.put(`/api/customers/${cust.id}`, payload);
      toast(isNew ? "Customer created" : "Customer updated");
      close();
      onDone && onDone();
    } catch (err) {
      toast(err.message, "err");
      saveBtn.disabled = false;
    }
  };
}

async function openProfile(cid, onDone) {
  const [c, hist, stmt] = await Promise.all([
    api.get(`/api/customers/${cid}`),
    api.get(`/api/customers/${cid}/history`),
    api.get(`/api/reports/customer-statement/${cid}`).catch(() => ({ entries: [] })),
  ]);
  const { close, root } = openModal({
    title: `${c.name} (${c.code})`,
    size: "lg",
    body: `
      <div class="kpi-grid">
        <div class="kpi"><div class="k-label">Phone</div><div class="k-value" style="font-size:16px">${esc(c.phone || "—")}</div><div class="k-sub">${esc(c.address || "")}</div></div>
        <div class="kpi ${c.balance_paisa > 0 ? "warn" : ""}"><div class="k-label">Outstanding Credit</div><div class="k-value">${money(c.balance_paisa)}</div></div>
        <div class="kpi ${c.advance_paisa > 0 ? "success" : ""}"><div class="k-label">Customer Advance</div><div class="k-value">${money(c.advance_paisa)}</div></div>
      </div>
      <div class="toolbar">
        <button class="btn btn-primary btn-sm" id="cp-repay">Record Credit Repayment</button>
        <button class="btn btn-ghost btn-sm" id="cp-adv">Record Customer Advance</button>
        <a class="btn btn-ghost btn-sm" href="#/vehicles?customer_id=${c.id}">Vehicles (${hist.vehicles.length})</a>
      </div>
      <h4 style="margin:14px 0 6px">Account Statement</h4>
      ${stmt.entries.length === 0 ? emptyState("No transactions yet") : `
      <div class="table-wrap">
        <table class="tbl">
          <thead><tr><th>Date</th><th>Type</th><th>Reference</th><th class="num">Charge</th><th class="num">Payment</th><th>Notes</th></tr></thead>
          <tbody>
            ${stmt.entries.map(r => `
              <tr>
                <td class="muted">${fmtDateTime(r.date)}</td>
                <td>${badge(r.type)}</td>
                <td class="mono">${esc(r.ref || "")}</td>
                <td class="num">${r.charge_paisa ? money(r.charge_paisa) : "—"}</td>
                <td class="num">${r.payment_paisa ? money(r.payment_paisa) : "—"}</td>
                <td class="muted">${esc(r.note || "")}</td>
              </tr>`).join("")}
          </tbody>
        </table>
      </div>`}
    `,
  });

  const payDialog = (kind) => {
    const m = openModal({
      title: kind === "repayment" ? `Credit Repayment — ${c.name}` : `Customer Advance — ${c.name}`,
      body: `
        <form id="pay-f">
          <div class="form-row">
            <label><span>Amount (PKR) *</span><input name="amount" type="number" step="0.01" min="1" required value="${kind === "repayment" && c.balance_paisa > 0 ? (c.balance_paisa / 100).toFixed(2) : ""}" /></label>
            <label><span>Method</span>
              <select name="method">
                <option value="cash">Cash</option><option value="card">Card</option>
                <option value="bank_transfer">Bank Transfer</option>
                <option value="jazzcash">JazzCash</option><option value="easypaisa">Easypaisa</option>
              </select>
            </label>
          </div>
          <label><span>Reference</span><input name="reference" /></label>
          <label><span>Notes</span><input name="notes" /></label>
          <div class="modal-foot">
            <button type="button" class="btn btn-ghost" data-close>Cancel</button>
            <button type="submit" class="btn btn-primary">Save Payment</button>
          </div>
        </form>`,
    });
    m.root.querySelector("#pay-f").onsubmit = async (e) => {
      e.preventDefault();
      const fd = formData(e.target);
      try {
        const endpoint = kind === "repayment" ? "/api/invoices/repayments" : "/api/invoices/advances";
        await api.post(endpoint, {
          customer_id: c.id,
          amount_paisa: toPaisa(fd.amount),
          method: fd.method,
          reference: fd.reference || null,
          notes: fd.notes || null,
        });
        toast("Payment recorded");
        m.close();
        close();
        onDone && onDone();
        openProfile(c.id, onDone);
      } catch (err) { toast(err.message, "err"); }
    };
  };
  root.querySelector("#cp-repay").onclick = () => payDialog("repayment");
  root.querySelector("#cp-adv").onclick = () => payDialog("advance");
}
