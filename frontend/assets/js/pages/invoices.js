// Invoices & Credit — list, filter, detail, collect due payment, void invoice, print receipt.
import { api, auth } from "../core/api.js";
import { badge, confirmDialog, emptyState, esc, fmtDateTime, formData, money, openModal, toast, toPaisa } from "../core/ui.js";
import { showReceiptModal } from "./pos.js";

export async function renderInvoices(root, params = {}) {
  root.innerHTML = `
    <div class="toolbar">
      <input id="inv-q" placeholder="Search invoice #…" />
      <select id="inv-status">
        <option value="">All statuses</option>
        <option value="paid">Paid</option><option value="partial">Partial</option>
        <option value="credit">Credit (Unpaid)</option><option value="returned">Returned</option>
        <option value="void">Void</option>
      </select>
      <input type="date" id="inv-from" />
      <input type="date" id="inv-to" />
      <button class="btn btn-ghost btn-sm" id="inv-filter">Filter</button>
      <span class="spacer"></span>
      <a class="btn btn-primary" href="#/pos">+ New POS Sale</a>
    </div>
    <div class="card" id="inv-list"></div>
  `;

  async function load() {
    const q = encodeURIComponent(root.querySelector("#inv-q").value.trim());
    const st = root.querySelector("#inv-status").value;
    const df = root.querySelector("#inv-from").value;
    const dt = root.querySelector("#inv-to").value;
    const url = `/api/invoices?q=${q}&status=${st}${df ? `&date_from=${df}` : ""}${dt ? `&date_to=${dt}` : ""}&page_size=100`;
    const res = await api.get(url);
    const list = root.querySelector("#inv-list");
    if (!res.items.length) { list.innerHTML = emptyState("No invoices match your filter"); return; }
    list.innerHTML = `
      <div class="table-wrap">
        <table class="tbl">
          <thead>
            <tr>
              <th>Invoice #</th><th>Date</th><th>Customer</th><th>Vehicle / Job</th>
              <th class="num">Total</th><th class="num">Paid</th><th class="num">Balance</th><th>Status</th><th></th>
            </tr>
          </thead>
          <tbody>
            ${res.items.map(i => `
              <tr>
                <td class="mono"><strong>${esc(i.invoice_number)}</strong></td>
                <td class="muted">${fmtDateTime(i.created_at)}</td>
                <td>${esc(i.customer_name)}</td>
                <td class="muted">${esc(i.vehicle_label || i.job_number || "—")}</td>
                <td class="num">${money(i.total_paisa)}</td>
                <td class="num">${money(i.paid_paisa)}</td>
                <td class="num">${i.balance_paisa > 0 ? `<strong style="color:var(--warning)">${money(i.balance_paisa)}</strong>` : money(0)}</td>
                <td>${badge(i.status)}</td>
                <td class="right"><button class="btn btn-ghost btn-sm" data-open="${i.id}">Open</button></td>
              </tr>`).join("")}
          </tbody>
        </table>
      </div>`;
    list.querySelectorAll("[data-open]").forEach(b => b.onclick = () => openInvoice(Number(b.dataset.open), load));
  }

  root.querySelector("#inv-filter").onclick = load;
  root.querySelector("#inv-q").onkeydown = (e) => { if (e.key === "Enter") load(); };
  root.querySelector("#inv-status").onchange = load;
  await load();
  if (params.id) openInvoice(Number(params.id), load);
}

async function openInvoice(iid, onDone) {
  const inv = await api.get(`/api/invoices/${iid}`);
  const canFin = auth.hasRole("admin", "manager");
  const { close, root } = openModal({
    title: `Invoice ${inv.invoice_number}`,
    size: "lg",
    body: `
      <div class="flex-between mb-2">
        <div>
          <strong>${esc(inv.customer_name)}</strong> ${inv.customer_phone ? `(${esc(inv.customer_phone)})` : ""} ·
          ${inv.vehicle_label ? `Vehicle: ${esc(inv.vehicle_label)} · ` : ""}
          ${inv.job_number ? `Job: <a href="#/jobs?id=${inv.job_id}">${esc(inv.job_number)}</a> · ` : ""}
          Cashier: ${esc(inv.cashier_name || "—")}
        </div>
        <div>${badge(inv.status)}</div>
      </div>

      <div class="table-wrap">
        <table class="tbl">
          <thead><tr><th>Type</th><th>Description</th><th class="num">Qty</th><th class="num">Unit Price</th><th class="num">Discount</th><th class="num">Line Total</th></tr></thead>
          <tbody>
            ${inv.items.map(it => `
              <tr>
                <td>${badge(it.item_type)}</td>
                <td>${esc(it.description)}</td>
                <td class="num">${it.quantity} ${esc(it.unit)}</td>
                <td class="num">${money(it.unit_price_paisa)}</td>
                <td class="num">${money(it.discount_paisa)}</td>
                <td class="num"><strong>${money(it.line_total_paisa)}</strong></td>
              </tr>`).join("")}
          </tbody>
        </table>
      </div>

      <div class="grid-2 mt-3">
        <div>
          <h4 style="margin:0 0 6px">Payments Recorded</h4>
          ${inv.payments.length === 0 ? `<div class="muted">No payments recorded yet</div>` : `
          <ul style="margin:0;padding-left:18px;font-size:13px">
            ${inv.payments.map(p => `<li>${fmtDateTime(p.created_at)} — <strong>${money(p.amount_paisa)}</strong> via ${esc(p.method)} (${esc(p.kind)})${p.reference ? ` · Ref: ${esc(p.reference)}` : ""}</li>`).join("")}
          </ul>`}
          ${inv.void_reason ? `<div class="form-error mt-2">Voided: ${esc(inv.void_reason)}</div>` : ""}
        </div>
        <div class="cart-totals">
          <div class="totals-row"><span>Subtotal</span><span>${money(inv.subtotal_paisa)}</span></div>
          <div class="totals-row"><span>Discount</span><span>-${money(inv.discount_paisa)}</span></div>
          <div class="totals-row"><span>Tax</span><span>${money(inv.tax_paisa)}</span></div>
          <div class="totals-row grand"><span>Total</span><span>${money(inv.total_paisa)}</span></div>
          <div class="totals-row"><span>Paid</span><span>${money(inv.paid_paisa)}</span></div>
          <div class="totals-row"><span>Balance Due</span><span><strong>${money(inv.balance_paisa)}</strong></span></div>
        </div>
      </div>
    `,
    foot: `
      <button class="btn btn-ghost" id="iv-print">Print / Receipt</button>
      ${inv.balance_paisa > 0 && inv.status !== "void" ? `<button class="btn btn-primary" id="iv-pay">Collect Payment</button>` : ""}
      ${canFin && inv.status !== "void" ? `<button class="btn btn-danger" id="iv-void">Void Invoice</button>` : ""}
    `,
  });

  root.querySelector("#iv-print").onclick = () => { close(); showReceiptModal(inv); };

  const payBtn = root.querySelector("#iv-pay");
  if (payBtn) {
    payBtn.onclick = () => {
      const m = openModal({
        title: `Collect Payment — ${inv.invoice_number}`,
        body: `
          <form id="iv-pay-form">
            <div class="form-row">
              <label><span>Amount (PKR) * (max ${(inv.balance_paisa / 100).toFixed(2)})</span>
                <input name="amount" type="number" step="0.01" min="1" max="${(inv.balance_paisa / 100).toFixed(2)}" value="${(inv.balance_paisa / 100).toFixed(2)}" required />
              </label>
              <label><span>Method</span>
                <select name="method">
                  <option value="cash">Cash</option><option value="card">Card</option>
                  <option value="bank_transfer">Bank Transfer</option>
                  <option value="jazzcash">JazzCash</option><option value="easypaisa">Easypaisa</option>
                </select>
              </label>
            </div>
            <label><span>Reference</span><input name="reference" /></label>
            <div class="modal-foot">
              <button type="button" class="btn btn-ghost" data-close>Cancel</button>
              <button type="submit" class="btn btn-primary">Record Payment</button>
            </div>
          </form>`,
      });
      m.root.querySelector("#iv-pay-form").onsubmit = async (e) => {
        e.preventDefault();
        const fd = formData(e.target);
        try {
          await api.post(`/api/invoices/${inv.id}/payments`, {
            amount_paisa: toPaisa(fd.amount),
            method: fd.method,
            reference: fd.reference || null,
          });
          toast("Payment recorded");
          m.close(); close();
          onDone && onDone();
        } catch (err) { toast(err.message, "err"); }
      };
    };
  }

  const voidBtn = root.querySelector("#iv-void");
  if (voidBtn) {
    voidBtn.onclick = async () => {
      const m = openModal({
        title: `Void Invoice ${inv.invoice_number}`,
        body: `
          <form id="void-form">
            <p class="muted">Voiding restores sold stock to inventory and reverses payments on this invoice.</p>
            <label><span>Reason for Voiding *</span><input name="reason" required minlength="2" /></label>
            <div class="modal-foot">
              <button type="button" class="btn btn-ghost" data-close>Cancel</button>
              <button type="submit" class="btn btn-danger">Confirm Void</button>
            </div>
          </form>`,
      });
      m.root.querySelector("#void-form").onsubmit = async (e) => {
        e.preventDefault();
        const fd = formData(e.target);
        try {
          await api.post(`/api/invoices/${inv.id}/void`, { reason: fd.reason });
          toast("Invoice voided & stock restored");
          m.close(); close();
          onDone && onDone();
        } catch (err) { toast(err.message, "err"); }
      };
    };
  }
}
