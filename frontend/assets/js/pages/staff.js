// Mechanics & Workshop Staff — skills, job assignment counts, commission rules.
import { api, auth } from "../core/api.js";
import { badge, confirmDialog, emptyState, esc, formData, money, openModal, toast, toPaisa } from "../core/ui.js";

export async function renderStaff(root) {
  const canEdit = auth.hasRole("admin", "manager");
  root.innerHTML = `
    <div class="toolbar">
      <h2 style="margin:0;font-size:18px;font-weight:600">Mechanics &amp; Workshop Staff</h2>
      <span class="spacer"></span>
      ${canEdit ? `<button class="btn btn-primary" id="m-new">+ Add Mechanic</button>` : ""}
    </div>
    <div class="card" id="m-list"></div>
  `;

  async function load() {
    const items = await api.get("/api/mechanics?include_inactive=true");
    const list = root.querySelector("#m-list");
    if (!items.length) { list.innerHTML = emptyState("No mechanics registered"); return; }
    list.innerHTML = `
      <div class="table-wrap">
        <table class="tbl">
          <thead><tr><th>Name</th><th>Phone</th><th>Specialization</th><th>Commission Rule</th><th class="num">Total Jobs</th><th>Status</th><th></th></tr></thead>
          <tbody>
            ${items.map(m => {
              let comm = "None";
              if (m.commission_type === "percent_per_job") comm = `${(m.commission_value / 100).toFixed(1)}% of labor`;
              else if (m.commission_type === "fixed_per_job") comm = `${money(m.commission_value)} per completed job`;
              return `<tr>
                <td><strong>${esc(m.name)}</strong></td>
                <td>${esc(m.phone || "—")}</td>
                <td>${esc(m.skill || "General")}</td>
                <td>${comm}</td>
                <td class="num">${m.jobs_total || 0}</td>
                <td>${badge(m.is_active ? "active" : "cancelled")}</td>
                <td class="right">
                  ${canEdit ? `
                    <button class="btn btn-ghost btn-sm" data-edit="${m.id}">Edit</button>
                    <button class="btn btn-ghost btn-sm" data-del="${m.id}">Delete</button>` : ""}
                </td>
              </tr>`;
            }).join("")}
          </tbody>
        </table>
      </div>`;
    list.querySelectorAll("[data-edit]").forEach(b => b.onclick = () => {
      const m = items.find(x => x.id === Number(b.dataset.edit));
      openEditor(m, load);
    });
    list.querySelectorAll("[data-del]").forEach(b => b.onclick = async () => {
      if (!await confirmDialog("Delete this mechanic record?")) return;
      await api.del(`/api/mechanics/${b.dataset.del}`);
      toast("Removed"); load();
    });
  }

  const nb = root.querySelector("#m-new");
  if (nb) nb.onclick = () => openEditor(null, load);
  await load();
}

function openEditor(m, onDone) {
  const isNew = !m;
  const modal = openModal({
    title: isNew ? "Add Mechanic" : `Edit ${m.name}`,
    body: `
      <form id="m-form">
        <div class="form-row">
          <label><span>Full Name *</span><input name="name" required value="${esc(m?.name || "")}" /></label>
          <label><span>Phone</span><input name="phone" value="${esc(m?.phone || "")}" /></label>
        </div>
        <div class="form-row">
          <label><span>Skill / Specialization</span><input name="skill" value="${esc(m?.skill || "")}" placeholder="Motorcycle Engine / Car Electrical / Tuning" /></label>
          <label><span>Commission Rule</span>
            <select name="commission_type" id="mc-type">
              <option value="none" ${(m?.commission_type || "none") === "none" ? "selected" : ""}>None</option>
              <option value="percent_per_job" ${m?.commission_type === "percent_per_job" ? "selected" : ""}>Percentage of Labor (%)</option>
              <option value="fixed_per_job" ${m?.commission_type === "fixed_per_job" ? "selected" : ""}>Fixed PKR per Completed Job</option>
            </select>
          </label>
          <label><span>Commission Value (% or PKR)</span>
            <input name="comm_val" type="number" step="0.01" min="0" value="${m ? ((m.commission_value || 0) / 100).toFixed(2) : "0"}" />
          </label>
        </div>
        <label><span>Notes</span><textarea name="notes">${esc(m?.notes || "")}</textarea></label>
        <div class="modal-foot">
          <button type="button" class="btn btn-ghost" data-close>Cancel</button>
          <button type="submit" class="btn btn-primary">Save</button>
        </div>
      </form>`,
  });
  modal.root.querySelector("#m-form").onsubmit = async (e) => {
    e.preventDefault();
    const fd = formData(e.target);
    const payload = {
      name: fd.name,
      phone: fd.phone || null,
      skill: fd.skill || null,
      commission_type: fd.commission_type,
      commission_value: toPaisa(fd.comm_val),
      notes: fd.notes || null,
      is_active: true,
    };
    try {
      if (isNew) await api.post("/api/mechanics", payload);
      else await api.put(`/api/mechanics/${m.id}`, payload);
      toast("Mechanic saved");
      modal.close(); onDone();
    } catch (err) { toast(err.message, "err"); }
  };
}

export default {
  route: "staff",
  title: "Staff & Mechanics",
  load: async () => renderStaff,
};
