// Audit Log — structured table of administrative & financial events with before/after detail inspector.
import { api } from "../core/api.js";
import { badge, emptyState, esc, fmtDateTime, money, openModal } from "../core/ui.js";

function parseJsonSafe(raw) {
  if (!raw) return null;
  if (typeof raw === "object") return raw;
  try { return JSON.parse(raw); } catch { return { note: String(raw) }; }
}

function formatActionLabel(action) {
  if (!action) return "System Event";
  return action
    .replace(/[._]/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatEntityLabel(entityType, entityId) {
  if (!entityType && !entityId) return "—";
  const label = (entityType || "record").replace(/_/g, " ");
  return entityId ? `${label} #${entityId}` : label;
}

function formatFieldVal(key, val) {
  if (val === null || val === undefined || val === "") return "—";
  if (key.endsWith("_paisa") && typeof val === "number") return money(val);
  if (typeof val === "boolean") return val ? "Yes" : "No";
  if (typeof val === "object") return JSON.stringify(val);
  return String(val);
}

function summarizeAuditEntry(entry) {
  const nv = parseJsonSafe(entry.new_values) || {};
  const ov = parseJsonSafe(entry.old_values) || {};
  const act = entry.action || "";

  if (act === "auth.setup") return `Initialized administrator account (${nv.username || "admin"})`;
  if (act === "auth.login") return `User signed in`;
  if (act === "invoice.create") return `Issued invoice ${nv.invoice_number || ""} · Total ${nv.total_paisa != null ? money(nv.total_paisa) : ""}`.trim();
  if (act === "invoice.void") return `Voided invoice ${nv.invoice_number || ""} (${nv.reason || "void"})`;
  if (act === "invoice.payment") return `Recorded payment of ${nv.amount_paisa != null ? money(nv.amount_paisa) : ""} via ${nv.method || "cash"}`;
  if (act === "job.create") return `Opened job card ${nv.job_number || ""}`;
  if (act === "job.status") return `Changed job status from ${ov.status || "previous"} to ${nv.status || "new"}`;
  if (act === "customer.create") return `Created customer ${nv.name || ""} (${nv.code || ""})`.trim();
  if (act === "customer.update") return `Updated customer record ${nv.name || ""}`.trim();
  if (act === "vehicle.create") return `Registered vehicle ${nv.registration_no || ""}`.trim();
  if (act === "expense.create") return `Recorded expense ${nv.expense_number || ""} (${nv.amount_paisa != null ? money(nv.amount_paisa) : ""})`;
  if (act === "expense.update") return `Updated expense ${nv.expense_number || "#" + (entry.entity_id || "")}`;
  if (act === "expense.delete") return `Deleted expense ${ov.expense_number || "#" + (entry.entity_id || "")}`;
  if (act === "claim.create") return `Submitted warranty claim ${nv.claim_number || ""}`;
  if (act === "claim.update") return `Updated warranty claim (${nv.status || "updated"})`;
  if (act === "backup.create") return `Created database backup ${nv.filename || ""}`;
  if (act === "backup.restore") return `Restored database from ${nv.restored_from || "backup"}`;

  // Generic clean summary from keys without raw JSON syntax
  const keys = Object.keys(nv);
  if (!keys.length) return formatActionLabel(act);
  const parts = [];
  for (const k of keys.slice(0, 3)) {
    const label = k.replace(/_paisa$/, "").replace(/_/g, " ");
    parts.push(`${label}: ${formatFieldVal(k, nv[k])}`);
  }
  return parts.join(" · ");
}

function openAuditDetailModal(entry) {
  const ov = parseJsonSafe(entry.old_values) || {};
  const nv = parseJsonSafe(entry.new_values) || {};
  const allKeys = Array.from(new Set([...Object.keys(ov), ...Object.keys(nv)]));

  openModal({
    title: `Audit Event #${entry.id} — ${formatActionLabel(entry.action)}`,
    size: "lg",
    body: `
      <div class="kpi-grid">
        <div class="kpi">
          <div class="k-label">Date &amp; Time</div>
          <div class="k-value" style="font-size:14px">${fmtDateTime(entry.created_at)}</div>
        </div>
        <div class="kpi">
          <div class="k-label">User</div>
          <div class="k-value" style="font-size:14px">${esc(entry.username || "system")}</div>
        </div>
        <div class="kpi">
          <div class="k-label">Action</div>
          <div class="k-value" style="font-size:14px">${esc(formatActionLabel(entry.action))}</div>
        </div>
        <div class="kpi">
          <div class="k-label">Affected Record</div>
          <div class="k-value" style="font-size:14px">${esc(formatEntityLabel(entry.entity_type, entry.entity_id))}</div>
        </div>
      </div>

      <div class="card" style="padding:12px;margin-bottom:12px">
        <div class="muted" style="font-size:11px;text-transform:uppercase;font-weight:600">Summary</div>
        <div style="font-size:13.5px;margin-top:4px">${esc(summarizeAuditEntry(entry))}</div>
      </div>

      <h4 style="margin:12px 0 6px">Recorded Field Values</h4>
      ${allKeys.length === 0 ? `<div class="muted">No additional field changes recorded for this event.</div>` : `
      <div class="table-wrap">
        <table class="tbl">
          <thead><tr><th>Field</th><th>Previous Value</th><th>Recorded / New Value</th></tr></thead>
          <tbody>
            ${allKeys.map(k => `
              <tr>
                <td class="mono muted">${esc(k.replace(/_/g, " "))}</td>
                <td>${esc(formatFieldVal(k, ov[k]))}</td>
                <td><strong>${esc(formatFieldVal(k, nv[k]))}</strong></td>
              </tr>`).join("")}
          </tbody>
        </table>
      </div>`}
    `,
  });
}

export async function renderAudit(root) {
  root.innerHTML = `
    <div class="toolbar">
      <input id="a-action" placeholder="Filter by action (e.g. invoice, job, expense)…" style="min-width:260px" />
      <input id="a-entity" placeholder="Filter by record type (e.g. customer, vehicle)…" style="min-width:220px" />
      <button class="btn btn-ghost btn-sm" id="a-filter">Filter</button>
    </div>
    <div class="card" id="a-list"></div>
  `;

  async function load() {
    const act = encodeURIComponent(root.querySelector("#a-action").value.trim());
    const ent = encodeURIComponent(root.querySelector("#a-entity").value.trim());
    const res = await api.get(`/api/audit?action=${act}&entity_type=${ent}&page_size=100`);
    const list = root.querySelector("#a-list");
    if (!res.items.length) { list.innerHTML = emptyState("No audit log entries match your filter"); return; }
    list.innerHTML = `
      <div class="table-wrap">
        <table class="tbl">
          <thead>
            <tr>
              <th>Date &amp; Time</th>
              <th>User</th>
              <th>Action</th>
              <th>Affected Record</th>
              <th>Summary</th>
              <th class="right">Additional Details</th>
            </tr>
          </thead>
          <tbody>
            ${res.items.map(a => `
              <tr>
                <td class="muted">${fmtDateTime(a.created_at)}</td>
                <td><strong>${esc(a.username || "system")}</strong></td>
                <td>${badge(a.action)}</td>
                <td class="mono muted">${esc(formatEntityLabel(a.entity_type, a.entity_id))}</td>
                <td>${esc(summarizeAuditEntry(a))}</td>
                <td class="right">
                  <button class="btn btn-ghost btn-sm" data-view="${a.id}">Details</button>
                </td>
              </tr>`).join("")}
          </tbody>
        </table>
      </div>`;
    list.querySelectorAll("[data-view]").forEach(btn => {
      btn.onclick = () => {
        const entry = res.items.find(x => x.id === Number(btn.dataset.view));
        if (entry) openAuditDetailModal(entry);
      };
    });
  }

  root.querySelector("#a-filter").onclick = load;
  root.querySelector("#a-action").onkeydown = (e) => { if (e.key === "Enter") load(); };
  root.querySelector("#a-entity").onkeydown = (e) => { if (e.key === "Enter") load(); };
  await load();
}

export default {
  route: "audit",
  title: "Audit Log",
  load: async () => renderAudit,
};
