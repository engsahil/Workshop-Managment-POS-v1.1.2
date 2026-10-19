// Workshop Service / Labor Catalog — labor charges never deduct stock.
import { api } from "../core/api.js";
import { badge, confirmDialog, emptyState, esc, formData, money, openModal, toast, toPaisa } from "../core/ui.js";

export async function renderServices(root) {
  root.innerHTML = `
    <div class="toolbar">
      <h2 style="margin:0;font-size:18px;font-weight:600">Workshop Labor &amp; Service Catalog</h2>
      <span class="spacer"></span>
      <button class="btn btn-primary" id="s-new">+ New Service</button>
    </div>
    <div class="card" id="s-list"></div>
  `;

  async function load() {
    const items = await api.get("/api/services?include_inactive=true");
    const list = root.querySelector("#s-list");
    if (!items.length) { list.innerHTML = emptyState("No services configured"); return; }
    list.innerHTML = `
      <div class="table-wrap">
        <table class="tbl">
          <thead><tr><th>Code</th><th>Service Name</th><th>Applicable To</th><th class="num">Est. Minutes</th><th class="num">Default Charge</th><th>Status</th><th></th></tr></thead>
          <tbody>
            ${items.map(s => `
              <tr>
                <td class="mono muted">${esc(s.code || "—")}</td>
                <td><strong>${esc(s.name)}</strong>${s.description ? `<div class="muted" style="font-size:11px">${esc(s.description)}</div>` : ""}</td>
                <td>${esc(s.vehicle_types)}</td>
                <td class="num">${s.estimated_minutes} min</td>
                <td class="num"><strong>${money(s.default_charge_paisa)}</strong></td>
                <td>${badge(s.is_active ? "active" : "cancelled")}</td>
                <td class="right">
                  <button class="btn btn-ghost btn-sm" data-edit="${s.id}">Edit</button>
                  <button class="btn btn-ghost btn-sm" data-del="${s.id}">Delete</button>
                </td>
              </tr>`).join("")}
          </tbody>
        </table>
      </div>`;
    list.querySelectorAll("[data-edit]").forEach(b => b.onclick = () => {
      const s = items.find(x => x.id === Number(b.dataset.edit));
      openEditor(s, load);
    });
    list.querySelectorAll("[data-del]").forEach(b => b.onclick = async () => {
      if (!await confirmDialog("Remove this service from catalog?")) return;
      await api.del(`/api/services/${b.dataset.del}`);
      toast("Removed"); load();
    });
  }

  root.querySelector("#s-new").onclick = () => openEditor(null, load);
  await load();
}

function openEditor(s, onDone) {
  const isNew = !s;
  const { close, root } = openModal({
    title: isNew ? "New Workshop Service" : `Edit ${s.name}`,
    body: `
      <form id="svc-f">
        <div class="form-row">
          <label><span>Service Name *</span><input name="name" required value="${esc(s?.name || "")}" /></label>
          <label><span>Code</span><input name="code" value="${esc(s?.code || "")}" placeholder="Auto if blank" /></label>
        </div>
        <div class="form-row">
          <label><span>Default Charge (PKR) *</span><input name="charge" type="number" step="0.01" min="0" required value="${((s?.default_charge_paisa || 0) / 100).toFixed(2)}" /></label>
          <label><span>Estimated Duration (min)</span><input name="estimated_minutes" type="number" min="0" value="${s?.estimated_minutes ?? 30}" /></label>
          <label><span>Vehicle Types</span>
            <select name="vehicle_types">
              ${["motorcycle,car", "motorcycle", "car"].map(v => `<option value="${v}" ${(s?.vehicle_types || "motorcycle,car") === v ? "selected" : ""}>${v}</option>`).join("")}
            </select>
          </label>
        </div>
        <label><span>Description</span><textarea name="description">${esc(s?.description || "")}</textarea></label>
        <div class="modal-foot">
          <button type="button" class="btn btn-ghost" data-close>Cancel</button>
          <button type="submit" class="btn btn-primary">${isNew ? "Create Service" : "Save"}</button>
        </div>
      </form>`,
  });
  root.querySelector("#svc-f").onsubmit = async (e) => {
    e.preventDefault();
    const fd = formData(e.target);
    const payload = {
      name: fd.name,
      code: fd.code || null,
      default_charge_paisa: toPaisa(fd.charge),
      estimated_minutes: Number(fd.estimated_minutes) || 0,
      vehicle_types: fd.vehicle_types,
      description: fd.description || null,
      is_active: true,
    };
    try {
      if (isNew) await api.post("/api/services", payload);
      else await api.put(`/api/services/${s.id}`, payload);
      toast("Service saved");
      close(); onDone();
    } catch (err) { toast(err.message, "err"); }
  };
}

export default {
  route: "services",
  title: "Services & Labor",
  load: async () => renderServices,
};
