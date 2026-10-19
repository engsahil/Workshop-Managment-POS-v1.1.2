// Dashboard — live operational & financial overview.
import { api } from "../core/api.js";
import { openDailySummaryModal } from "../core/app.js";
import { badge, emptyState, esc, fmtDateTime, money, todayISO } from "../core/ui.js";

export async function renderDashboard(root) {
  const today = todayISO();
  root.innerHTML = `
    <div class="toolbar">
      <h2 style="margin:0;font-size:18px;font-weight:600">Operations Overview</h2>
      <span class="spacer"></span>
      <button class="btn btn-ghost btn-sm" data-preset="today">Today</button>
      <button class="btn btn-ghost btn-sm" data-preset="7d">Last 7 Days</button>
      <button class="btn btn-ghost btn-sm" data-preset="month">This Month</button>
      <input type="date" id="d-from" value="${today}" aria-label="From date" />
      <span class="muted">to</span>
      <input type="date" id="d-to" value="${today}" aria-label="To date" />
      <button class="btn btn-primary btn-sm" id="d-apply">Apply</button>
      <button class="btn btn-ghost btn-sm" id="d-daily-summary">Daily Summary</button>
    </div>
    <div id="dash-body"><div class="muted">Loading dashboard…</div></div>
  `;

  const fromEl = root.querySelector("#d-from");
  const toEl = root.querySelector("#d-to");

  async function load() {
    const body = root.querySelector("#dash-body");
    const df = encodeURIComponent(fromEl.value || today);
    const dt = encodeURIComponent(toEl.value || today);
    let d;
    try {
      d = await api.get(`/api/reports/dashboard?date_from=${df}&date_to=${dt}`);
    } catch (err) {
      body.innerHTML = `
        <div class="card">
          <div class="form-error" style="margin-bottom:10px">
            Could not load dashboard summary: ${esc(err.message || "Unexpected error")}
          </div>
          <button class="btn btn-primary btn-sm" id="d-retry">Retry</button>
        </div>`;
      body.querySelector("#d-retry")?.addEventListener("click", load);
      return;
    }

    const sales = d?.sales || {};
    const collections = d?.collections || {};
    const profit = d?.profit || {};
    const receivables = d?.receivables || {};
    const jobs = d?.jobs || {};
    const inventory = d?.inventory || {};
    const recent = d?.recent || {};

    body.innerHTML = `
      <div class="kpi-grid">
        <div class="kpi">
          <div class="k-label">Invoiced Sales</div>
          <div class="k-value">${money(sales.revenue_paisa)}</div>
          <div class="k-sub">${sales.invoice_count || 0} invoice(s) · Discounts ${money(sales.discounts_paisa)}</div>
        </div>
        <div class="kpi success">
          <div class="k-label">Payments Collected</div>
          <div class="k-value">${money(collections.total_paisa)}</div>
          <div class="k-sub">Cash ${money(collections.cash_paisa)} · Digital/Card ${money(collections.card_digital_paisa)}</div>
        </div>
        <div class="kpi">
          <div class="k-label">Parts vs Labor</div>
          <div class="k-value">${money(sales.parts_paisa)}</div>
          <div class="k-sub">Labor: ${money(sales.services_paisa)}</div>
        </div>
        <div class="kpi ${(profit.net_profit_paisa || 0) >= 0 ? "success" : "danger"}">
          <div class="k-label">Estimated Net Profit</div>
          <div class="k-value">${money(profit.net_profit_paisa)}</div>
          <div class="k-sub">Gross ${money(profit.gross_profit_paisa)} · Expenses ${money(profit.expenses_paisa)}</div>
        </div>
        <div class="kpi ${(receivables.outstanding_paisa || 0) > 0 ? "warn" : ""}">
          <div class="k-label">Customer Receivables</div>
          <div class="k-value">${money(receivables.outstanding_paisa)}</div>
          <div class="k-sub">${receivables.credit_customers || 0} account(s) · Advances ${money(receivables.advances_paisa)}</div>
        </div>
        <div class="kpi info">
          <div class="k-label">Workshop Jobs</div>
          <div class="k-value">${jobs.active || 0} active</div>
          <div class="k-sub">${jobs.vehicles_in_service || 0} in bay · ${jobs.completed || 0} completed</div>
        </div>
        <div class="kpi ${(inventory.low_stock_count || 0) > 0 ? "warn" : ""}">
          <div class="k-label">Low-Stock Alerts</div>
          <div class="k-value">${inventory.low_stock_count || 0}</div>
          <div class="k-sub">Stock value ${money(inventory.valuation_paisa)}</div>
        </div>
      </div>

      <div class="grid-2">
        <div class="card">
          <div class="card-head">
            <h3 class="card-title">Recent Invoices</h3>
            <a href="#/invoices" class="btn btn-ghost btn-sm">View all</a>
          </div>
          ${(recent.invoices || []).length === 0 ? emptyState("No invoices recorded yet") : `
          <div class="table-wrap">
            <table class="tbl">
              <thead><tr><th>Invoice</th><th>Customer</th><th>Vehicle</th><th class="num">Total</th><th class="num">Balance</th><th>Status</th></tr></thead>
              <tbody>
                ${(recent.invoices || []).map(i => `
                  <tr>
                    <td><a href="#/invoices?id=${i.id}"><strong>${esc(i.invoice_number)}</strong></a></td>
                    <td>${esc(i.customer_name)}</td>
                    <td class="muted">${esc(i.vehicle)}</td>
                    <td class="num">${money(i.total_paisa)}</td>
                    <td class="num">${money(i.balance_paisa)}</td>
                    <td>${badge(i.status)}</td>
                  </tr>`).join("")}
              </tbody>
            </table>
          </div>`}
        </div>

        <div class="card">
          <div class="card-head">
            <h3 class="card-title">Recent Service Jobs</h3>
            <a href="#/jobs" class="btn btn-ghost btn-sm">View all</a>
          </div>
          ${(recent.jobs || []).length === 0 ? emptyState("No service jobs yet") : `
          <div class="table-wrap">
            <table class="tbl">
              <thead><tr><th>Job #</th><th>Customer</th><th>Plate</th><th>Status</th><th>Checked In</th></tr></thead>
              <tbody>
                ${(recent.jobs || []).map(j => `
                  <tr>
                    <td><a href="#/jobs?id=${j.id}"><strong>${esc(j.job_number)}</strong></a></td>
                    <td>${esc(j.customer_name || "—")}</td>
                    <td>${esc(j.registration_no || "—")}</td>
                    <td>${badge(j.status)}</td>
                    <td class="muted">${fmtDateTime(j.checkin_at)}</td>
                  </tr>`).join("")}
              </tbody>
            </table>
          </div>`}
        </div>
      </div>

      <div class="grid-2 mt-3">
        <div class="card">
          <div class="card-head">
            <h3 class="card-title">Low-Stock Inventory</h3>
            <a href="#/products?low=1" class="btn btn-ghost btn-sm">Manage stock</a>
          </div>
          ${(inventory.low_stock_items || []).length === 0 ? emptyState("All stocked items are above minimum thresholds") : `
          <div class="table-wrap">
            <table class="tbl">
              <thead><tr><th>Item</th><th>SKU</th><th class="num">On Hand</th><th class="num">Min Level</th></tr></thead>
              <tbody>
                ${(inventory.low_stock_items || []).map(p => `
                  <tr>
                    <td>${esc(p.name)}</td>
                    <td class="mono muted">${esc(p.sku || "—")}</td>
                    <td class="num">${p.quantity_on_hand}</td>
                    <td class="num muted">${p.min_stock}</td>
                  </tr>`).join("")}
              </tbody>
            </table>
          </div>`}
        </div>

        <div class="card">
          <div class="card-head">
            <h3 class="card-title">Recent Expenses</h3>
            <a href="#/expenses" class="btn btn-ghost btn-sm">Manage expenses</a>
          </div>
          ${(recent.expenses || []).length === 0 ? emptyState("No expenses recorded") : `
          <div class="table-wrap">
            <table class="tbl">
              <thead><tr><th>Number</th><th>Description</th><th class="num">Amount</th></tr></thead>
              <tbody>
                ${(recent.expenses || []).map(e => `
                  <tr>
                    <td class="mono">${esc(e.expense_number)}</td>
                    <td>${esc(e.description || "—")}</td>
                    <td class="num">${money(e.amount_paisa)}</td>
                  </tr>`).join("")}
              </tbody>
            </table>
          </div>`}
        </div>
      </div>
    `;
  }

  root.querySelector("#d-apply").onclick = load;
  root.querySelector("#d-daily-summary").onclick = () => openDailySummaryModal(toEl.value || today);
  root.querySelectorAll("[data-preset]").forEach(btn => {
    btn.onclick = () => {
      const p = btn.dataset.preset;
      const now = new Date();
      const to = todayISO();
      let from = to;
      if (p === "7d") {
        const d = new Date(now.getTime() - 6 * 86400000);
        from = d.toISOString().slice(0, 10);
      } else if (p === "month") {
        from = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-01`;
      }
      fromEl.value = from;
      toEl.value = to;
      load();
    };
  });

  await load();
}
