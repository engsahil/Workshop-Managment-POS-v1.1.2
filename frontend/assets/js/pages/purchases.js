// Purchases & Suppliers — PO creation, goods receiving, supplier payments & purchase returns.
import { api } from "../core/api.js";
import { badge, emptyState, esc, fmtDateTime, formData, money, openModal, toast, toPaisa } from "../core/ui.js";

export async function renderPurchases(root) {
  root.innerHTML = `
    <div class="tabs">
      <div class="tab active" data-t="pos">Purchase Orders</div>
      <div class="tab" data-t="sups">Suppliers &amp; Balances</div>
      <div class="tab" data-t="rets">Purchase Returns</div>
    </div>
    <div id="pur-body"></div>
  `;
  const body = root.querySelector("#pur-body");
  root.querySelectorAll(".tab").forEach(t => {
    t.onclick = () => {
      root.querySelectorAll(".tab").forEach(x => x.classList.remove("active"));
      t.classList.add("active");
      if (t.dataset.t === "pos") renderPOs(body);
      else if (t.dataset.t === "sups") renderSuppliers(body);
      else renderPurchaseReturns(body);
    };
  });
  await renderPOs(body);
}

async function renderPOs(box) {
  const res = await api.get("/api/purchases?page_size=100");
  box.innerHTML = `
    <div class="toolbar">
      <span class="muted">Stock increases when goods are received against a Purchase Order.</span>
      <span class="spacer"></span>
      <button class="btn btn-primary" id="po-new">+ New Purchase Order</button>
    </div>
    <div class="card">
      ${!res.items.length ? emptyState("No purchase orders yet") : `
      <div class="table-wrap">
        <table class="tbl">
          <thead><tr><th>PO #</th><th>Supplier</th><th>Date</th><th class="num">Total</th><th class="num">Paid</th><th class="num">Balance</th><th>Status</th><th></th></tr></thead>
          <tbody>
            ${res.items.map(p => `
              <tr>
                <td class="mono"><strong>${esc(p.po_number)}</strong></td>
                <td>${esc(p.supplier_name || "")}</td>
                <td class="muted">${fmtDateTime(p.order_date)}</td>
                <td class="num">${money(p.total_paisa)}</td>
                <td class="num">${money(p.paid_paisa)}</td>
                <td class="num">${money(p.balance_paisa)}</td>
                <td>${badge(p.status)}</td>
                <td class="right"><button class="btn btn-ghost btn-sm" data-open="${p.id}">Open</button></td>
              </tr>`).join("")}
          </tbody>
        </table>
      </div>`}
    </div>`;
  box.querySelector("#po-new").onclick = () => openNewPO(() => renderPOs(box));
  box.querySelectorAll("[data-open]").forEach(b => b.onclick = () => openPODetail(Number(b.dataset.open), () => renderPOs(box)));
}

async function openNewPO(onDone) {
  const [sups, prods] = await Promise.all([
    api.get("/api/suppliers"),
    api.get("/api/products?include_services=false&page_size=200"),
  ]);
  if (!sups.length) { toast("Create a supplier first in the Suppliers tab", "warn"); return; }
  const products = prods.items || [];
  if (!products.length) { toast("Create at least one product first", "warn"); return; }

  const lines = [{ product_id: products[0].id, quantity: 1, unit_cost: (products[0].purchase_cost_paisa / 100).toFixed(2) }];
  const m = openModal({
    title: "New Purchase Order",
    size: "lg",
    body: `
      <form id="po-form">
        <div class="form-row">
          <label><span>Supplier *</span>
            <select name="supplier_id" required>${sups.map(s => `<option value="${s.id}">${esc(s.name)}</option>`).join("")}</select>
          </label>
          <label><span>PO Discount (PKR)</span><input name="discount" type="number" step="0.01" min="0" value="0" /></label>
          <label><span>Initial Payment (PKR)</span><input name="paid" type="number" step="0.01" min="0" value="0" /></label>
        </div>
        <div id="po-lines"></div>
        <button type="button" class="btn btn-ghost btn-sm mt-2" id="po-add-line">+ Add Line</button>
        <label class="mt-2"><span>Notes</span><input name="notes" /></label>
        <div class="modal-foot">
          <button type="button" class="btn btn-ghost" data-close>Cancel</button>
          <button type="submit" class="btn btn-primary">Create Purchase Order</button>
        </div>
      </form>`,
  });

  function drawLines() {
    const el = m.root.querySelector("#po-lines");
    el.innerHTML = lines.map((l, i) => `
      <div class="form-row">
        <select data-lp="${i}">${products.map(p => `<option value="${p.id}" ${p.id === l.product_id ? "selected" : ""}>${esc(p.name)} (${esc(p.sku || "")})</option>`).join("")}</select>
        <input data-lq="${i}" type="number" min="1" value="${l.quantity}" placeholder="Qty" />
        <input data-lc="${i}" type="number" step="0.01" min="0" value="${l.unit_cost}" placeholder="Unit cost (PKR)" />
      </div>`).join("");
    el.querySelectorAll("[data-lp]").forEach(s => s.onchange = () => {
      const idx = Number(s.dataset.lp);
      lines[idx].product_id = Number(s.value);
      const pr = products.find(x => x.id === lines[idx].product_id);
      if (pr) { lines[idx].unit_cost = (pr.purchase_cost_paisa / 100).toFixed(2); drawLines(); }
    });
    el.querySelectorAll("[data-lq]").forEach(inp => inp.oninput = () => { lines[Number(inp.dataset.lq)].quantity = Number(inp.value) || 1; });
    el.querySelectorAll("[data-lc]").forEach(inp => inp.oninput = () => { lines[Number(inp.dataset.lc)].unit_cost = inp.value; });
  }
  drawLines();
  m.root.querySelector("#po-add-line").onclick = () => {
    lines.push({ product_id: products[0].id, quantity: 1, unit_cost: (products[0].purchase_cost_paisa / 100).toFixed(2) });
    drawLines();
  };

  m.root.querySelector("#po-form").onsubmit = async (e) => {
    e.preventDefault();
    const fd = formData(e.target);
    try {
      await api.post("/api/purchases", {
        supplier_id: Number(fd.supplier_id),
        discount_paisa: toPaisa(fd.discount),
        paid_paisa: toPaisa(fd.paid),
        payment_method: "cash",
        notes: fd.notes || null,
        items: lines.map(l => ({ product_id: l.product_id, quantity: l.quantity, unit_cost_paisa: toPaisa(l.unit_cost) })),
      });
      toast("Purchase order created");
      m.close(); onDone();
    } catch (err) { toast(err.message, "err"); }
  };
}

async function openPODetail(pid, onDone) {
  const po = await api.get(`/api/purchases/${pid}`);
  const m = openModal({
    title: `${po.po_number} — ${po.supplier_name}`,
    size: "lg",
    body: `
      <div class="flex-between mb-2">
        <div>Total: <strong>${money(po.total_paisa)}</strong> · Paid: ${money(po.paid_paisa)} · Balance: <strong>${money(po.balance_paisa)}</strong></div>
        <div>${badge(po.status)}</div>
      </div>
      <div class="table-wrap">
        <table class="tbl">
          <thead><tr><th>Part</th><th class="num">Ordered</th><th class="num">Received</th><th class="num">Unit Cost</th><th class="num">Line Total</th></tr></thead>
          <tbody>
            ${po.items.map(i => `
              <tr>
                <td>${esc(i.product_name)}</td>
                <td class="num">${i.quantity}</td>
                <td class="num">${i.received_quantity}</td>
                <td class="num">${money(i.unit_cost_paisa)}</td>
                <td class="num">${money(i.line_total_paisa)}</td>
              </tr>`).join("")}
          </tbody>
        </table>
      </div>`,
    foot: `
      ${po.status !== "received" && po.status !== "cancelled" ? `<button class="btn btn-primary" id="po-rcv">Receive Remaining Goods</button>` : ""}
      ${po.balance_paisa > 0 && po.status !== "cancelled" ? `<button class="btn btn-ghost" id="po-pay">Record Supplier Payment</button>` : ""}
    `,
  });
  const rcvBtn = m.root.querySelector("#po-rcv");
  if (rcvBtn) {
    rcvBtn.onclick = async () => {
      const items = po.items
        .filter(i => i.quantity > i.received_quantity)
        .map(i => ({ product_id: i.product_id, quantity: i.quantity - i.received_quantity }));
      try {
        await api.post(`/api/purchases/${po.id}/receive`, { items });
        toast("Goods received into stock");
        m.close(); onDone();
      } catch (e) { toast(e.message, "err"); }
    };
  }
  const payBtn = m.root.querySelector("#po-pay");
  if (payBtn) {
    payBtn.onclick = async () => {
      try {
        await api.post(`/api/purchases/${po.id}/payments`, { amount_paisa: po.balance_paisa, method: "cash" });
        toast("Supplier payment recorded");
        m.close(); onDone();
      } catch (e) { toast(e.message, "err"); }
    };
  }
}

async function renderSuppliers(box) {
  const sups = await api.get("/api/suppliers");
  box.innerHTML = `
    <div class="toolbar">
      <span class="spacer"></span>
      <button class="btn btn-primary" id="sup-new">+ New Supplier</button>
    </div>
    <div class="card">
      ${!sups.length ? emptyState("No suppliers registered") : `
      <div class="table-wrap">
        <table class="tbl">
          <thead><tr><th>Code</th><th>Name</th><th>Contact</th><th>Phone</th><th class="num">Payable Balance</th><th></th></tr></thead>
          <tbody>
            ${sups.map(s => `
              <tr>
                <td class="mono muted">${esc(s.code)}</td>
                <td><strong>${esc(s.name)}</strong></td>
                <td>${esc(s.contact_person || "—")}</td>
                <td>${esc(s.phone || "—")}</td>
                <td class="num">${s.balance_paisa > 0 ? `<span class="badge credit">${money(s.balance_paisa)}</span>` : money(0)}</td>
                <td class="right"><button class="btn btn-ghost btn-sm" data-edit="${s.id}">Edit</button></td>
              </tr>`).join("")}
          </tbody>
        </table>
      </div>`}
    </div>`;
  box.querySelector("#sup-new").onclick = () => editSup(null, () => renderSuppliers(box));
  box.querySelectorAll("[data-edit]").forEach(b => b.onclick = () => {
    const s = sups.find(x => x.id === Number(b.dataset.edit));
    editSup(s, () => renderSuppliers(box));
  });
}

function editSup(s, onDone) {
  const isNew = !s;
  const m = openModal({
    title: isNew ? "New Supplier" : `Edit ${s.name}`,
    body: `
      <form id="sup-f">
        <div class="form-row">
          <label><span>Supplier Name *</span><input name="name" required value="${esc(s?.name || "")}" /></label>
          <label><span>Contact Person</span><input name="contact_person" value="${esc(s?.contact_person || "")}" /></label>
        </div>
        <div class="form-row">
          <label><span>Phone</span><input name="phone" value="${esc(s?.phone || "")}" /></label>
          <label><span>Email</span><input name="email" value="${esc(s?.email || "")}" /></label>
        </div>
        <label><span>Address</span><input name="address" value="${esc(s?.address || "")}" /></label>
        <div class="modal-foot">
          <button type="button" class="btn btn-ghost" data-close>Cancel</button>
          <button type="submit" class="btn btn-primary">Save</button>
        </div>
      </form>`,
  });
  m.root.querySelector("#sup-f").onsubmit = async (e) => {
    e.preventDefault();
    const fd = formData(e.target);
    try {
      if (isNew) await api.post("/api/suppliers", fd);
      else await api.put(`/api/suppliers/${s.id}`, fd);
      toast("Supplier saved");
      m.close(); onDone();
    } catch (err) { toast(err.message, "err"); }
  };
}

async function renderPurchaseReturns(box) {
  const rets = await api.get("/api/purchase-returns");
  box.innerHTML = `
    <div class="card">
      <div class="card-head"><h3 class="card-title">Purchase Returns to Suppliers</h3></div>
      ${!rets.length ? emptyState("No purchase returns recorded") : `
      <div class="table-wrap">
        <table class="tbl">
          <thead><tr><th>Return #</th><th>Supplier</th><th>Date</th><th class="num">Total</th><th>Notes</th></tr></thead>
          <tbody>
            ${rets.map(r => `
              <tr>
                <td class="mono">${esc(r.return_number)}</td>
                <td>${esc(r.supplier_name || "")}</td>
                <td class="muted">${fmtDateTime(r.return_date)}</td>
                <td class="num">${money(r.total_paisa)}</td>
                <td class="muted">${esc(r.notes || "—")}</td>
              </tr>`).join("")}
          </tbody>
        </table>
      </div>`}
    </div>`;
}

export default {
  route: "purchases",
  title: "Purchases & Suppliers",
  load: async () => renderPurchases,
};
