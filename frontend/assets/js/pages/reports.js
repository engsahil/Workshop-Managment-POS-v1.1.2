// Reports & Analytics — sales trend, profit & COGS, breakdowns, stock valuation, mechanic commission, CSV export.
import { api } from "../core/api.js";
import { badge, downloadCSV, emptyState, esc, fmtDateTime, money, todayISO } from "../core/ui.js";

export async function renderReports(root) {
  const today = todayISO();
  const monthStart = `${today.slice(0, 8)}01`;

  root.innerHTML = `
    <div class="toolbar">
      <label style="display:flex;align-items:center;gap:6px;margin:0"><span style="margin:0">From</span><input type="date" id="r-from" value="${monthStart}" /></label>
      <label style="display:flex;align-items:center;gap:6px;margin:0"><span style="margin:0">To</span><input type="date" id="r-to" value="${today}" /></label>
      <button class="btn btn-primary btn-sm" id="r-run">Generate Reports</button>
      <span class="spacer"></span>
      <button class="btn btn-ghost btn-sm" id="r-csv">Export Current Table CSV</button>
    </div>

    <div class="tabs">
      <div class="tab active" data-t="profit">Profit, COGS &amp; Expenses</div>
      <div class="tab" data-t="product">Sales by Part</div>
      <div class="tab" data-t="service">Sales by Labor</div>
      <div class="tab" data-t="payments">Payment Methods</div>
      <div class="tab" data-t="mechanics">Mechanic Performance</div>
      <div class="tab" data-t="stock">Stock Valuation</div>
    </div>
    <div id="r-body"></div>
  `;

  let currentTab = "profit";
  let lastRows = [];

  async function run() {
    const df = root.querySelector("#r-from").value || monthStart;
    const dt = root.querySelector("#r-to").value || today;
    const body = root.querySelector("#r-body");

    if (currentTab === "profit") {
      const [p, trend] = await Promise.all([
        api.get(`/api/reports/profit?date_from=${df}&date_to=${dt}`),
        api.get(`/api/reports/sales-trend?date_from=${df}&date_to=${dt}`),
      ]);
      lastRows = trend;
      body.innerHTML = `
        <div class="kpi-grid">
          <div class="kpi"><div class="k-label">Total Net Revenue</div><div class="k-value">${money(p.revenue_paisa)}</div><div class="k-sub">Parts ${money(p.parts_revenue_paisa)} · Labor ${money(p.labor_revenue_paisa)}</div></div>
          <div class="kpi"><div class="k-label">COGS (Part Cost Snapshot)</div><div class="k-value">${money(p.cogs_paisa)}</div><div class="k-sub">Returns: ${money(p.returns_value_paisa)}</div></div>
          <div class="kpi success"><div class="k-label">Gross Profit</div><div class="k-value">${money(p.gross_profit_paisa)}</div></div>
          <div class="kpi warn"><div class="k-label">Operating Expenses</div><div class="k-value">${money(p.expenses_paisa)}</div></div>
          <div class="kpi ${p.net_profit_paisa >= 0 ? "success" : "danger"}"><div class="k-label">Estimated Net Profit</div><div class="k-value">${money(p.net_profit_paisa)}</div></div>
        </div>
        <div class="card">
          <div class="card-head">
            <div>
              <h3 class="card-title">Daily Sales Trend (${esc(df)} to ${esc(dt)})</h3>
              <div class="card-sub">${esc(p.methodology)}</div>
            </div>
          </div>
          <div class="table-wrap">
            <table class="tbl">
              <thead><tr><th>Date</th><th class="num">Invoices</th><th class="num">Revenue</th></tr></thead>
              <tbody>
                ${trend.filter(x => x.invoices > 0 || trend.length <= 14).map(r => `
                  <tr><td>${esc(r.date)}</td><td class="num">${r.invoices}</td><td class="num"><strong>${money(r.revenue_paisa)}</strong></td></tr>`).join("")}
              </tbody>
            </table>
          </div>
        </div>`;
    } else if (currentTab === "product" || currentTab === "service") {
      const rows = await api.get(`/api/reports/sales-by/${currentTab}?date_from=${df}&date_to=${dt}`);
      lastRows = rows;
      body.innerHTML = `
        <div class="card">
          <div class="card-head"><h3 class="card-title">Sales Breakdown by ${currentTab === "product" ? "Spare Part" : "Service / Labor"}</h3></div>
          ${!rows.length ? emptyState("No sales in selected date range") : `
          <div class="table-wrap">
            <table class="tbl">
              <thead><tr><th>Item</th><th class="num">Qty Sold</th><th class="num">Net Revenue</th></tr></thead>
              <tbody>
                ${rows.map(r => `<tr><td><strong>${esc(r.name)}</strong></td><td class="num">${r.quantity}</td><td class="num">${money(r.amount_paisa)}</td></tr>`).join("")}
              </tbody>
            </table>
          </div>`}
        </div>`;
    } else if (currentTab === "payments") {
      const rows = await api.get(`/api/reports/payments-summary?date_from=${df}&date_to=${dt}`);
      lastRows = rows;
      body.innerHTML = `
        <div class="card">
          <div class="card-head"><h3 class="card-title">Collections by Payment Method</h3></div>
          ${!rows.length ? emptyState("No payments in selected period") : `
          <div class="table-wrap">
            <table class="tbl">
              <thead><tr><th>Method</th><th class="num">Transactions</th><th class="num">Total Collected</th></tr></thead>
              <tbody>
                ${rows.map(r => `<tr><td>${badge(r.method)}</td><td class="num">${r.count}</td><td class="num"><strong>${money(r.amount_paisa)}</strong></td></tr>`).join("")}
              </tbody>
            </table>
          </div>`}
        </div>`;
    } else if (currentTab === "mechanics") {
      const rows = await api.get(`/api/reports/mechanic-performance?date_from=${df}&date_to=${dt}`);
      lastRows = rows;
      body.innerHTML = `
        <div class="card">
          <div class="card-head"><h3 class="card-title">Mechanic Performance &amp; Commission Calculation</h3></div>
          ${!rows.length ? emptyState("No mechanics") : `
          <div class="table-wrap">
            <table class="tbl">
              <thead><tr><th>Mechanic</th><th class="num">Jobs Assigned</th><th class="num">Completed</th><th class="num">Labor Revenue</th><th class="num">Calculated Commission</th></tr></thead>
              <tbody>
                ${rows.map(r => `
                  <tr>
                    <td><strong>${esc(r.name)}</strong></td>
                    <td class="num">${r.jobs_assigned}</td>
                    <td class="num">${r.jobs_completed}</td>
                    <td class="num">${money(r.labor_revenue_paisa)}</td>
                    <td class="num"><strong>${money(r.commission_due_paisa)}</strong></td>
                  </tr>`).join("")}
              </tbody>
            </table>
          </div>`}
        </div>`;
    } else if (currentTab === "stock") {
      const rows = await api.get("/api/reports/stock");
      lastRows = rows;
      const totalVal = rows.reduce((a, b) => a + b.value_paisa, 0);
      body.innerHTML = `
        <div class="card">
          <div class="card-head">
            <h3 class="card-title">Inventory Valuation Report</h3>
            <div>Total Weighted-Average Value: <strong>${money(totalVal)}</strong></div>
          </div>
          ${!rows.length ? emptyState("No stock items") : `
          <div class="table-wrap">
            <table class="tbl">
              <thead><tr><th>SKU</th><th>Product</th><th class="num">On Hand</th><th class="num">Min</th><th class="num">Avg Cost</th><th class="num">Sell Price</th><th class="num">Stock Value</th><th>Status</th></tr></thead>
              <tbody>
                ${rows.map(r => `
                  <tr>
                    <td class="mono muted">${esc(r.sku || "—")}</td>
                    <td><strong>${esc(r.name)}</strong></td>
                    <td class="num">${r.quantity_on_hand}</td>
                    <td class="num muted">${r.min_stock}</td>
                    <td class="num">${money(r.avg_cost_paisa)}</td>
                    <td class="num">${money(r.selling_price_paisa)}</td>
                    <td class="num"><strong>${money(r.value_paisa)}</strong></td>
                    <td>${badge(r.status)}</td>
                  </tr>`).join("")}
              </tbody>
            </table>
          </div>`}
        </div>`;
    }
  }

  root.querySelector("#r-run").onclick = run;
  root.querySelector("#r-csv").onclick = () => downloadCSV(`report_${currentTab}.csv`, lastRows);
  root.querySelectorAll(".tab").forEach(t => {
    t.onclick = () => {
      root.querySelectorAll(".tab").forEach(x => x.classList.remove("active"));
      t.classList.add("active");
      currentTab = t.dataset.t;
      run();
    };
  });

  await run();
}

export default {
  route: "reports",
  title: "Reports & Analytics",
  load: async () => renderReports,
};
