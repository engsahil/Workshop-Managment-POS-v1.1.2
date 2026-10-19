// POS Billing — fast parts + services counter billing, split payments, credit & receipt print.
import { api, auth } from "../core/api.js";
import { appState, refreshHeaderContext } from "../core/app.js";
import { emptyState, esc, fmtDateTime, money, openModal, printDocument, toast, toPaisa } from "../core/ui.js";
import { openQuickCustomerModal } from "./customers.js";
import { openQuickVehicleModal } from "./vehicles.js";

const HOLD_KEY = "awp_pos_held_carts";

export async function renderPOS(root) {
  const [cat, custs, vehs] = await Promise.all([
    api.get("/api/pos/search?q="),
    api.get("/api/customers?page_size=200"),
    api.get("/api/vehicles?page_size=200"),
  ]);
  let customers = custs.items || [];
  let vehicles = vehs.items || [];

  const state = {
    cart: [],
    customer_id: "",
    vehicle_id: "",
    invoice_discount: 0,
    payments: [{ method: "cash", amount: "" }],
    notes: "",
    tab: "products",
    catalog: cat,
  };

  root.innerHTML = `
    <div class="pos-grid">
      <!-- Left: catalog search & tiles -->
      <div class="card">
        <div class="toolbar">
          <input id="pos-q" placeholder="Scan barcode / SKU or type item name…" style="flex:1" autofocus />
          <button class="btn btn-ghost btn-sm" data-tab="products">Parts (${cat.products.length})</button>
          <button class="btn btn-ghost btn-sm" data-tab="services">Services (${cat.services.length})</button>
        </div>
        <div id="pos-tiles" class="catalog-grid"></div>
      </div>

      <!-- Right: cart & checkout -->
      <div class="card">
        <div class="card-head">
          <h3 class="card-title">Current Bill</h3>
          <div class="flex">
            <button class="btn btn-ghost btn-sm" id="pos-hold">Hold</button>
            <button class="btn btn-ghost btn-sm" id="pos-held">Held (<span id="held-cnt">0</span>)</button>
            <button class="btn btn-ghost btn-sm" id="pos-clear">Clear</button>
          </div>
        </div>

        <div class="form-row">
          <label>
            <span class="flex-between">
              <span>Customer (walk-in if blank)</span>
              <button type="button" class="btn btn-ghost btn-sm" id="pos-new-cust" style="padding:1px 6px;font-size:11px">+ New</button>
            </span>
            <select id="pos-cust">
              <option value="">Walk-in Customer</option>
              ${customers.map(c => `<option value="${c.id}">${esc(c.name)} (${esc(c.phone || c.code)})</option>`).join("")}
            </select>
          </label>
          <label>
            <span class="flex-between">
              <span>Vehicle (optional)</span>
              <button type="button" class="btn btn-ghost btn-sm" id="pos-new-veh" style="padding:1px 6px;font-size:11px">+ New</button>
            </span>
            <select id="pos-veh"><option value="">—</option></select>
          </label>
        </div>

        <div id="pos-cart"></div>
        <div id="pos-totals" class="cart-totals"></div>

        <div class="mt-2">
          <div class="flex-between mb-2">
            <span class="muted" style="font-size:12px">Payments (split across methods if needed)</span>
            <button class="btn btn-ghost btn-sm" id="pos-add-pay">+ Split Payment</button>
          </div>
          <div id="pos-payments"></div>
        </div>

        <label class="mt-2"><span>Invoice Notes</span><input id="pos-notes" placeholder="Optional note on receipt…" /></label>

        <div class="flex mt-3">
          <button class="btn btn-primary btn-block" id="pos-submit">Complete Sale &amp; Print Receipt</button>
        </div>
      </div>
    </div>
  `;

  const qInput = root.querySelector("#pos-q");
  const tilesEl = root.querySelector("#pos-tiles");
  const custSel = root.querySelector("#pos-cust");
  const vehSel = root.querySelector("#pos-veh");

  function refreshVehOptions(cid, selectedVid = "") {
    const vs = vehicles.filter(v => Number(v.customer_id) === Number(cid));
    vehSel.innerHTML = `<option value="">—</option>` +
      vs.map(v => `<option value="${v.id}" ${Number(selectedVid) === v.id ? "selected" : ""}>${esc(v.registration_no || "")} ${esc(v.make || "")} ${esc(v.model || "")}</option>`).join("");
  }

  custSel.onchange = () => {
    state.customer_id = custSel.value ? Number(custSel.value) : "";
    refreshVehOptions(state.customer_id);
  };
  vehSel.onchange = () => { state.vehicle_id = vehSel.value ? Number(vehSel.value) : ""; };

  root.querySelector("#pos-new-cust").onclick = () => {
    openQuickCustomerModal((c) => {
      customers.unshift(c);
      custSel.innerHTML = `<option value="">Walk-in Customer</option>` +
        customers.map(x => `<option value="${x.id}" ${x.id === c.id ? "selected" : ""}>${esc(x.name)} (${esc(x.phone || x.code)})</option>`).join("");
      state.customer_id = c.id;
      refreshVehOptions(c.id);
    });
  };

  root.querySelector("#pos-new-veh").onclick = () => {
    openQuickVehicleModal(customers, state.customer_id, (v) => {
      vehicles.unshift(v);
      if (!state.customer_id) {
        state.customer_id = v.customer_id;
        custSel.value = String(v.customer_id);
      }
      state.vehicle_id = v.id;
      refreshVehOptions(state.customer_id, v.id);
    });
  };

  function renderTiles() {
    const list = state.tab === "products" ? state.catalog.products : state.catalog.services;
    if (!list.length) { tilesEl.innerHTML = `<div class="muted" style="grid-column:1/-1;padding:18px">No matching items</div>`; return; }
    tilesEl.innerHTML = list.map(it => {
      if (it.type === "product") {
        const cls = it.quantity_on_hand <= 0 ? "out" : it.low_stock ? "low" : "";
        return `<div class="cat-tile ${cls}" data-add="product:${it.id}">
          <div>
            <div class="ct-name">${esc(it.name)}</div>
            <div class="ct-meta">${esc(it.sku || "")} · Stock: ${it.quantity_on_hand} ${esc(it.unit)}</div>
          </div>
          <div class="ct-price">${money(it.price_paisa)}</div>
        </div>`;
      }
      return `<div class="cat-tile" data-add="service:${it.id}">
        <div>
          <div class="ct-name">${esc(it.name)}</div>
          <div class="ct-meta">Service · ${it.estimated_minutes || 0} min</div>
        </div>
        <div class="ct-price">${money(it.price_paisa)}</div>
      </div>`;
    }).join("");
    tilesEl.querySelectorAll("[data-add]").forEach(el => {
      el.onclick = () => {
        const [kind, idStr] = el.dataset.add.split(":");
        const id = Number(idStr);
        const src = (kind === "product" ? state.catalog.products : state.catalog.services).find(x => x.id === id);
        if (src) addToCart(src);
      };
    });
  }

  function addToCart(item) {
    const key = `${item.type}:${item.id}`;
    const existing = state.cart.find(c => c.key === key);
    if (existing) {
      if (item.type === "product" && existing.quantity + 1 > item.max_qty) {
        toast(`Only ${item.max_qty} in stock`, "warn");
        return;
      }
      existing.quantity += 1;
    } else {
      state.cart.push({
        key,
        item_type: item.type,
        product_id: item.type === "product" ? item.id : null,
        service_id: item.type === "service" ? item.id : null,
        description: item.name,
        unit: item.unit || "job",
        quantity: 1,
        max_qty: item.quantity_on_hand ?? 9999,
        unit_price_paisa: item.price_paisa,
        discount_paisa: 0,
      });
    }
    syncCart();
  }

  function calcTotals() {
    let gross = 0, lineDisc = 0;
    for (const c of state.cart) {
      gross += Math.round(c.quantity * c.unit_price_paisa);
      lineDisc += c.discount_paisa || 0;
    }
    const invDisc = state.invoice_discount || 0;
    const net = Math.max(0, gross - lineDisc - invDisc);
    const taxOn = appState.business?.tax_enabled;
    const rate = Number(appState.business?.tax_rate_percent || 0);
    const tax = taxOn && rate > 0 ? Math.round(net * rate / 100) : 0;
    const total = net + tax;
    return { gross, lineDisc, invDisc, tax, total };
  }

  function syncCart() {
    const cartEl = root.querySelector("#pos-cart");
    if (!state.cart.length) {
      cartEl.innerHTML = emptyState("Cart is empty — click or scan items to add");
    } else {
      cartEl.innerHTML = `
        <div class="table-wrap">
          <table class="tbl">
            <thead><tr><th>Item</th><th class="num">Qty</th><th class="num">Price (PKR)</th><th class="num">Disc (PKR)</th><th class="num">Line</th><th></th></tr></thead>
            <tbody>
              ${state.cart.map((c, idx) => {
                const line = Math.max(0, Math.round(c.quantity * c.unit_price_paisa) - c.discount_paisa);
                return `<tr>
                  <td>${esc(c.description)}</td>
                  <td class="num"><input data-qty="${idx}" type="number" min="1" max="${c.max_qty}" value="${c.quantity}" style="width:64px;text-align:right" /></td>
                  <td class="num"><input data-price="${idx}" type="number" step="0.01" min="0" value="${(c.unit_price_paisa / 100).toFixed(2)}" style="width:92px;text-align:right" /></td>
                  <td class="num"><input data-disc="${idx}" type="number" step="0.01" min="0" value="${(c.discount_paisa / 100).toFixed(2)}" style="width:80px;text-align:right" /></td>
                  <td class="num"><strong>${money(line)}</strong></td>
                  <td><button class="btn btn-ghost btn-sm" data-rm="${idx}">Remove</button></td>
                </tr>`;
              }).join("")}
            </tbody>
          </table>
        </div>`;
      cartEl.querySelectorAll("[data-qty]").forEach(inp => inp.onchange = () => {
        const c = state.cart[Number(inp.dataset.qty)];
        c.quantity = Math.max(1, Math.min(c.max_qty, Number(inp.value) || 1));
        syncCart();
      });
      cartEl.querySelectorAll("[data-price]").forEach(inp => inp.onchange = () => {
        state.cart[Number(inp.dataset.price)].unit_price_paisa = toPaisa(inp.value);
        syncCart();
      });
      cartEl.querySelectorAll("[data-disc]").forEach(inp => inp.onchange = () => {
        state.cart[Number(inp.dataset.disc)].discount_paisa = toPaisa(inp.value);
        syncCart();
      });
      cartEl.querySelectorAll("[data-rm]").forEach(b => b.onclick = () => {
        state.cart.splice(Number(b.dataset.rm), 1);
        syncCart();
      });
    }

    const t = calcTotals();
    if (state.payments.length === 1) {
      state.payments[0].amount = (t.total / 100).toFixed(2);
    }
    const totEl = root.querySelector("#pos-totals");
    totEl.innerHTML = `
      <div class="totals-row"><span>Subtotal</span><span>${money(t.gross - t.lineDisc)}</span></div>
      <div class="totals-row">
        <span>Invoice Discount (PKR)</span>
        <input id="pos-inv-disc" type="number" step="0.01" min="0" value="${(state.invoice_discount / 100).toFixed(2)}" style="width:110px;text-align:right" />
      </div>
      ${t.tax > 0 ? `<div class="totals-row"><span>Tax</span><span>${money(t.tax)}</span></div>` : ""}
      <div class="totals-row grand"><span>Grand Total</span><span>${money(t.total)}</span></div>
    `;
    totEl.querySelector("#pos-inv-disc").onchange = (e) => {
      state.invoice_discount = toPaisa(e.target.value);
      syncCart();
    };
    renderPayments();
  }

  function renderPayments() {
    const pEl = root.querySelector("#pos-payments");
    pEl.innerHTML = state.payments.map((p, i) => `
      <div class="flex mb-2">
        <select data-pm="${i}" style="max-width:150px">
          ${["cash", "card", "bank_transfer", "jazzcash", "easypaisa", "other"].map(m =>
            `<option value="${m}" ${p.method === m ? "selected" : ""}>${m.replace("_", " ")}</option>`).join("")}
        </select>
        <input data-pa="${i}" type="number" step="0.01" min="0" placeholder="Amount (PKR)" value="${p.amount}" />
        <input data-pr="${i}" placeholder="Ref / txn #" value="${esc(p.reference || "")}" />
        ${state.payments.length > 1 ? `<button class="btn btn-ghost btn-sm" data-prm="${i}">Remove</button>` : ""}
      </div>`).join("");
    pEl.querySelectorAll("[data-pm]").forEach(el => el.onchange = () => { state.payments[Number(el.dataset.pm)].method = el.value; });
    pEl.querySelectorAll("[data-pa]").forEach(el => el.oninput = () => { state.payments[Number(el.dataset.pa)].amount = el.value; });
    pEl.querySelectorAll("[data-pr]").forEach(el => el.oninput = () => { state.payments[Number(el.dataset.pr)].reference = el.value; });
    pEl.querySelectorAll("[data-prm]").forEach(el => el.onclick = () => {
      state.payments.splice(Number(el.dataset.prm), 1);
      renderPayments();
    });
  }

  root.querySelector("#pos-add-pay").onclick = () => {
    state.payments.push({ method: "card", amount: "0.00" });
    renderPayments();
  };

  root.querySelectorAll("[data-tab]").forEach(b => b.onclick = () => {
    state.tab = b.dataset.tab;
    renderTiles();
  });

  let sTimer = null;
  qInput.oninput = () => {
    clearTimeout(sTimer);
    sTimer = setTimeout(async () => {
      const q = qInput.value.trim();
      state.catalog = await api.get(`/api/pos/search?q=${encodeURIComponent(q)}`);
      renderTiles();
    }, 150);
  };
  qInput.onkeydown = async (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      const q = qInput.value.trim();
      if (!q) return;
      const res = await api.get(`/api/pos/search?q=${encodeURIComponent(q)}`);
      const exact = res.products.find(p => p.barcode === q || p.sku === q);
      if (exact) {
        addToCart(exact);
        qInput.value = "";
      }
    }
  };

  const getHeld = () => { try { return JSON.parse(localStorage.getItem(HOLD_KEY) || "[]"); } catch { return []; } };
  const setHeld = (arr) => { localStorage.setItem(HOLD_KEY, JSON.stringify(arr)); root.querySelector("#held-cnt").textContent = arr.length; };
  setHeld(getHeld());

  root.querySelector("#pos-hold").onclick = () => {
    if (!state.cart.length) { toast("Nothing to hold", "warn"); return; }
    const arr = getHeld();
    arr.push({ ts: new Date().toISOString(), cart: state.cart, customer_id: state.customer_id });
    setHeld(arr);
    state.cart = [];
    syncCart();
    toast("Bill held locally");
  };
  root.querySelector("#pos-held").onclick = () => {
    const arr = getHeld();
    if (!arr.length) { toast("No held bills", "warn"); return; }
    const m = openModal({
      title: "Held Bills",
      body: arr.map((h, i) => `
        <div class="flex-between" style="padding:8px 0;border-bottom:1px solid var(--border)">
          <span>#${i + 1} · ${h.cart.length} item(s) · ${fmtDateTime(h.ts)}</span>
          <button class="btn btn-primary btn-sm" data-resume="${i}">Resume</button>
        </div>`).join(""),
    });
    m.root.querySelectorAll("[data-resume]").forEach(b => b.onclick = () => {
      const idx = Number(b.dataset.resume);
      state.cart = arr[idx].cart;
      arr.splice(idx, 1);
      setHeld(arr);
      m.close();
      syncCart();
    });
  };
  root.querySelector("#pos-clear").onclick = () => { state.cart = []; state.invoice_discount = 0; syncCart(); };

  root.querySelector("#pos-submit").onclick = async () => {
    if (!state.cart.length) { toast("Add at least one item", "warn"); return; }
    const t = calcTotals();
    const payments = state.payments
      .map(p => ({ method: p.method, amount_paisa: toPaisa(p.amount), reference: p.reference || null }))
      .filter(p => p.amount_paisa > 0);
    const paidSum = payments.reduce((a, b) => a + b.amount_paisa, 0);

    if (paidSum < t.total && !state.customer_id) {
      toast("Select a customer to record a credit / partial-payment invoice", "err");
      return;
    }
    if (paidSum < t.total && !auth.hasRole("admin", "manager")) {
      toast("Credit or partial billing requires manager or administrator rights", "err");
      return;
    }

    const submitBtn = root.querySelector("#pos-submit");
    submitBtn.disabled = true;
    try {
      const inv = await api.post("/api/pos/invoices", {
        customer_id: state.customer_id || null,
        vehicle_id: state.vehicle_id || null,
        items: state.cart.map(c => ({
          item_type: c.item_type,
          product_id: c.product_id,
          service_id: c.service_id,
          description: c.description,
          quantity: c.quantity,
          unit: c.unit,
          unit_price_paisa: c.unit_price_paisa,
          discount_paisa: c.discount_paisa,
        })),
        invoice_discount_paisa: state.invoice_discount,
        payments,
        is_credit: paidSum < t.total,
        notes: root.querySelector("#pos-notes").value.trim() || null,
      });
      toast(`Invoice ${inv.invoice_number} saved`);
      state.cart = [];
      state.invoice_discount = 0;
      state.catalog = await api.get("/api/pos/search?q=");
      renderTiles();
      syncCart();
      refreshHeaderContext();
      showReceiptModal(inv);
    } catch (err) {
      toast(err.message, "err");
    } finally {
      submitBtn.disabled = false;
    }
  };

  renderTiles();
  syncCart();
}

export function showReceiptModal(inv) {
  const biz = appState.business || {};
  const printHtml = (thermal = false) => `
    <div class="print-area ${thermal ? "thermal" : ""}">
      <div style="text-align:center;border-bottom:1px dashed #706C64;padding-bottom:8px;margin-bottom:8px">
        <h2>${esc(biz.business_name || "Auto Workshop")}</h2>
        <div>${esc(biz.address || "")} · ${esc(biz.phone || "")}</div>
        ${biz.tax_ntn ? `<div>NTN/STRN: ${esc(biz.tax_ntn)}</div>` : ""}
      </div>
      <div style="display:flex;justify-content:space-between;font-size:12px">
        <div><strong>Invoice:</strong> ${esc(inv.invoice_number)}<br/><strong>Customer:</strong> ${esc(inv.customer_name)}</div>
        <div style="text-align:right"><strong>Date:</strong> ${fmtDateTime(inv.created_at)}<br/><strong>Status:</strong> ${esc(inv.status.toUpperCase())}</div>
      </div>
      ${inv.vehicle_label ? `<div style="font-size:12px;margin-top:4px"><strong>Vehicle:</strong> ${esc(inv.vehicle_label)}</div>` : ""}
      <table>
        <thead><tr><th>Description</th><th class="num">Qty</th><th class="num">Price</th><th class="num">Total</th></tr></thead>
        <tbody>
          ${inv.items.map(i => `
            <tr>
              <td>${esc(i.description)}</td>
              <td class="num">${i.quantity}</td>
              <td class="num">${money(i.unit_price_paisa)}</td>
              <td class="num">${money(i.line_total_paisa)}</td>
            </tr>`).join("")}
        </tbody>
      </table>
      <div style="border-top:1px solid #D5C8B6;padding-top:6px">
        <div class="totals-row"><span>Subtotal</span><span>${money(inv.subtotal_paisa)}</span></div>
        ${inv.discount_paisa > 0 ? `<div class="totals-row"><span>Discount</span><span>-${money(inv.discount_paisa)}</span></div>` : ""}
        ${inv.tax_paisa > 0 ? `<div class="totals-row"><span>Tax</span><span>${money(inv.tax_paisa)}</span></div>` : ""}
        <div class="totals-row grand"><span>Total</span><span>${money(inv.total_paisa)}</span></div>
        <div class="totals-row"><span>Paid (${esc(inv.payment_method_summary || "—")})</span><span>${money(inv.paid_paisa)}</span></div>
        ${inv.balance_paisa > 0 ? `<div class="totals-row"><span>Balance Due</span><span>${money(inv.balance_paisa)}</span></div>` : ""}
      </div>
      <div style="text-align:center;margin-top:12px;font-size:11px;color:#706C64">
        ${esc(biz.invoice_footer || "Thank you for your business!")}
      </div>
    </div>`;

  const m = openModal({
    title: `Receipt — ${inv.invoice_number}`,
    size: "lg",
    body: `<div id="rcp-wrap">${printHtml(false)}</div>`,
    foot: `
      <button class="btn btn-ghost" id="rcp-thermal">Thermal 80mm Layout</button>
      <button class="btn btn-ghost" id="rcp-a4">A4 Layout</button>
      <button class="btn btn-primary" id="rcp-print">Print Receipt</button>`,
  });
  let isThermal = false;
  m.root.querySelector("#rcp-thermal").onclick = () => { isThermal = true; m.root.querySelector("#rcp-wrap").innerHTML = printHtml(true); };
  m.root.querySelector("#rcp-a4").onclick = () => { isThermal = false; m.root.querySelector("#rcp-wrap").innerHTML = printHtml(false); };
  m.root.querySelector("#rcp-print").onclick = () => printDocument(printHtml(isThermal), isThermal);
}
