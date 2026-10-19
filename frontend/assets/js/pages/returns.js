// Sale Returns & Refunds + Warranty Claims (Auto-fill, Coverage Check, Inspection Notes, Search, View & Delete)
import { api, auth } from "../core/api.js";
import { badge, confirmDialog, esc, fmtDate, fmtDateTime, fmtPKR, formData, openModal, toast, toPaisa } from "../core/ui.js";

export async function renderReturns(root, params) {
  let activeTab = params?.get("tab") === "claims" ? "claims" : "returns";
  root.innerHTML = `
    <div class="tabs">
      <div class="tab ${activeTab === "returns" ? "active" : ""}" data-t="returns">Sale Returns &amp; Refunds</div>
      <div class="tab ${activeTab === "claims" ? "active" : ""}" data-t="claims">Warranty Claims</div>
    </div>
    <div id="rw-body"></div>
  `;
  const body = root.querySelector("#rw-body");
  root.querySelectorAll(".tab").forEach(t => {
    t.onclick = () => {
      root.querySelectorAll(".tab").forEach(x => x.classList.remove("active"));
      t.classList.add("active");
      activeTab = t.dataset.t;
      if (activeTab === "returns") renderReturnsTab(body);
      else renderClaimsTab(body);
    };
  });
  if (activeTab === "returns") await renderReturnsTab(body);
  else await renderClaimsTab(body);
}

async function renderReturnsTab(box) {
  const canManageReturns = auth.hasRole("admin", "manager");
  box.innerHTML = `
    <div class="card">
      <div class="toolbar">
        <input id="ret-q" placeholder="Filter by return #, invoice #, customer, or reason..." style="min-width:260px" />
        <select id="ret-status">
          <option value="">All Statuses</option>
          <option value="pending">Pending Approval</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
        </select>
        <div class="spacer"></div>
        ${canManageReturns
          ? `<button class="btn btn-primary" id="ret-new">+ New Sale Return</button>`
          : `<span class="muted" style="font-size:12px">Note: Manager/Admin approval required to record returns</span>`}
      </div>
      <div id="ret-table"></div>
    </div>
  `;

  let allReturns = [];

  function renderTable() {
    const q = (box.querySelector("#ret-q").value || "").trim().toLowerCase();
    const rows = allReturns.filter(r => {
      if (!q) return true;
      const hay = `${r.return_number || ""} ${r.invoice_number || ""} ${r.customer_name || ""} ${r.reason || ""}`.toLowerCase();
      return hay.includes(q);
    });
    const tbox = box.querySelector("#ret-table");
    if (!rows.length) {
      tbox.innerHTML = `<div class="empty">No sale returns recorded matching the filter.</div>`;
      return;
    }
    tbox.innerHTML = `
      <div class="table-wrap">
        <table class="tbl">
          <thead>
            <tr>
              <th>Return #</th><th>Invoice</th><th>Customer</th><th>Items</th><th>Restock</th>
              <th>Refund Method</th><th class="num">Refund Total</th><th>Status</th><th>Date</th><th class="num">Actions</th>
            </tr>
          </thead>
          <tbody>
            ${rows.map(r => `
              <tr>
                <td class="mono"><a href="#/returns" data-viewret="${r.id}"><b>${esc(r.return_number)}</b></a></td>
                <td><a href="#/invoices?id=${r.invoice_id}" class="mono">${esc(r.invoice_number || "#" + r.invoice_id)}</a></td>
                <td>${esc(r.customer_name || "Walk-in Customer")}</td>
                <td>${(r.items || []).map(i => `${esc(i.description)} × ${i.quantity}`).join(", ") || "—"}</td>
                <td>${badge(r.restock_action)}</td>
                <td>${esc(r.refund_method)}</td>
                <td class="num"><b>${fmtPKR(r.total_paisa)}</b></td>
                <td>${badge(r.status)}</td>
                <td>${fmtDateTime(r.created_at || r.return_date)}</td>
                <td class="num">
                  <button class="btn btn-ghost btn-sm" data-viewret="${r.id}">View</button>
                  ${r.status === "pending" && canManageReturns ? `
                    <button class="btn btn-success btn-sm" data-dec="${r.id}" data-s="approved">Approve</button>
                    <button class="btn btn-danger btn-sm" data-dec="${r.id}" data-s="rejected">Reject</button>
                  ` : ""}
                </td>
              </tr>`).join("")}
          </tbody>
        </table>
      </div>`;

    tbox.querySelectorAll("[data-viewret]").forEach(b => {
      b.onclick = (e) => {
        e.preventDefault();
        const r = allReturns.find(x => x.id === Number(b.dataset.viewret));
        if (r) openReturnDetailModal(r, canManageReturns, load);
      };
    });

    tbox.querySelectorAll("[data-dec]").forEach(b => {
      b.onclick = async () => {
        const id = Number(b.dataset.dec);
        const status = b.dataset.s;
        if (!(await confirmDialog({
          title: `${status === "approved" ? "Approve" : "Reject"} Return`,
          message: `Mark return as ${status}? Approving will update stock and refund/credit the invoice.`,
          danger: status === "rejected",
        }))) return;
        try {
          await api.post(`/api/invoices/returns/${id}/decide`, { status });
          toast(`Return ${status}`);
          load();
        } catch (err) { toast(err.message, "err"); }
      };
    });
  }

  async function load() {
    const tbox = box.querySelector("#ret-table");
    const status = box.querySelector("#ret-status").value;
    const qs = status ? `?status=${encodeURIComponent(status)}&page_size=100` : `?page_size=100`;
    try {
      const res = await api.get(`/api/invoices/returns${qs}`);
      allReturns = res.items || [];
      renderTable();
    } catch (err) {
      tbox.innerHTML = `
        <div class="form-error" style="display:flex;align-items:center;justify-content:space-between;gap:12px">
          <span>Unable to load sale returns: ${esc(err.message || "Request failed")}</span>
          <button class="btn btn-ghost btn-sm" id="ret-retry">Retry</button>
        </div>`;
      const retryBtn = tbox.querySelector("#ret-retry");
      if (retryBtn) retryBtn.onclick = () => load();
    }
  }

  box.querySelector("#ret-q").oninput = () => renderTable();
  box.querySelector("#ret-status").onchange = () => load();
  const newBtn = box.querySelector("#ret-new");
  if (newBtn) newBtn.onclick = () => openNewReturnModal(load);
  await load();
}

function openReturnDetailModal(r, canManageReturns, onDone) {
  const m = openModal({
    title: `Sale Return ${r.return_number}`,
    size: "lg",
    body: `
      <div class="grid-2" style="margin-bottom:14px">
        <div>
          <div class="muted">Original Invoice</div>
          <div><a href="#/invoices?id=${r.invoice_id}" class="mono" data-close><b>${esc(r.invoice_number || "#" + r.invoice_id)}</b></a></div>
          <div class="muted mt-2">Customer</div>
          <div><b>${esc(r.customer_name || "Walk-in Customer")}</b></div>
          <div class="muted mt-2">Date</div>
          <div>${fmtDateTime(r.created_at || r.return_date)}</div>
        </div>
        <div>
          <div class="muted">Status</div>
          <div>${badge(r.status)}</div>
          <div class="muted mt-2">Restock / Refund Method</div>
          <div>${badge(r.restock_action)} · <b>${esc(r.refund_method)}</b></div>
          <div class="muted mt-2">Reason / Notes</div>
          <div>${esc(r.reason || "—")}${r.notes ? ` (${esc(r.notes)})` : ""}</div>
        </div>
      </div>
      <div class="table-wrap">
        <table class="tbl">
          <thead>
            <tr><th>Item Description</th><th class="num">Returned Qty</th><th class="num">Restocked Qty</th><th class="num">Unit Price</th><th class="num">Line Refund</th></tr>
          </thead>
          <tbody>
            ${(r.items || []).map(i => `
              <tr>
                <td>${esc(i.description)}</td>
                <td class="num">${i.quantity}</td>
                <td class="num">${i.restocked_quantity ?? 0}</td>
                <td class="num">${fmtPKR(i.unit_price_paisa)}</td>
                <td class="num"><b>${fmtPKR(i.line_total_paisa)}</b></td>
              </tr>`).join("")}
          </tbody>
        </table>
      </div>
      <div class="flex-between mt-3">
        <span class="muted">Total Refund / Credit</span>
        <span style="font-size:16px;font-weight:700">${fmtPKR(r.total_paisa)}</span>
      </div>
      <div class="modal-foot">
        ${r.status === "pending" && canManageReturns ? `
          <button type="button" class="btn btn-danger" id="rd-reject">Reject Return</button>
          <button type="button" class="btn btn-success" id="rd-approve">Approve Return</button>
        ` : ""}
        <button type="button" class="btn btn-ghost" data-close>Close</button>
      </div>`,
  });

  const decide = async (status) => {
    try {
      await api.post(`/api/invoices/returns/${r.id}/decide`, { status });
      toast(`Return ${status}`);
      m.close();
      onDone && onDone();
    } catch (err) { toast(err.message, "err"); }
  };
  const appBtn = m.root.querySelector("#rd-approve");
  const rejBtn = m.root.querySelector("#rd-reject");
  if (appBtn) appBtn.onclick = () => decide("approved");
  if (rejBtn) rejBtn.onclick = () => decide("rejected");
}

function openNewReturnModal(onDone) {
  const m = openModal({
    title: "New Sale Return",
    size: "lg",
    body: `
      <div class="toolbar">
        <input id="nr-inv-q" placeholder="Enter invoice number (e.g. INV-00001)..." style="flex:1" />
        <button class="btn btn-ghost" type="button" id="nr-find">Find Invoice</button>
      </div>
      <div id="nr-body"><div class="empty">Search and select an invoice to load returnable items.</div></div>`,
  });

  async function findInvoice() {
    const q = m.root.querySelector("#nr-inv-q").value.trim();
    const nrb = m.root.querySelector("#nr-body");
    try {
      const res = await api.get(`/api/invoices?q=${encodeURIComponent(q)}&page_size=10`);
      const items = (res.items || []).filter(inv => inv.status !== "void");
      if (!items.length) {
        nrb.innerHTML = `<div class="empty">No active invoice found matching "${esc(q)}".</div>`;
        return;
      }
      const inv = await api.get(`/api/invoices/${items[0].id}`);
      const prodItems = (inv.items || []).filter(i => i.item_type === "product");
      if (!prodItems.length) {
        nrb.innerHTML = `<div class="empty">Invoice <b>${esc(inv.invoice_number)}</b> has no physical product lines to return.</div>`;
        return;
      }
      nrb.innerHTML = `
        <form id="nr-f">
          <div class="card" style="padding:12px;margin-bottom:12px;background:var(--bg-subtle)">
            <div class="flex-between">
              <div>
                <b>${esc(inv.invoice_number)}</b> — ${esc(inv.customer_name || "Walk-in Customer")}
                ${inv.customer_phone ? `<span class="muted">(${esc(inv.customer_phone)})</span>` : ""}
              </div>
              <div>${badge(inv.status)} · Total: <b>${fmtPKR(inv.total_paisa)}</b></div>
            </div>
          </div>
          <div class="table-wrap mb-2">
            <table class="tbl">
              <thead>
                <tr>
                  <th>Item</th>
                  <th class="num">Sold Qty</th>
                  <th class="num">Already Returned</th>
                  <th class="num">Returnable</th>
                  <th class="num">Net Unit Price</th>
                  <th class="num">Return Qty</th>
                  <th class="num">Refund Subtotal</th>
                </tr>
              </thead>
              <tbody>
                ${prodItems.map(it => {
                  const soldQty = Number(it.quantity || 0);
                  const alreadyRet = Number(it.returned_quantity || 0);
                  const maxRet = it.returnable_quantity !== undefined
                    ? Number(it.returnable_quantity)
                    : Math.max(0, soldQty - alreadyRet);
                  const netUnitPaisa = soldQty > 0 ? Math.round(it.line_total_paisa / soldQty) : it.unit_price_paisa;
                  return `
                  <tr>
                    <td>${esc(it.description)}</td>
                    <td class="num">${soldQty}</td>
                    <td class="num">${alreadyRet}</td>
                    <td class="num"><b>${maxRet}</b></td>
                    <td class="num">${fmtPKR(netUnitPaisa)}</td>
                    <td class="num" style="width:120px">
                      <input type="number" step="0.01" min="0" max="${maxRet}" value="0"
                        data-ii="${it.id}" data-max="${maxRet}" data-unit="${netUnitPaisa}"
                        ${maxRet <= 0 ? "disabled title='Already fully returned'" : ""} />
                    </td>
                    <td class="num" data-line-sub="${it.id}">${fmtPKR(0)}</td>
                  </tr>`;
                }).join("")}
              </tbody>
            </table>
          </div>
          <div class="flex-between mb-2" style="padding:8px 12px;background:var(--bg-subtle);border-radius:var(--radius-sm)">
            <span class="muted">Calculated Refund Total</span>
            <strong id="nr-calc-total" style="font-size:15px">${fmtPKR(0)}</strong>
          </div>
          <div class="form-row">
            <label><span>Restock Action</span>
              <select name="restock_action">
                <option value="restock">Return to sellable stock</option>
                <option value="damaged">Mark as damaged (no restock)</option>
                <option value="discard">Discard</option>
              </select>
            </label>
            <label><span>Refund Method</span>
              <select name="refund_method">
                <option value="cash">Cash Refund</option>
                <option value="credit">Customer Credit Note</option>
                <option value="bank_transfer">Bank Transfer</option>
                <option value="card">Card</option>
                <option value="jazzcash">JazzCash</option>
                <option value="easypaisa">Easypaisa</option>
              </select>
            </label>
          </div>
          <label><span>Reason</span><input name="reason" placeholder="Customer return reason..." /></label>
          <label><span>Notes</span><input name="notes" placeholder="Optional internal notes..." /></label>
          <div class="modal-foot">
            <button type="button" class="btn btn-ghost" data-close>Cancel</button>
            <button type="submit" class="btn btn-primary">Submit Return</button>
          </div>
        </form>`;

      const qtyInputs = nrb.querySelectorAll("[data-ii]");
      const totalEl = nrb.querySelector("#nr-calc-total");

      function updateCalc() {
        let grand = 0;
        qtyInputs.forEach(inp => {
          const qVal = Math.max(0, Number(inp.value || 0));
          const unitPaisa = Number(inp.dataset.unit || 0);
          const sub = Math.round(qVal * unitPaisa);
          grand += sub;
          const cell = nrb.querySelector(`[data-line-sub="${inp.dataset.ii}"]`);
          if (cell) cell.textContent = fmtPKR(sub);
        });
        if (totalEl) totalEl.textContent = fmtPKR(grand);
      }

      qtyInputs.forEach(inp => {
        inp.oninput = () => updateCalc();
      });

      nrb.querySelector("#nr-f").onsubmit = async (e) => {
        e.preventDefault();
        const fd = formData(e.target);
        const returnItems = [];
        for (const inp of qtyInputs) {
          const val = Number(inp.value || 0);
          const maxAllowed = Number(inp.dataset.max || 0);
          if (val < 0) {
            toast("Return quantity cannot be negative", "err");
            return;
          }
          if (val > maxAllowed + 1e-9) {
            toast(`Return quantity (${val}) exceeds remaining returnable quantity (${maxAllowed})`, "err");
            return;
          }
          if (val > 0) {
            returnItems.push({ invoice_item_id: Number(inp.dataset.ii), quantity: val });
          }
        }
        if (!returnItems.length) {
          toast("Enter return quantity > 0 for at least one item", "warn");
          return;
        }
        try {
          const created = await api.post("/api/invoices/returns", {
            invoice_id: inv.id,
            restock_action: fd.restock_action,
            refund_method: fd.refund_method,
            reason: fd.reason || null,
            notes: fd.notes || null,
            items: returnItems,
          });
          toast(`Sale return ${created.return_number || ""} submitted (${fmtPKR(created.total_paisa)})`);
          m.close();
          onDone && onDone();
        } catch (err) { toast(err.message, "err"); }
      };
    } catch (err) {
      nrb.innerHTML = `
        <div class="form-error" style="display:flex;align-items:center;justify-content:space-between;gap:12px">
          <span>${esc(err.message || "Failed to look up invoice")}</span>
          <button type="button" class="btn btn-ghost btn-sm" id="nr-retry">Retry</button>
        </div>`;
      const rb = nrb.querySelector("#nr-retry");
      if (rb) rb.onclick = () => findInvoice();
    }
  }

  m.root.querySelector("#nr-find").onclick = () => findInvoice();
  m.root.querySelector("#nr-inv-q").onkeydown = (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      findInvoice();
    }
  };
}

async function renderClaimsTab(box) {
  const canDelete = auth.hasRole("admin", "manager");
  box.innerHTML = `
    <div class="card">
      <div class="toolbar">
        <input id="clm-q" placeholder="Search claim #, customer, vehicle, description..." style="min-width:250px" />
        <select id="clm-status">
          <option value="">All Statuses</option>
          <option value="open">Open</option>
          <option value="under_review">Under Review</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
          <option value="resolved">Resolved</option>
        </select>
        <div class="spacer"></div>
        <button class="btn btn-primary" id="clm-new">+ New Warranty Claim</button>
      </div>
      <div id="clm-table"></div>
    </div>
  `;

  async function load() {
    const tbox = box.querySelector("#clm-table");
    const q = encodeURIComponent(box.querySelector("#clm-q").value.trim());
    const st = encodeURIComponent(box.querySelector("#clm-status").value);
    try {
      const res = await api.get(`/api/claims?q=${q}&status=${st}&page_size=100`);
      const rows = res.items || [];
      if (!rows.length) {
        tbox.innerHTML = `<div class="empty">No warranty claims found.</div>`;
        return;
      }
      tbox.innerHTML = `
        <div class="table-wrap">
          <table class="tbl">
            <thead>
              <tr>
                <th>Claim #</th><th>Customer / Vehicle</th><th>Linked Doc</th><th>Item</th>
                <th>Coverage</th><th>Issue &amp; Resolution</th><th>Status</th><th>Date</th><th class="num">Actions</th>
              </tr>
            </thead>
            <tbody>
              ${rows.map(c => {
                let covBadge = `<span class="muted">—</span>`;
                if (c.is_within_warranty === true) {
                  covBadge = `<span class="badge ok" title="Expires ${esc(c.warranty_expiry_date || "")}">In Warranty</span>`;
                } else if (c.is_within_warranty === false) {
                  covBadge = `<span class="badge out" title="Expired ${esc(c.warranty_expiry_date || "")}">Expired</span>`;
                } else if (c.warranty_days) {
                  covBadge = `<span class="muted">${c.warranty_days}d</span>`;
                }
                const linked = [
                  c.invoice_number ? `<a href="#/invoices?id=${c.invoice_id}" class="mono">${esc(c.invoice_number)}</a>` : "",
                  c.job_number ? `<a href="#/jobs?id=${c.job_id}" class="mono">${esc(c.job_number)}</a>` : "",
                ].filter(Boolean).join(" · ") || "—";
                return `
                <tr>
                  <td class="mono"><a href="#/returns?tab=claims" data-viewclm="${c.id}"><b>${esc(c.claim_number)}</b></a></td>
                  <td>
                    <div>${esc(c.customer_name || "Walk-in")}</div>
                    ${c.vehicle_label ? `<div class="muted" style="font-size:11.5px">${esc(c.vehicle_label)}</div>` : ""}
                  </td>
                  <td>${linked}</td>
                  <td>${esc(c.product_name || c.service_name || c.item_type)}</td>
                  <td>${covBadge}</td>
                  <td>
                    <div>${esc(c.description)}</div>
                    ${c.inspection_notes ? `<div class="muted" style="font-size:11.5px">Inspection: ${esc(c.inspection_notes)}</div>` : ""}
                    ${c.action_taken ? `<div class="muted" style="font-size:11.5px">Action: ${esc(c.action_taken)}</div>` : ""}
                  </td>
                  <td>${badge(c.status)}</td>
                  <td>${fmtDate(c.claim_date || c.created_at)}</td>
                  <td class="num">
                    <button class="btn btn-ghost btn-sm" data-viewclm="${c.id}">View</button>
                    <button class="btn btn-ghost btn-sm" data-edit="${c.id}">Update</button>
                    ${canDelete ? `<button class="btn btn-ghost btn-sm" data-delclm="${c.id}">Delete</button>` : ""}
                  </td>
                </tr>`;
              }).join("")}
            </tbody>
          </table>
        </div>`;

      tbox.querySelectorAll("[data-viewclm]").forEach(b => {
        b.onclick = (e) => {
          e.preventDefault();
          const c = rows.find(x => x.id === Number(b.dataset.viewclm));
          if (c) openClaimDetailModal(c, () => openClaimModal(c, load));
        };
      });

      tbox.querySelectorAll("[data-edit]").forEach(b => {
        b.onclick = () => {
          const c = rows.find(x => x.id === Number(b.dataset.edit));
          if (c) openClaimModal(c, load);
        };
      });

      tbox.querySelectorAll("[data-delclm]").forEach(b => {
        b.onclick = async () => {
          const c = rows.find(x => x.id === Number(b.dataset.delclm));
          if (!c) return;
          if (!(await confirmDialog({
            title: `Delete Warranty Claim ${c.claim_number}`,
            message: `Are you sure you want to permanently delete warranty claim ${c.claim_number}?`,
            danger: true,
          }))) return;
          try {
            await api.del(`/api/claims/${c.id}`);
            toast(`Warranty claim ${c.claim_number} deleted`);
            load();
          } catch (err) { toast(err.message, "err"); }
        };
      });
    } catch (err) {
      tbox.innerHTML = `
        <div class="form-error" style="display:flex;align-items:center;justify-content:space-between;gap:12px">
          <span>Unable to load warranty claims: ${esc(err.message || "Request failed")}</span>
          <button class="btn btn-ghost btn-sm" id="clm-retry">Retry</button>
        </div>`;
      const retryBtn = tbox.querySelector("#clm-retry");
      if (retryBtn) retryBtn.onclick = () => load();
    }
  }

  let t;
  box.querySelector("#clm-q").oninput = () => { clearTimeout(t); t = setTimeout(load, 220); };
  box.querySelector("#clm-status").onchange = load;
  box.querySelector("#clm-new").onclick = () => openClaimModal(null, load);
  await load();
}

function openClaimDetailModal(c, onEdit) {
  let covText = "Not specified";
  if (c.is_within_warranty === true) covText = `Within Warranty (expires ${c.warranty_expiry_date || "—"})`;
  else if (c.is_within_warranty === false) covText = `Warranty Expired (${c.warranty_expiry_date || "—"})`;
  else if (c.warranty_days) covText = `${c.warranty_days} days`;

  const m = openModal({
    title: `Warranty Claim ${c.claim_number}`,
    size: "lg",
    body: `
      <div class="grid-2" style="margin-bottom:14px">
        <div>
          <div class="muted">Customer</div>
          <div><b>${esc(c.customer_name || "Walk-in Customer")}</b> ${c.customer_phone ? `<span class="muted">(${esc(c.customer_phone)})</span>` : ""}</div>
          <div class="muted mt-2">Vehicle</div>
          <div>${esc(c.vehicle_label || "—")}</div>
          <div class="muted mt-2">Linked Invoice / Job</div>
          <div>${c.invoice_number ? `Invoice <b>${esc(c.invoice_number)}</b>` : ""} ${c.job_number ? `Job <b>${esc(c.job_number)}</b>` : (!c.invoice_number ? "—" : "")}</div>
        </div>
        <div>
          <div class="muted">Status</div>
          <div>${badge(c.status)}</div>
          <div class="muted mt-2">Covered Item</div>
          <div><b>${esc(c.product_name || c.service_name || c.item_type)}</b> (${esc(c.item_type)})</div>
          <div class="muted mt-2">Warranty Coverage</div>
          <div>${esc(covText)}</div>
        </div>
      </div>
      <div class="card" style="background:var(--bg-subtle);padding:12px">
        <div class="muted">Defect / Issue Description</div>
        <div style="margin-bottom:8px">${esc(c.description || "—")}</div>
        <div class="muted">Inspection Findings</div>
        <div style="margin-bottom:8px">${esc(c.inspection_notes || "—")}</div>
        <div class="muted">Action Taken &amp; Resolution</div>
        <div>${esc(c.action_taken || "—")} ${c.resolution ? `· <b>${esc(c.resolution)}</b>` : ""}</div>
      </div>
      <div class="flex-between mt-3">
        <span>Internal Workshop Cost: <b>${fmtPKR(c.cost_paisa || 0)}</b></span>
        <span>Customer Refund: <b>${fmtPKR(c.refund_amount_paisa || 0)}</b></span>
      </div>
      <div class="modal-foot">
        <button type="button" class="btn btn-ghost" data-close>Close</button>
        <button type="button" class="btn btn-primary" id="cd-edit">Edit Claim</button>
      </div>`,
  });
  m.root.querySelector("#cd-edit").onclick = () => {
    m.close();
    onEdit && onEdit();
  };
}

async function openClaimModal(c, onDone) {
  let custRes = { items: [] }, vehRes = { items: [] }, prodRes = { items: [] }, invRes = { items: [] }, jobRes = { items: [] }, svcList = [];
  try {
    [custRes, vehRes, prodRes, invRes, jobRes, svcList] = await Promise.all([
      api.get("/api/customers?page_size=200"),
      api.get("/api/vehicles?page_size=200"),
      api.get("/api/products?page_size=200&include_services=false"),
      api.get("/api/invoices?page_size=100"),
      api.get("/api/jobs?page_size=100"),
      api.get("/api/services"),
    ]);
  } catch (err) {
    toast(err.message || "Failed to load reference data for warranty claim", "err");
    return;
  }
  const customers = custRes.items || [];
  const vehicles = vehRes.items || [];
  const products = prodRes.items || [];
  const invoices = invRes.items || [];
  const jobs = jobRes.items || [];
  const services = Array.isArray(svcList) ? svcList : (svcList.items || []);

  const m = openModal({
    title: c ? `Update Warranty Claim ${c.claim_number}` : "New Warranty Claim",
    size: "lg",
    body: `
      <form id="clm-f">
        ${!c ? `
          <div class="card" style="padding:12px;margin-bottom:14px;background:var(--bg-subtle)">
            <div style="font-size:12px;font-weight:600;margin-bottom:8px;color:var(--text-muted)">Quick Link Original Invoice or Job Card (auto-fills customer, vehicle &amp; purchase date)</div>
            <div class="form-row" style="margin-bottom:0">
              <label style="margin-bottom:0"><span>Original Invoice</span>
                <select name="invoice_id" id="clm-inv">
                  <option value="">— None —</option>
                  ${invoices.map(i => `<option value="${i.id}" data-cid="${i.customer_id || ""}" data-vid="${i.vehicle_id || ""}" data-dt="${(i.created_at || "").slice(0, 10)}">${esc(i.invoice_number)} — ${esc(i.customer_name || "Walk-in")} (${fmtPKR(i.total_paisa)})</option>`).join("")}
                </select>
              </label>
              <label style="margin-bottom:0"><span>Original Job Card</span>
                <select name="job_id" id="clm-job">
                  <option value="">— None —</option>
                  ${jobs.map(j => `<option value="${j.id}" data-cid="${j.customer_id || ""}" data-vid="${j.vehicle_id || ""}" data-dt="${(j.completed_at || j.checkin_at || "").slice(0, 10)}" data-wd="${j.warranty_days || 0}">${esc(j.job_number)} — ${esc(j.customer_name || "")} (${esc(j.vehicle_reg || "")})</option>`).join("")}
                </select>
              </label>
            </div>
          </div>
          <div class="form-row">
            <label><span>Customer</span>
              <select name="customer_id" id="clm-cust">
                <option value="">— Walk-in —</option>
                ${customers.map(cu => `<option value="${cu.id}">${esc(cu.name)} (${esc(cu.phone || "no phone")})</option>`).join("")}
              </select>
            </label>
            <label><span>Vehicle</span>
              <select name="vehicle_id" id="clm-veh">
                <option value="">— Optional —</option>
                ${vehicles.map(v => `<option value="${v.id}" data-cid="${v.customer_id}">${esc(v.registration_no)} — ${esc(v.make)} ${esc(v.model)}</option>`).join("")}
              </select>
            </label>
          </div>
          <div class="form-row">
            <label><span>Item Type</span>
              <select name="item_type" id="clm-itype">
                <option value="product">Part / Product</option>
                <option value="service">Labor / Service</option>
              </select>
            </label>
            <label id="clm-prod-wrap"><span>Part / Product</span>
              <select name="product_id" id="clm-prod">
                <option value="">— Select part —</option>
                ${products.map(p => `<option value="${p.id}" data-wd="${p.warranty_days || 0}">${esc(p.name)} (${esc(p.sku)}${p.warranty_days ? ` · ${p.warranty_days}d warranty` : ""})</option>`).join("")}
              </select>
            </label>
            <label id="clm-svc-wrap" hidden><span>Service / Labor</span>
              <select name="service_id" id="clm-svc">
                <option value="">— Select service —</option>
                ${services.map(s => `<option value="${s.id}">${esc(s.name)} (${esc(s.code)})</option>`).join("")}
              </select>
            </label>
          </div>
          <div class="form-row">
            <label><span>Original Purchase Date</span><input name="purchase_date" id="clm-pdate" type="date" /></label>
            <label><span>Warranty Period (days)</span><input name="warranty_days" id="clm-wdays" type="number" min="0" value="90" /></label>
          </div>
        ` : ""}
        <label><span>Issue / Defect Description *</span><textarea name="description" required>${esc(c?.description || "")}</textarea></label>
        <div class="form-row">
          <label><span>Inspection Findings / Notes</span><textarea name="inspection_notes" placeholder="Technician inspection findings...">${esc(c?.inspection_notes || "")}</textarea></label>
          <label><span>Action Taken</span><textarea name="action_taken" placeholder="Replaced part, repaired assembly, issued credit...">${esc(c?.action_taken || "")}</textarea></label>
        </div>
        <div class="form-row">
          <label><span>Status</span>
            <select name="status">
              ${["open", "under_review", "approved", "rejected", "resolved"].map(s => `<option value="${s}" ${(c?.status || "open") === s ? "selected" : ""}>${s.replace(/_/g, " ")}</option>`).join("")}
            </select>
          </label>
          <label><span>Resolution Type</span>
            <select name="resolution">
              <option value="">— Pending —</option>
              ${["repaired", "replaced", "refunded", "rejected"].map(r => `<option value="${r}" ${c?.resolution === r ? "selected" : ""}>${r}</option>`).join("")}
            </select>
          </label>
        </div>
        <div class="form-row">
          <label><span>Workshop Cost (PKR)</span><input name="cost" type="number" step="0.01" min="0" value="${((c?.cost_paisa || 0) / 100).toFixed(2)}" /></label>
          <label><span>Customer Refund Amount (PKR)</span><input name="refund" type="number" step="0.01" min="0" value="${((c?.refund_amount_paisa || 0) / 100).toFixed(2)}" /></label>
        </div>
        <div class="modal-foot">
          <button type="button" class="btn btn-ghost" data-close>Cancel</button>
          <button type="submit" class="btn btn-primary">${c ? "Save Claim Update" : "Create Warranty Claim"}</button>
        </div>
      </form>`,
  });

  if (!c) {
    const invSel = m.root.querySelector("#clm-inv");
    const jobSel = m.root.querySelector("#clm-job");
    const custSel = m.root.querySelector("#clm-cust");
    const vehSel = m.root.querySelector("#clm-veh");
    const pdateIn = m.root.querySelector("#clm-pdate");
    const wdaysIn = m.root.querySelector("#clm-wdays");
    const itypeSel = m.root.querySelector("#clm-itype");
    const prodWrap = m.root.querySelector("#clm-prod-wrap");
    const svcWrap = m.root.querySelector("#clm-svc-wrap");
    const prodSel = m.root.querySelector("#clm-prod");

    invSel.onchange = () => {
      const opt = invSel.selectedOptions[0];
      if (!opt || !opt.value) return;
      if (opt.dataset.cid) custSel.value = opt.dataset.cid;
      if (opt.dataset.vid) vehSel.value = opt.dataset.vid;
      if (opt.dataset.dt) pdateIn.value = opt.dataset.dt;
    };
    jobSel.onchange = () => {
      const opt = jobSel.selectedOptions[0];
      if (!opt || !opt.value) return;
      if (opt.dataset.cid) custSel.value = opt.dataset.cid;
      if (opt.dataset.vid) vehSel.value = opt.dataset.vid;
      if (opt.dataset.dt) pdateIn.value = opt.dataset.dt;
      if (Number(opt.dataset.wd) > 0) wdaysIn.value = opt.dataset.wd;
    };
    prodSel.onchange = () => {
      const opt = prodSel.selectedOptions[0];
      if (opt && Number(opt.dataset.wd) > 0) wdaysIn.value = opt.dataset.wd;
    };
    itypeSel.onchange = () => {
      const isSvc = itypeSel.value === "service";
      prodWrap.hidden = isSvc;
      svcWrap.hidden = !isSvc;
    };
  }

  m.root.querySelector("#clm-f").onsubmit = async (e) => {
    e.preventDefault();
    const fd = formData(e.target);
    const payload = {
      description: fd.description,
      inspection_notes: fd.inspection_notes || null,
      action_taken: fd.action_taken || null,
      status: fd.status,
      resolution: fd.resolution || null,
      cost_paisa: toPaisa(fd.cost),
      refund_amount_paisa: toPaisa(fd.refund),
    };
    if (!c) {
      payload.invoice_id = fd.invoice_id ? Number(fd.invoice_id) : null;
      payload.job_id = fd.job_id ? Number(fd.job_id) : null;
      payload.customer_id = fd.customer_id ? Number(fd.customer_id) : null;
      payload.vehicle_id = fd.vehicle_id ? Number(fd.vehicle_id) : null;
      payload.item_type = fd.item_type;
      payload.product_id = fd.item_type === "product" && fd.product_id ? Number(fd.product_id) : null;
      payload.service_id = fd.item_type === "service" && fd.service_id ? Number(fd.service_id) : null;
      payload.purchase_date = fd.purchase_date || null;
      payload.warranty_days = Number(fd.warranty_days || 0);
    }
    try {
      if (c) await api.put(`/api/claims/${c.id}`, payload);
      else await api.post("/api/claims", payload);
      toast(c ? "Warranty claim updated" : "Warranty claim created");
      m.close();
      onDone && onDone();
    } catch (err) { toast(err.message, "err"); }
  };
}

export default {
  route: "returns",
  title: "Returns & Warranty",
  load: async () => renderReturns,
};
