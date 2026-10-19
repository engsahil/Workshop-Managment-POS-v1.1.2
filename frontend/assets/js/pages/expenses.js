// Expenses — categories, expense recording, daily/monthly summaries, CSV export, and attachments.
import { api } from "../core/api.js";
import { badge, confirmDialog, downloadCSV, emptyState, esc, fmtDate, formData, money, openModal, todayISO, toast, toPaisa } from "../core/ui.js";

export async function renderExpenses(root) {
  const cats = await api.get("/api/expense-categories");
  root.innerHTML = `
    <div class="toolbar">
      <input id="e-q" placeholder="Search payee, description, reference…" />
      <select id="e-cat">
        <option value="">All categories</option>
        ${cats.map(c => `<option value="${c.id}">${esc(c.name)}</option>`).join("")}
      </select>
      <select id="e-method">
        <option value="">All methods</option>
        <option value="cash">Cash</option>
        <option value="bank_transfer">Bank Transfer</option>
        <option value="card">Card</option>
        <option value="jazzcash">JazzCash</option>
        <option value="easypaisa">Easypaisa</option>
      </select>
      <input type="date" id="e-from" />
      <input type="date" id="e-to" />
      <button class="btn btn-ghost btn-sm" id="e-filter">Filter</button>
      <span class="spacer"></span>
      <button class="btn btn-ghost btn-sm" id="e-export">Export CSV</button>
      <button class="btn btn-ghost btn-sm" id="e-newcat">+ Category</button>
      <button class="btn btn-primary" id="e-new">+ Record Expense</button>
    </div>
    <div class="kpi-grid" id="e-kpis"></div>
    <div class="card" id="e-list"></div>
  `;

  let lastItems = [];

  async function load() {
    const q = encodeURIComponent(root.querySelector("#e-q").value.trim());
    const cat = root.querySelector("#e-cat").value;
    const method = root.querySelector("#e-method").value;
    const df = root.querySelector("#e-from").value;
    const dt = root.querySelector("#e-to").value;
    const res = await api.get(`/api/expenses?q=${q}${cat ? `&category_id=${cat}` : ""}${method ? `&method=${method}` : ""}${df ? `&date_from=${df}` : ""}${dt ? `&date_to=${dt}` : ""}&page_size=100`);
    lastItems = res.items || [];
    const sum = res.summary || {
      filtered_total_paisa: lastItems.reduce((a, b) => a + b.amount_paisa, 0),
      today_total_paisa: 0,
      month_total_paisa: 0,
    };

    root.querySelector("#e-kpis").innerHTML = `
      <div class="kpi">
        <div class="k-label">Today's Expenses</div>
        <div class="k-value">${money(sum.today_total_paisa)}</div>
      </div>
      <div class="kpi">
        <div class="k-label">Current Month Expenses</div>
        <div class="k-value">${money(sum.month_total_paisa)}</div>
      </div>
      <div class="kpi warn">
        <div class="k-label">Filtered Total (${res.total || lastItems.length} record(s))</div>
        <div class="k-value">${money(sum.filtered_total_paisa)}</div>
      </div>
    `;

    const list = root.querySelector("#e-list");
    if (!lastItems.length) {
      list.innerHTML = emptyState("No expenses recorded for this filter");
      return;
    }
    list.innerHTML = `
      <div class="table-wrap">
        <table class="tbl">
          <thead><tr><th>Expense #</th><th>Date</th><th>Category</th><th>Payee</th><th>Description</th><th>Method</th><th class="num">Amount</th><th></th></tr></thead>
          <tbody>
            ${lastItems.map(e => `
              <tr>
                <td class="mono">${esc(e.expense_number)}</td>
                <td class="muted">${fmtDate(e.expense_date)}</td>
                <td>${esc(e.category_name || "—")}</td>
                <td>${esc(e.payee || "—")}</td>
                <td>${esc(e.description || "—")}${e.attachment_path ? ` · <a href="/api/files/${esc(e.attachment_path)}" target="_blank">Attachment</a>` : ""}</td>
                <td>${badge(e.method)}</td>
                <td class="num"><strong>${money(e.amount_paisa)}</strong></td>
                <td class="right">
                  <button class="btn btn-ghost btn-sm" data-edit="${e.id}">Edit</button>
                  <button class="btn btn-ghost btn-sm" data-del="${e.id}">Delete</button>
                </td>
              </tr>`).join("")}
          </tbody>
        </table>
      </div>`;
    list.querySelectorAll("[data-edit]").forEach(b => b.onclick = () => {
      const e = lastItems.find(x => x.id === Number(b.dataset.edit));
      openEditor(e, cats, load);
    });
    list.querySelectorAll("[data-del]").forEach(b => b.onclick = async () => {
      if (!await confirmDialog("Delete this expense entry?")) return;
      await api.del(`/api/expenses/${b.dataset.del}`);
      toast("Expense deleted");
      load();
    });
  }

  root.querySelector("#e-filter").onclick = load;
  root.querySelector("#e-q").onkeydown = (e) => { if (e.key === "Enter") load(); };
  root.querySelector("#e-cat").onchange = load;
  root.querySelector("#e-method").onchange = load;
  root.querySelector("#e-export").onclick = () => {
    downloadCSV("expenses.csv", lastItems.map(e => ({
      expense_number: e.expense_number,
      date: (e.expense_date || "").slice(0, 10),
      category: e.category_name || "",
      payee: e.payee || "",
      description: e.description || "",
      method: e.method,
      amount_pkr: (e.amount_paisa / 100).toFixed(2),
    })));
  };
  root.querySelector("#e-new").onclick = () => openEditor(null, cats, load);
  root.querySelector("#e-newcat").onclick = () => {
    const m = openModal({
      title: "New Expense Category",
      body: `<form id="ec-f"><label><span>Category Name *</span><input name="name" required /></label>
        <div class="modal-foot"><button type="button" class="btn btn-ghost" data-close>Cancel</button><button class="btn btn-primary">Create</button></div></form>`,
    });
    m.root.querySelector("#ec-f").onsubmit = async (e) => {
      e.preventDefault();
      try {
        await api.post("/api/expense-categories", formData(e.target));
        toast("Category added");
        m.close();
        renderExpenses(root);
      } catch (err) { toast(err.message, "err"); }
    };
  };

  await load();
}

function openEditor(exp, cats, onDone) {
  const isNew = !exp;
  const m = openModal({
    title: isNew ? "Record Expense" : `Edit ${exp.expense_number}`,
    body: `
      <form id="exp-form">
        <div class="form-row">
          <label><span>Category *</span>
            <select name="category_id" required>
              ${cats.map(c => `<option value="${c.id}" ${exp?.category_id === c.id ? "selected" : ""}>${esc(c.name)}</option>`).join("")}
            </select>
          </label>
          <label><span>Amount (PKR) *</span><input name="amount" type="number" step="0.01" min="1" required value="${exp ? (exp.amount_paisa / 100).toFixed(2) : ""}" /></label>
          <label><span>Date</span><input name="expense_date" type="date" value="${exp?.expense_date ? exp.expense_date.slice(0, 10) : todayISO()}" /></label>
        </div>
        <div class="form-row">
          <label><span>Method</span>
            <select name="method">
              ${["cash", "bank_transfer", "card", "jazzcash", "easypaisa", "other"].map(x => `<option value="${x}" ${(exp?.method || "cash") === x ? "selected" : ""}>${x.replace("_", " ")}</option>`).join("")}
            </select>
          </label>
          <label><span>Payee / Vendor</span><input name="payee" value="${esc(exp?.payee || "")}" /></label>
          <label><span>Reference</span><input name="reference" value="${esc(exp?.reference || "")}" /></label>
        </div>
        <label><span>Description</span><input name="description" value="${esc(exp?.description || "")}" /></label>
        <label><span>Receipt Attachment (Image or PDF)</span><input type="file" id="exp-file" accept="image/*,.pdf" /></label>
        <div class="modal-foot">
          <button type="button" class="btn btn-ghost" data-close>Cancel</button>
          <button type="submit" class="btn btn-primary" id="exp-save-btn">${isNew ? "Save Expense" : "Update"}</button>
        </div>
      </form>`,
  });
  m.root.querySelector("#exp-form").onsubmit = async (e) => {
    e.preventDefault();
    const saveBtn = m.root.querySelector("#exp-save-btn");
    saveBtn.disabled = true;
    const fd = formData(e.target);
    let attachment_path = exp?.attachment_path || null;
    const fileInput = m.root.querySelector("#exp-file");
    try {
      if (fileInput.files.length) {
        const up = new FormData();
        up.append("file", fileInput.files[0]);
        const r = await api.post("/api/uploads/expense", up);
        attachment_path = r.attachment_path;
      }
      const payload = {
        category_id: Number(fd.category_id),
        amount_paisa: toPaisa(fd.amount),
        expense_date: fd.expense_date || null,
        method: fd.method,
        payee: fd.payee || null,
        reference: fd.reference || null,
        description: fd.description || null,
        attachment_path,
      };
      if (isNew) await api.post("/api/expenses", payload);
      else await api.put(`/api/expenses/${exp.id}`, payload);
      toast(isNew ? "Expense recorded" : "Expense updated");
      m.close();
      onDone();
    } catch (err) {
      toast(err.message, "err");
      saveBtn.disabled = false;
    }
  };
}
