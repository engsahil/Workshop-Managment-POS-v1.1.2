// Operational Help & Reference Guide (v1.2.2).
export async function renderHelp(root) {
  root.innerHTML = `
    <div class="grid-2">
      <div class="card">
        <div class="card-head"><h3 class="card-title">Daily Workshop &amp; POS Workflow Guide</h3></div>
        <ol style="line-height:1.7;padding-left:18px;margin:0">
          <li><strong>Open Cashier Shift:</strong> Go to <a href="#/shifts">Cash Shifts</a> at the start of the day and record your opening cash float.</li>
          <li><strong>Counter Part / Service Sales:</strong> Use <a href="#/pos">POS Billing</a> to scan barcodes or click parts/labor tiles, split payments across Cash/Card/JazzCash/Easypaisa, and print thermal 80mm or A4 receipts.</li>
          <li><strong>Vehicle Check-In (Job Cards):</strong> Use <a href="#/jobs">Job Cards</a> to check in motorcycles or cars, record odometer &amp; fuel level, log customer complaints, add labor &amp; stock parts, track customer approval, print the Job Card, and generate the final invoice on completion.</li>
          <li><strong>Returns &amp; Warranty Claims:</strong> Use <a href="#/returns">Returns &amp; Warranty</a> to look up original invoices for partial/full sale returns and refunds, or log and track customer warranty claims with automatic coverage expiry validation.</li>
          <li><strong>Stock Replenishment:</strong> Use <a href="#/purchases">Purchases &amp; Suppliers</a> to create Purchase Orders and receive goods, or use quick <em>+ Receive</em> in <a href="#/products">Parts &amp; Inventory</a>. Weighted-average cost is updated automatically.</li>
          <li><strong>End-of-Day Reconciliation:</strong> Review the <strong>Daily Summary</strong> from the Dashboard or Notifications menu, close your shift in <a href="#/shifts">Cash Shifts</a>, and create a database backup in <a href="#/backups">Backups</a>.</li>
        </ol>
      </div>

      <div class="card">
        <div class="card-head"><h3 class="card-title">Accounting, PWA &amp; Security Guarantees (v1.2.2)</h3></div>
        <ul style="line-height:1.7;padding-left:18px;margin:0">
          <li><strong>Integer Paisa Ledger:</strong> All monetary values are stored in integer paisa (<span class="mono">1 PKR = 100 paisa</span>) to eliminate floating-point rounding drift.</li>
          <li><strong>Traceable Stock Movements:</strong> Product stock quantities only change through recorded transactions (Purchases, POS Sales, Job Part Issues, Sale Returns, Void Restocks, or Audited Adjustments).</li>
          <li><strong>COGS Snapshot:</strong> When a part is sold, its current weighted-average cost is snapshotted onto the invoice line so historical gross profit reports remain accurate even when future purchase prices change.</li>
          <li><strong>Installable Progressive Web App (PWA):</strong> Click <strong>Install App</strong> in the top bar (or your browser's address bar) to install Auto Workshop POS as a standalone desktop or mobile application. Static shell assets are cached safely while live <span class="mono">/api/</span> data is never cached.</li>
          <li><strong>Role-Based Access Control:</strong> Enforced server-side across all API endpoints for <span class="mono">admin</span>, <span class="mono">manager</span>, <span class="mono">cashier</span>, and <span class="mono">mechanic</span> roles.</li>
        </ul>
      </div>
    </div>
  `;
}

export default {
  route: "help",
  title: "Help & Guide",
  load: async () => renderHelp,
};
