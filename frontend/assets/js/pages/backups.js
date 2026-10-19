// Backups & Restore — SQLite hot backup, upload & schema validation, safe pre-restore backup, and JSON export.
import { api, auth } from "../core/api.js";
import { confirmDialog, emptyState, esc, fmtDateTime, toast } from "../core/ui.js";

export async function renderBackups(root) {
  const res = await api.get("/api/backups");
  const items = res.items || [];

  root.innerHTML = `
    <div class="toolbar">
      <h2 style="margin:0;font-size:18px;font-weight:600">Database Backups &amp; Recovery</h2>
      <span class="spacer"></span>
      <button class="btn btn-ghost btn-sm" id="bk-json">Export Full JSON Snapshot</button>
      <button class="btn btn-primary" id="bk-create">+ Create Backup Now</button>
    </div>

    <div class="card mb-3">
      <div class="card-head">
        <div>
          <h3 class="card-title">Upload &amp; Validate External Backup (.db)</h3>
          <div class="card-sub">Upload a SQLite .db backup file to verify its integrity and required schema tables before restoring.</div>
        </div>
      </div>
      <div class="flex">
        <input type="file" id="bk-file" accept=".db,.sqlite,.sqlite3" style="max-width:340px" />
        <button class="btn btn-ghost btn-sm" id="bk-upload-val">Upload &amp; Validate</button>
        <button class="btn btn-danger btn-sm" id="bk-upload-rest" disabled>Restore Uploaded Backup</button>
      </div>
      <div class="muted mt-2" id="bk-upload-msg" style="font-size:12px"></div>
    </div>

    <div class="card">
      <div class="card-head">
        <div>
          <h3 class="card-title">Available Backups (data/backups/)</h3>
          <div class="card-sub">Every restore automatically creates a safety backup of the current database first.</div>
        </div>
      </div>
      ${!items.length ? emptyState("No backups created yet — click '+ Create Backup Now' to create your first backup") : `
      <div class="table-wrap">
        <table class="tbl">
          <thead><tr><th>Filename</th><th>Created</th><th class="num">Size</th><th></th></tr></thead>
          <tbody>
            ${items.map(b => `
              <tr>
                <td class="mono"><strong>${esc(b.filename)}</strong></td>
                <td class="muted">${fmtDateTime(b.created_at)}</td>
                <td class="num">${(b.size_bytes / 1024).toFixed(1)} KB</td>
                <td class="right">
                  <button class="btn btn-ghost btn-sm" data-val="${esc(b.filename)}">Validate</button>
                  <button class="btn btn-ghost btn-sm" data-dl="${esc(b.filename)}">Download</button>
                  <button class="btn btn-danger btn-sm" data-rest="${esc(b.filename)}">Restore</button>
                </td>
              </tr>`).join("")}
          </tbody>
        </table>
      </div>`}
    </div>
  `;

  let uploadedFilename = null;
  const fileEl = root.querySelector("#bk-file");
  const msgEl = root.querySelector("#bk-upload-msg");
  const restUpBtn = root.querySelector("#bk-upload-rest");

  fileEl.onchange = () => {
    uploadedFilename = null;
    restUpBtn.disabled = true;
    msgEl.textContent = fileEl.files[0] ? `Selected file: ${fileEl.files[0].name}` : "";
  };

  root.querySelector("#bk-upload-val").onclick = async () => {
    const f = fileEl.files[0];
    if (!f) { toast("Select a .db backup file first", "warn"); return; }
    const fd = new FormData();
    fd.append("file", f);
    try {
      const r = await api.post("/api/backups/upload", fd);
      uploadedFilename = r.filename;
      restUpBtn.disabled = false;
      msgEl.textContent = `Uploaded as ${r.filename} — Integrity OK (${r.validation?.tables || 0} tables verified).`;
      toast("Backup uploaded and validated");
    } catch (e) {
      msgEl.textContent = `Validation failed: ${e.message}`;
      toast(e.message, "err");
    }
  };

  restUpBtn.onclick = async () => {
    if (!uploadedFilename) return;
    if (!await confirmDialog(`Restore '${uploadedFilename}'? Current database will be backed up first and replaced.`)) return;
    try {
      const r = await api.post(`/api/backups/${encodeURIComponent(uploadedFilename)}/restore`, {});
      toast(`Restored (safety backup: ${r.pre_restore_backup})`);
      renderBackups(root);
    } catch (e) { toast(e.message, "err"); }
  };

  root.querySelector("#bk-create").onclick = async () => {
    try {
      const r = await api.post("/api/backups", {});
      toast(`Backup created: ${r.filename}`);
      renderBackups(root);
    } catch (e) { toast(e.message, "err"); }
  };

  root.querySelector("#bk-json").onclick = async () => {
    try {
      const data = await api.get("/api/export");
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `auto_workshop_export_${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) { toast(e.message, "err"); }
  };

  root.querySelectorAll("[data-val]").forEach(b => b.onclick = async () => {
    try {
      const r = await api.post(`/api/backups/validate?filename=${encodeURIComponent(b.dataset.val)}`);
      toast(`Valid SQLite backup (${r.tables} tables, integrity OK)`);
    } catch (e) { toast(e.message, "err"); }
  });

  root.querySelectorAll("[data-dl]").forEach(b => b.onclick = async () => {
    const fn = b.dataset.dl;
    const res = await fetch(`/api/backups/${encodeURIComponent(fn)}/download`, {
      headers: { Authorization: `Bearer ${auth.token}` },
    });
    if (!res.ok) { toast("Download failed", "err"); return; }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = fn; a.click();
    URL.revokeObjectURL(url);
  });

  root.querySelectorAll("[data-rest]").forEach(b => b.onclick = async () => {
    const fn = b.dataset.rest;
    if (!await confirmDialog(`Restore backup ${fn}? Current database will be backed up first and replaced.`)) return;
    try {
      const r = await api.post(`/api/backups/${encodeURIComponent(fn)}/restore`);
      toast(`Restored (safety backup: ${r.pre_restore_backup})`);
      renderBackups(root);
    } catch (e) { toast(e.message, "err"); }
  });
}

export default {
  route: "backups",
  title: "Backup & Restore",
  load: async () => renderBackups,
};
