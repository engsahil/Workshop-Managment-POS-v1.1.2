// Products & Inventory — parts catalog, stock receiving, adjustments, movement ledger, categories & brands, CSV import/export.
import { api } from "../core/api.js";
import { badge, confirmDialog, emptyState, esc, fmtDateTime, formData, money, openModal, toast, toPaisa } from "../core/ui.js";

export async function renderProducts(root, params = {}) {
  root.innerHTML = `
    <div class="tabs">
      <div class="tab active" data-t="catalog">Parts &amp; Stock (${params.low ? "Low Stock" : "All"})</div>
      <div class="tab" data-t="movements">Stock Movements Ledger</div>
      <div class="tab" data-t="taxonomy">Categories &amp; Brands</div>
    </div>
    <div id="prod-body"></div>
  `;
  const body = root.querySelector("#prod-body");
  root.querySelectorAll(".tab").forEach(t => {
    t.onclick = () => {
      root.querySelectorAll(".tab").forEach(x => x.classList.remove("active"));
      t.classList.add("active");
      const tab = t.dataset.t;
      if (tab === "catalog") renderCatalog(body, params);
      else if (tab === "movements") renderMovements(body);
      else renderTaxonomy(body);
    };
  });
  await renderCatalog(body, params);
}

async function renderCatalog(box, params) {
  const [cats, brands, sups] = await Promise.all([
    api.get("/api/categories"),
    api.get("/api/brands"),
    api.get("/api/suppliers"),
  ]);

  box.innerHTML = `
    <div class="toolbar">
      <input id="p-q" placeholder="Search name, SKU, barcode, compatibility…" style="min-width:250px" />
      <select id="p-cat">
        <option value="">All categories</option>
        ${cats.map(c => `<option value="${c.id}">${esc(c.name)}</option>`).join("")}
      </select>
      <label style="display:flex;align-items:center;gap:6px;margin:0">
        <input type="checkbox" id="p-low" style="width:auto" ${params.low ? "checked" : ""} />
        <span style="margin:0">Low stock only</span>
      </label>
      <button class="btn btn-ghost btn-sm" id="p-filter">Filter</button>
      <span class="spacer"></span>
      <a class="btn btn-ghost btn-sm" href="/api/products/export/csv" target="_blank">Export CSV</a>
      <button class="btn btn-ghost btn-sm" id="p-import">Import CSV</button>
      <button class="btn btn-primary" id="p-new">+ New Part / Product</button>
    </div>
    <div class="card" id="p-list"></div>
  `;

  async function load() {
    const q = encodeURIComponent(box.querySelector("#p-q").value.trim());
    const cat = box.querySelector("#p-cat").value;
    const low = box.querySelector("#p-low").checked;
    const url = `/api/products?q=${q}${cat ? `&category_id=${cat}` : ""}${low ? "&low_stock=true" : ""}&include_services=false&page_size=100`;
    const res = await api.get(url);
    const list = box.querySelector("#p-list");
    if (!res.items.length) { list.innerHTML = emptyState("No products found"); return; }
    list.innerHTML = `
      <div class="table-wrap">
        <table class="tbl">
          <thead>
            <tr>
              <th>SKU</th><th>Part Name</th><th>Compatibility</th>
              <th class="num">Cost</th><th class="num">Avg Cost</th><th class="num">Sell Price</th>
              <th class="num">On Hand</th><th>Status</th><th></th>
            </tr>
          </thead>
          <tbody>
            ${res.items.map(p => {
              const st = p.quantity_on_hand <= 0 ? "out" : p.low_stock ? "low" : "ok";
              return `<tr>
                <td class="mono muted">${esc(p.sku || "—")}</td>
                <td><strong>${esc(p.name)}</strong>${p.barcode ? `<div class="mono muted" style="font-size:11px">${esc(p.barcode)}</div>` : ""}</td>
                <td class="muted">${esc(p.compatibility || "—")}</td>
                <td class="num">${money(p.purchase_cost_paisa)}</td>
                <td class="num muted">${money(p.avg_cost_paisa)}</td>
                <td class="num"><strong>${money(p.selling_price_paisa)}</strong></td>
                <td class="num">${p.quantity_on_hand} ${esc(p.unit)} <span class="muted">(min ${p.min_stock})</span></td>
                <td>${badge(st)}</td>
                <td class="right">
                  <button class="btn btn-ghost btn-sm" data-rcv="${p.id}">+ Receive</button>
                  <button class="btn btn-ghost btn-sm" data-adj="${p.id}">Adjust</button>
                  <button class="btn btn-ghost btn-sm" data-edit="${p.id}">Edit</button>
                </td>
              </tr>`;
            }).join("")}
          </tbody>
        </table>
      </div>`;
    list.querySelectorAll("[data-edit]").forEach(b => b.onclick = () => {
      const p = res.items.find(x => x.id === Number(b.dataset.edit));
      openProductEditor(p, cats, brands, sups, load);
    });
    list.querySelectorAll("[data-rcv]").forEach(b => b.onclick = () => {
      const p = res.items.find(x => x.id === Number(b.dataset.rcv));
      openReceiveModal(p, load);
    });
    list.querySelectorAll("[data-adj]").forEach(b => b.onclick = () => {
      const p = res.items.find(x => x.id === Number(b.dataset.adj));
      openAdjustModal(p, load);
    });
  }

  box.querySelector("#p-filter").onclick = load;
  box.querySelector("#p-q").onkeydown = (e) => { if (e.key === "Enter") load(); };
  box.querySelector("#p-cat").onchange = load;
  box.querySelector("#p-low").onchange = load;
  box.querySelector("#p-new").onclick = () => openProductEditor(null, cats, brands, sups, load);
  box.querySelector("#p-import").onclick = () => {
    const m = openModal({
      title: "Import Products CSV",
      body: `
        <form id="csv-form">
          <p class="muted">Upload a UTF-8 CSV with columns: <span class="mono">name, sku, barcode, compatibility, purchase_cost_pkr, selling_price_pkr, min_stock, unit</span></p>
          <input type="file" name="file" accept=".csv" required />
          <div class="modal-foot">
            <button type="button" class="btn btn-ghost" data-close>Cancel</button>
            <button type="submit" class="btn btn-primary">Upload &amp; Import</button>
          </div>
        </form>`,
    });
    m.root.querySelector("#csv-form").onsubmit = async (e) => {
      e.preventDefault();
      const fd = new FormData(e.target);
      try {
        const res = await api.post("/api/products/import/csv", fd);
        toast(`Imported: ${res.created} created, ${res.updated} updated`);
        m.close(); load();
      } catch (err) { toast(err.message, "err"); }
    };
  };

  await load();
}

function openProductEditor(p, cats, brands, sups, onDone) {
  const isNew = !p;
  const { close, root } = openModal({
    title: isNew ? "New Spare Part / Product" : `Edit ${p.name}`,
    size: "lg",
    body: `
      <form id="prod-form">
        <div class="form-row">
          <label><span>Part Name *</span><input name="name" required value="${esc(p?.name || "")}" /></label>
          <label><span>SKU / Part Code</span><input name="sku" value="${esc(p?.sku || "")}" placeholder="Auto if blank" /></label>
          <label><span>Barcode</span><input name="barcode" value="${esc(p?.barcode || "")}" /></label>
        </div>
        <div class="form-row">
          <label><span>Category</span>
            <select name="category_id"><option value="">—</option>${cats.map(c => `<option value="${c.id}" ${p?.category_id === c.id ? "selected" : ""}>${esc(c.name)}</option>`).join("")}</select>
          </label>
          <label><span>Brand</span>
            <select name="brand_id"><option value="">—</option>${brands.map(b => `<option value="${b.id}" ${p?.brand_id === b.id ? "selected" : ""}>${esc(b.name)}</option>`).join("")}</select>
          </label>
          <label><span>Preferred Supplier</span>
            <select name="supplier_id"><option value="">—</option>${sups.map(s => `<option value="${s.id}" ${p?.supplier_id === s.id ? "selected" : ""}>${esc(s.name)}</option>`).join("")}</select>
          </label>
        </div>
        <div class="form-row">
          <label><span>Purchase Cost (PKR) *</span><input name="purchase_cost" type="number" step="0.01" min="0" required value="${((p?.purchase_cost_paisa || 0) / 100).toFixed(2)}" /></label>
          <label><span>Selling Price (PKR) *</span><input name="selling_price" type="number" step="0.01" min="0" required value="${((p?.selling_price_paisa || 0) / 100).toFixed(2)}" /></label>
          <label><span>Unit</span><input name="unit" value="${esc(p?.unit || "pcs")}" /></label>
        </div>
        <div class="form-row">
          <label><span>Min Stock Alert Level</span><input name="min_stock" type="number" min="0" value="${p?.min_stock ?? 5}" /></label>
          <label><span>Warranty (days)</span><input name="warranty_days" type="number" min="0" value="${p?.warranty_days ?? 0}" /></label>
          <label><span>Vehicle Compatibility</span><input name="compatibility" value="${esc(p?.compatibility || "")}" placeholder="CG125 / CD70 / Corolla…" /></label>
        </div>
        <label><span>Description</span><textarea name="description">${esc(p?.description || "")}</textarea></label>
        <div class="modal-foot">
          <button type="button" class="btn btn-ghost" data-close>Cancel</button>
          <button type="submit" class="btn btn-primary">${isNew ? "Create Product" : "Save Changes"}</button>
        </div>
      </form>`,
  });
  root.querySelector("#prod-form").onsubmit = async (e) => {
    e.preventDefault();
    const fd = formData(e.target);
    const payload = {
      name: fd.name,
      sku: fd.sku || null,
      barcode: fd.barcode || null,
      category_id: fd.category_id ? Number(fd.category_id) : null,
      brand_id: fd.brand_id ? Number(fd.brand_id) : null,
      supplier_id: fd.supplier_id ? Number(fd.supplier_id) : null,
      purchase_cost_paisa: toPaisa(fd.purchase_cost),
      selling_price_paisa: toPaisa(fd.selling_price),
      unit: fd.unit || "pcs",
      min_stock: Number(fd.min_stock) || 0,
      warranty_days: Number(fd.warranty_days) || 0,
      compatibility: fd.compatibility || null,
      description: fd.description || null,
      is_service: false,
      is_active: true,
    };
    try {
      if (isNew) await api.post("/api/products", payload);
      else await api.put(`/api/products/${p.id}`, payload);
      toast(isNew ? "Product created" : "Product updated");
      close(); onDone();
    } catch (err) { toast(err.message, "err"); }
  };
}

function openReceiveModal(p, onDone) {
  const m = openModal({
    title: `Receive Stock — ${p.name}`,
    body: `
      <form id="rcv-f">
        <div class="form-row">
          <label><span>Quantity Received *</span><input name="quantity" type="number" min="1" required value="1" /></label>
          <label><span>Unit Cost (PKR) *</span><input name="unit_cost" type="number" step="0.01" min="0" required value="${(p.purchase_cost_paisa / 100).toFixed(2)}" /></label>
        </div>
        <label><span>Reference / Supplier Bill #</span><input name="reference_number" /></label>
        <label><span>Notes</span><input name="notes" /></label>
        <div class="modal-foot">
          <button type="button" class="btn btn-ghost" data-close>Cancel</button>
          <button type="submit" class="btn btn-primary">Receive into Stock</button>
        </div>
      </form>`,
  });
  m.root.querySelector("#rcv-f").onsubmit = async (e) => {
    e.preventDefault();
    const fd = formData(e.target);
    try {
      await api.post("/api/inventory/receive", {
        product_id: p.id,
        quantity: Number(fd.quantity),
        unit_cost_paisa: toPaisa(fd.unit_cost),
        reference_number: fd.reference_number || null,
        notes: fd.notes || null,
      });
      toast("Stock received & weighted average cost updated");
      m.close(); onDone();
    } catch (err) { toast(err.message, "err"); }
  };
}

function openAdjustModal(p, onDone) {
  const m = openModal({
    title: `Stock Adjustment — ${p.name} (On hand: ${p.quantity_on_hand})`,
    body: `
      <form id="adj-f">
        <div class="form-row">
          <label><span>Change (+/-) *</span><input name="delta" type="number" required placeholder="-2 or +5" /></label>
          <label><span>Movement Type</span>
            <select name="movement_type">
              <option value="adjust">Stock Count Adjustment</option>
              <option value="damage">Damaged / Write-off</option>
            </select>
          </label>
        </div>
        <label><span>Reason *</span><input name="reason" required minlength="2" placeholder="Physical count variance, damaged in bay…" /></label>
        <div class="modal-foot">
          <button type="button" class="btn btn-ghost" data-close>Cancel</button>
          <button type="submit" class="btn btn-primary">Record Adjustment</button>
        </div>
      </form>`,
  });
  m.root.querySelector("#adj-f").onsubmit = async (e) => {
    e.preventDefault();
    const fd = formData(e.target);
    try {
      await api.post("/api/inventory/adjust", {
        product_id: p.id,
        delta: Number(fd.delta),
        movement_type: fd.movement_type,
        reason: fd.reason,
      });
      toast("Stock adjusted");
      m.close(); onDone();
    } catch (err) { toast(err.message, "err"); }
  };
}

async function renderMovements(box) {
  const res = await api.get("/api/inventory/movements?page_size=100");
  box.innerHTML = `
    <div class="card">
      <div class="card-head"><h3 class="card-title">Stock Movement Audit Trail</h3></div>
      ${!res.items.length ? emptyState("No stock movements yet") : `
      <div class="table-wrap">
        <table class="tbl">
          <thead><tr><th>Date</th><th>Part</th><th>Type</th><th class="num">Delta</th><th class="num">After</th><th class="num">Unit Cost</th><th>Reference</th><th>Notes</th></tr></thead>
          <tbody>
            ${res.items.map(m => `
              <tr>
                <td class="muted">${fmtDateTime(m.created_at)}</td>
                <td>${esc(m.product_name || "")} <span class="mono muted">${esc(m.sku || "")}</span></td>
                <td>${badge(m.movement_type)}</td>
                <td class="num"><strong>${m.quantity_delta > 0 ? "+" + m.quantity_delta : m.quantity_delta}</strong></td>
                <td class="num">${m.quantity_after}</td>
                <td class="num">${money(m.unit_cost_paisa)}</td>
                <td class="mono muted">${esc(m.reference_number || m.reference_type || "—")}</td>
                <td class="muted">${esc(m.notes || "—")}</td>
              </tr>`).join("")}
          </tbody>
        </table>
      </div>`}
    </div>`;
}

async function renderTaxonomy(box) {
  const [cats, brands] = await Promise.all([api.get("/api/categories"), api.get("/api/brands")]);
  box.innerHTML = `
    <div class="grid-2">
      <div class="card">
        <div class="card-head"><h3 class="card-title">Product Categories</h3></div>
        <form id="cat-add" class="flex mb-2">
          <input name="name" placeholder="New category name…" required />
          <button class="btn btn-primary btn-sm">+ Add</button>
        </form>
        <div class="table-wrap">
          <table class="tbl">
            <tbody>
              ${cats.map(c => `<tr><td>${esc(c.name)}</td><td class="right"><button class="btn btn-ghost btn-sm" data-delcat="${c.id}">Delete</button></td></tr>`).join("")}
            </tbody>
          </table>
        </div>
      </div>
      <div class="card">
        <div class="card-head"><h3 class="card-title">Brands</h3></div>
        <form id="br-add" class="flex mb-2">
          <input name="name" placeholder="New brand name…" required />
          <button class="btn btn-primary btn-sm">+ Add</button>
        </form>
        <div class="table-wrap">
          <table class="tbl">
            <tbody>
              ${brands.map(b => `<tr><td>${esc(b.name)}</td><td class="right"><button class="btn btn-ghost btn-sm" data-delbr="${b.id}">Delete</button></td></tr>`).join("")}
            </tbody>
          </table>
        </div>
      </div>
    </div>`;
  box.querySelector("#cat-add").onsubmit = async (e) => {
    e.preventDefault();
    await api.post("/api/categories", formData(e.target));
    renderTaxonomy(box);
  };
  box.querySelector("#br-add").onsubmit = async (e) => {
    e.preventDefault();
    await api.post("/api/brands", formData(e.target));
    renderTaxonomy(box);
  };
  box.querySelectorAll("[data-delcat]").forEach(b => b.onclick = async () => {
    try { await api.del(`/api/categories/${b.dataset.delcat}`); renderTaxonomy(box); }
    catch (e) { toast(e.message, "err"); }
  });
  box.querySelectorAll("[data-delbr]").forEach(b => b.onclick = async () => {
    try { await api.del(`/api/brands/${b.dataset.delbr}`); renderTaxonomy(box); }
    catch (e) { toast(e.message, "err"); }
  });
}

export default {
  route: "products",
  title: "Parts & Inventory",
  load: async () => renderProducts,
};
