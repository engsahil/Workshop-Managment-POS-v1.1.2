// Cashier Shifts & Cash Drawer Reconciliation.
import { api, auth } from "../core/api.js";
import { refreshHeaderContext } from "../core/app.js";
import { badge, emptyState, esc, fmtDateTime, formData, money, openModal, toast, toPaisa } from "../core/ui.js";

export async function renderShifts(root) {
  const [cur, list] = await Promise.all([
    api.get("/api/shifts/current"),
    api.get("/api/shifts?page_size=50"),
  ]);

  root.innerHTML = `
    <div class="card mb-3">
      <div class="card-head">
        <div>
          <h3 class="card-title">Current Cash Drawer Shift</h3>
          <div class="card-sub">Expected cash = opening cash + cash receipts - cash refunds - cash expenses +/- approved drawer movements</div>
        </div>
        <div class="flex">
          ${!cur ? `<button class="btn btn-primary" id="sh-open">Open New Shift</button>` : `
            ${auth.hasRole("admin", "manager") ? `<button class="btn btn-ghost btn-sm" id="sh-move">+ Cash In / Out</button>` : ""}
            <button class="btn btn-ghost btn-sm" id="sh-ledger">View Ledger</button>
            <button class="btn btn-danger btn-sm" id="sh-close">Close &amp; Reconcile Shift</button>
          `}
        </div>
      </div>
      ${!cur ? emptyState("You do not have an open cash shift. Open a shift before taking cash payments.") : `
      <div class="kpi-grid">
        <div class="kpi"><div class="k-label">Shift #${cur.id}</div><div class="k-value" style="font-size:15px">Opened ${fmtDateTime(cur.opened_at)}</div><div class="k-sub">${esc(cur.opening_notes || "")}</div></div>
        <div class="kpi"><div class="k-label">Opening Float</div><div class="k-value">${money(cur.opening_cash_paisa)}</div></div>
        <div class="kpi success"><div class="k-label">Expected Drawer Cash</div><div class="k-value">${money(cur.expected_cash_paisa)}</div></div>
      </div>`}
    </div>

    <div class="card">
      <div class="card-head"><h3 class="card-title">Shift History &amp; Reconciliation</h3></div>
      ${!list.items.length ? emptyState("No shifts recorded yet") : `
      <div class="table-wrap">
        <table class="tbl">
          <thead><tr><th>ID</th><th>Cashier</th><th>Opened</th><th>Closed</th><th class="num">Opening</th><th class="num">Expected</th><th class="num">Counted</th><th class="num">Variance</th><th>Status</th><th></th></tr></thead>
          <tbody>
            ${list.items.map(s => `
              <tr>
                <td class="mono">#${s.id}</td>
                <td>${esc(s.user_name || "")}</td>
                <td class="muted">${fmtDateTime(s.opened_at)}</td>
                <td class="muted">${fmtDateTime(s.closed_at)}</td>
                <td class="num">${money(s.opening_cash_paisa)}</td>
                <td class="num">${money(s.expected_cash_paisa)}</td>
                <td class="num">${s.counted_cash_paisa != null ? money(s.counted_cash_paisa) : "—"}</td>
                <td class="num">${s.difference_paisa != null ? `<strong style="color:${s.difference_paisa === 0 ? "var(--success)" : "var(--warning)"}">${money(s.difference_paisa)}</strong>` : "—"}</td>
                <td>${badge(s.status)}</td>
                <td class="right"><button class="btn btn-ghost btn-sm" data-led="${s.id}">Ledger</button></td>
              </tr>`).join("")}
          </tbody>
        </table>
      </div>`}
    </div>
  `;

  const reload = () => { refreshHeaderContext(); renderShifts(root); };

  const openBtn = root.querySelector("#sh-open");
  if (openBtn) {
    openBtn.onclick = () => {
      const m = openModal({
        title: "Open Cashier Shift",
        body: `
          <form id="sho-f">
            <label><span>Opening Cash Float (PKR) *</span><input name="opening_cash" type="number" step="0.01" min="0" value="0" required /></label>
            <label><span>Notes</span><input name="notes" /></label>
            <div class="modal-foot">
              <button type="button" class="btn btn-ghost" data-close>Cancel</button>
              <button type="submit" class="btn btn-primary">Open Shift</button>
            </div>
          </form>`,
      });
      m.root.querySelector("#sho-f").onsubmit = async (e) => {
        e.preventDefault();
        const fd = formData(e.target);
        try {
          await api.post("/api/shifts/open", { opening_cash_paisa: toPaisa(fd.opening_cash), notes: fd.notes || null });
          toast("Shift opened");
          m.close(); reload();
        } catch (err) { toast(err.message, "err"); }
      };
    };
  }

  const moveBtn = root.querySelector("#sh-move");
  if (moveBtn && cur) {
    moveBtn.onclick = () => {
      const m = openModal({
        title: "Cash Drawer Addition / Withdrawal",
        body: `
          <form id="shm-f">
            <div class="form-row">
              <label><span>Movement Type</span>
                <select name="movement_type">
                  <option value="addition">Cash Addition (Float Top-up)</option>
                  <option value="withdrawal">Cash Withdrawal (Safe Drop)</option>
                </select>
              </label>
              <label><span>Amount (PKR) *</span><input name="amount" type="number" step="0.01" min="1" required /></label>
            </div>
            <label><span>Reason *</span><input name="reason" required minlength="2" /></label>
            <div class="modal-foot">
              <button type="button" class="btn btn-ghost" data-close>Cancel</button>
              <button type="submit" class="btn btn-primary">Record Movement</button>
            </div>
          </form>`,
      });
      m.root.querySelector("#shm-f").onsubmit = async (e) => {
        e.preventDefault();
        const fd = formData(e.target);
        try {
          await api.post(`/api/shifts/${cur.id}/cash-movements`, {
            movement_type: fd.movement_type,
            amount_paisa: toPaisa(fd.amount),
            reason: fd.reason,
          });
          toast("Cash movement recorded");
          m.close(); reload();
        } catch (err) { toast(err.message, "err"); }
      };
    };
  }

  const closeBtn = root.querySelector("#sh-close");
  if (closeBtn && cur) {
    closeBtn.onclick = () => {
      const m = openModal({
        title: `Close & Reconcile Shift #${cur.id}`,
        body: `
          <form id="shc-f">
            <p>Expected cash in drawer: <strong>${money(cur.expected_cash_paisa)}</strong></p>
            <label><span>Counted Physical Cash (PKR) *</span><input name="counted" type="number" step="0.01" min="0" value="${(cur.expected_cash_paisa / 100).toFixed(2)}" required /></label>
            <label><span>Closing Notes</span><textarea name="closing_notes"></textarea></label>
            <div class="modal-foot">
              <button type="button" class="btn btn-ghost" data-close>Cancel</button>
              <button type="submit" class="btn btn-danger">Close Shift</button>
            </div>
          </form>`,
      });
      m.root.querySelector("#shc-f").onsubmit = async (e) => {
        e.preventDefault();
        const fd = formData(e.target);
        try {
          await api.post(`/api/shifts/${cur.id}/close`, {
            counted_cash_paisa: toPaisa(fd.counted),
            closing_notes: fd.closing_notes || null,
          });
          toast("Shift closed & reconciled");
          m.close(); reload();
        } catch (err) { toast(err.message, "err"); }
      };
    };
  }

  const ledBtn = root.querySelector("#sh-ledger");
  if (ledBtn && cur) ledBtn.onclick = () => openLedger(cur.id);
  root.querySelectorAll("[data-led]").forEach(b => b.onclick = () => openLedger(Number(b.dataset.led)));
}

async function openLedger(sid) {
  const led = await api.get(`/api/shifts/${sid}/ledger`);
  openModal({
    title: `Shift #${sid} Cash Ledger`,
    size: "lg",
    body: `
      <p>Opening: <strong>${money(led.shift.opening_cash_paisa)}</strong> · Expected: <strong>${money(led.shift.expected_cash_paisa)}</strong></p>
      <h4>Payments (${led.payments.length})</h4>
      ${!led.payments.length ? `<div class="muted">None</div>` : `
      <ul style="font-size:13px">${led.payments.map(p => `<li>${fmtDateTime(p.created_at)} — ${esc(p.invoice_number || p.kind)}: <strong>${money(p.amount_paisa)}</strong> (${esc(p.method)})</li>`).join("")}</ul>`}
      <h4>Cash Movements (${led.movements.length})</h4>
      ${!led.movements.length ? `<div class="muted">None</div>` : `
      <ul style="font-size:13px">${led.movements.map(m => `<li>${fmtDateTime(m.created_at)} — ${esc(m.movement_type)}: <strong>${money(m.amount_paisa)}</strong> (${esc(m.reason)})</li>`).join("")}</ul>`}
      <h4>Cash Expenses (${led.expenses.length})</h4>
      ${!led.expenses.length ? `<div class="muted">None</div>` : `
      <ul style="font-size:13px">${led.expenses.map(e => `<li>${esc(e.expense_number)} — ${esc(e.description || "")}: <strong>${money(e.amount_paisa)}</strong></li>`).join("")}</ul>`}
    `,
  });
}

export default {
  route: "shifts",
  title: "Cash Shifts",
  load: async () => renderShifts,
};
