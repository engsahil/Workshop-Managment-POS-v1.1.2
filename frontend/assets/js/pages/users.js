// Users & Role-Based Access Control (Admin only).
import { api } from "../core/api.js";
import { badge, emptyState, esc, fmtDateTime, formData, openModal, toast } from "../core/ui.js";

export async function renderUsers(root) {
  const users = await api.get("/api/users");
  root.innerHTML = `
    <div class="toolbar">
      <h2 style="margin:0;font-size:18px;font-weight:600">User Accounts &amp; Role Permissions</h2>
      <span class="spacer"></span>
      <button class="btn btn-primary" id="u-new">+ New User Account</button>
    </div>
    <div class="card">
      ${!users.length ? emptyState("No users found") : `
      <div class="table-wrap">
        <table class="tbl">
          <thead><tr><th>Username</th><th>Full Name</th><th>Role</th><th>Phone / Email</th><th>Last Login</th><th>Status</th><th></th></tr></thead>
          <tbody>
            ${users.map(u => `
              <tr>
                <td class="mono"><strong>${esc(u.username)}</strong></td>
                <td>${esc(u.full_name)}</td>
                <td>${badge(u.role)}</td>
                <td class="muted">${esc([u.phone, u.email].filter(Boolean).join(" · ") || "—")}</td>
                <td class="muted">${fmtDateTime(u.last_login_at)}</td>
                <td>${badge(u.is_active ? "active" : "cancelled")}</td>
                <td class="right">
                  <button class="btn btn-ghost btn-sm" data-edit="${u.id}">Edit</button>
                  <button class="btn btn-ghost btn-sm" data-pw="${u.id}">Reset Password</button>
                </td>
              </tr>`).join("")}
          </tbody>
        </table>
      </div>`}
    </div>
  `;

  root.querySelector("#u-new").onclick = () => openEditor(null, () => renderUsers(root));
  root.querySelectorAll("[data-edit]").forEach(b => b.onclick = () => {
    const u = users.find(x => x.id === Number(b.dataset.edit));
    openEditor(u, () => renderUsers(root));
  });
  root.querySelectorAll("[data-pw]").forEach(b => b.onclick = () => {
    const u = users.find(x => x.id === Number(b.dataset.pw));
    const m = openModal({
      title: `Reset Password — ${u.username}`,
      body: `
        <form id="pw-f">
          <label><span>New Temporary Password (min 6 chars) *</span><input name="new_password" type="password" minlength="6" required /></label>
          <div class="modal-foot">
            <button type="button" class="btn btn-ghost" data-close>Cancel</button>
            <button type="submit" class="btn btn-primary">Reset Password</button>
          </div>
        </form>`,
    });
    m.root.querySelector("#pw-f").onsubmit = async (e) => {
      e.preventDefault();
      try {
        await api.post(`/api/auth/users/${u.id}/reset-password`, formData(e.target));
        toast("Password reset");
        m.close();
      } catch (err) { toast(err.message, "err"); }
    };
  });
}

function openEditor(u, onDone) {
  const isNew = !u;
  const m = openModal({
    title: isNew ? "New User Account" : `Edit ${u.username}`,
    body: `
      <form id="u-form">
        <div class="form-row">
          <label><span>Username *</span><input name="username" required minlength="2" value="${esc(u?.username || "")}" ${!isNew ? "disabled" : ""} /></label>
          <label><span>Full Name *</span><input name="full_name" required value="${esc(u?.full_name || "")}" /></label>
        </div>
        <div class="form-row">
          <label><span>Role *</span>
            <select name="role">
              ${["admin", "manager", "cashier", "mechanic"].map(r => `<option value="${r}" ${(u?.role || "cashier") === r ? "selected" : ""}>${r}</option>`).join("")}
            </select>
          </label>
          ${isNew ? `<label><span>Initial Password (min 6 chars) *</span><input name="password" type="password" minlength="6" required /></label>` : `
          <label style="display:flex;align-items:center;gap:8px;padding-top:22px">
            <input type="checkbox" name="is_active" style="width:auto" ${u.is_active ? "checked" : ""} />
            <span style="margin:0">Account Active</span>
          </label>`}
        </div>
        <div class="form-row">
          <label><span>Phone</span><input name="phone" value="${esc(u?.phone || "")}" /></label>
          <label><span>Email</span><input name="email" value="${esc(u?.email || "")}" /></label>
        </div>
        <div class="modal-foot">
          <button type="button" class="btn btn-ghost" data-close>Cancel</button>
          <button type="submit" class="btn btn-primary">${isNew ? "Create User" : "Save Changes"}</button>
        </div>
      </form>`,
  });
  m.root.querySelector("#u-form").onsubmit = async (e) => {
    e.preventDefault();
    const fd = formData(e.target);
    try {
      if (isNew) {
        await api.post("/api/users", {
          username: fd.username,
          full_name: fd.full_name,
          role: fd.role,
          password: fd.password,
          phone: fd.phone || null,
          email: fd.email || null,
        });
      } else {
        await api.put(`/api/users/${u.id}`, {
          full_name: fd.full_name,
          role: fd.role,
          phone: fd.phone || null,
          email: fd.email || null,
          is_active: !!fd.is_active,
        });
      }
      toast("User saved");
      m.close(); onDone();
    } catch (err) { toast(err.message, "err"); }
  };
}

export default {
  route: "users",
  title: "Users & Roles",
  load: async () => renderUsers,
};
