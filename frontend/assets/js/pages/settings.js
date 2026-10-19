// Business Settings — workshop profile, logo, numbering prefixes, tax & inventory rules, notification preferences.
import { api } from "../core/api.js";
import { appState, refreshHeaderContext } from "../core/app.js";
import { esc, formData, toast } from "../core/ui.js";

export async function renderSettings(root) {
  const [b, notifPrefs] = await Promise.all([
    api.get("/api/settings/business"),
    api.get("/api/settings/notifications").catch(() => ({
      job_alerts: true,
      invoice_alerts: true,
      low_stock_alerts: true,
      warranty_alerts: true,
      daily_summary_alerts: true,
      system_alerts: true,
    })),
  ]);
  appState.business = b;

  root.innerHTML = `
    <div class="grid-2">
      <div class="card">
        <div class="card-head">
          <h3 class="card-title">Business Profile &amp; Tax Configuration</h3>
        </div>
        <form id="biz-form">
          <div class="form-row">
            <label><span>Workshop / Business Name *</span><input name="business_name" required value="${esc(b.business_name || "")}" /></label>
            <label><span>Tagline</span><input name="tagline" value="${esc(b.tagline || "")}" /></label>
          </div>
          <div class="form-row">
            <label><span>Phone</span><input name="phone" value="${esc(b.phone || "")}" /></label>
            <label><span>Alternate Phone</span><input name="alt_phone" value="${esc(b.alt_phone || "")}" /></label>
            <label><span>Email</span><input name="email" value="${esc(b.email || "")}" /></label>
          </div>
          <label><span>Address</span><input name="address" value="${esc(b.address || "")}" /></label>
          <div class="form-row">
            <label><span>Business Hours</span><input name="business_hours" value="${esc(b.business_hours || "")}" placeholder="Mon–Sat 9:00 AM – 8:00 PM" /></label>
            <label><span>NTN / STRN (Tax ID)</span><input name="tax_ntn" value="${esc(b.tax_ntn || "")}" /></label>
          </div>

          <h4 style="margin:14px 0 8px">Numbering Prefixes</h4>
          <div class="form-row">
            <label><span>Invoice Prefix</span><input name="invoice_prefix" value="${esc(b.invoice_prefix || "INV")}" /></label>
            <label><span>Job Card Prefix</span><input name="job_prefix" value="${esc(b.job_prefix || "JOB")}" /></label>
            <label><span>Purchase Prefix</span><input name="purchase_prefix" value="${esc(b.purchase_prefix || "PO")}" /></label>
          </div>
          <div class="form-row">
            <label><span>Expense Prefix</span><input name="expense_prefix" value="${esc(b.expense_prefix || "EXP")}" /></label>
            <label><span>Return Prefix</span><input name="return_prefix" value="${esc(b.return_prefix || "RET")}" /></label>
            <label><span>Claim Prefix</span><input name="claim_prefix" value="${esc(b.claim_prefix || "CLM")}" /></label>
          </div>

          <h4 style="margin:14px 0 8px">Tax &amp; Stock Policy</h4>
          <div class="form-row">
            <label style="display:flex;align-items:center;gap:8px">
              <input type="checkbox" name="tax_enabled" style="width:auto" ${b.tax_enabled ? "checked" : ""} />
              <span style="margin:0">Enable Sales Tax on Invoices</span>
            </label>
            <label><span>Tax Rate (%)</span><input name="tax_rate_percent" type="number" step="0.1" min="0" max="100" value="${b.tax_rate_percent || 0}" /></label>
            <label><span>Default Low-Stock Threshold</span><input name="low_stock_default" type="number" min="0" value="${b.low_stock_default ?? 5}" /></label>
          </div>

          <label><span>Invoice Receipt Footer Message</span><textarea name="invoice_footer">${esc(b.invoice_footer || "")}</textarea></label>
          <button type="submit" class="btn btn-primary mt-2">Save Business Settings</button>
        </form>
      </div>

      <div>
        <div class="card mb-3">
          <div class="card-head"><h3 class="card-title">Workshop Logo</h3></div>
          <p class="muted">Upload a PNG, JPG, GIF, or WebP logo (max 2 MB) to appear in the sidebar and printed receipts.</p>
          ${b.logo_path ? `<div class="mb-2"><img src="/api/files/${esc(b.logo_path)}" alt="Workshop logo" style="max-height:72px;border-radius:8px;border:1px solid var(--border)" /></div>` : ""}
          <form id="logo-form" class="flex">
            <input type="file" name="logo" accept="image/png,image/jpeg,image/gif,image/webp" required />
            <button class="btn btn-primary btn-sm" type="submit">Upload Logo</button>
          </form>
        </div>

        <div class="card mb-3">
          <div class="card-head"><h3 class="card-title">Notification Preferences</h3></div>
          <form id="notif-pref-form">
            <label style="display:flex;align-items:center;gap:8px">
              <input type="checkbox" name="job_alerts" style="width:auto" ${notifPrefs.job_alerts !== false ? "checked" : ""} />
              <span style="margin:0">Service job creation, status &amp; ready-for-delivery alerts</span>
            </label>
            <label style="display:flex;align-items:center;gap:8px">
              <input type="checkbox" name="invoice_alerts" style="width:auto" ${notifPrefs.invoice_alerts !== false ? "checked" : ""} />
              <span style="margin:0">Invoice creation, payment &amp; outstanding balance alerts</span>
            </label>
            <label style="display:flex;align-items:center;gap:8px">
              <input type="checkbox" name="low_stock_alerts" style="width:auto" ${notifPrefs.low_stock_alerts !== false ? "checked" : ""} />
              <span style="margin:0">Low-stock &amp; out-of-stock inventory alerts</span>
            </label>
            <label style="display:flex;align-items:center;gap:8px">
              <input type="checkbox" name="warranty_alerts" style="width:auto" ${notifPrefs.warranty_alerts !== false ? "checked" : ""} />
              <span style="margin:0">Warranty claim submission &amp; status alerts</span>
            </label>
            <label style="display:flex;align-items:center;gap:8px">
              <input type="checkbox" name="daily_summary_alerts" style="width:auto" ${notifPrefs.daily_summary_alerts !== false ? "checked" : ""} />
              <span style="margin:0">Daily operational &amp; financial summary notifications</span>
            </label>
            <button type="submit" class="btn btn-ghost btn-sm mt-2">Save Notification Preferences</button>
          </form>
        </div>

        <div class="card">
          <div class="card-head"><h3 class="card-title">System Information</h3></div>
          <div class="table-wrap">
            <table class="tbl">
              <tbody>
                <tr><td class="muted">Version</td><td><strong>1.2.2</strong></td></tr>
                <tr><td class="muted">Theme</td><td>White + Off-White + Beach/Sand (Light &amp; Dark Modes)</td></tr>
                <tr><td class="muted">PWA Status</td><td>Installable Web App (<span class="mono">manifest.webmanifest</span> + <span class="mono">sw.js</span>)</td></tr>
                <tr><td class="muted">Currency</td><td>PKR (Rs.) — Integer Paisa Ledger</td></tr>
                <tr><td class="muted">Timezone</td><td>Asia/Karachi (PKT)</td></tr>
                <tr><td class="muted">Legal Documents</td><td><a href="#/legal">Privacy Policy &amp; Terms</a></td></tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  `;

  root.querySelector("#biz-form").onsubmit = async (e) => {
    e.preventDefault();
    const fd = formData(e.target);
    try {
      await api.put("/api/settings/business", {
        ...b,
        business_name: fd.business_name,
        tagline: fd.tagline || "",
        phone: fd.phone || "",
        alt_phone: fd.alt_phone || "",
        email: fd.email || "",
        address: fd.address || "",
        business_hours: fd.business_hours || "",
        tax_ntn: fd.tax_ntn || "",
        invoice_prefix: fd.invoice_prefix || "INV",
        job_prefix: fd.job_prefix || "JOB",
        purchase_prefix: fd.purchase_prefix || "PO",
        expense_prefix: fd.expense_prefix || "EXP",
        return_prefix: fd.return_prefix || "RET",
        claim_prefix: fd.claim_prefix || "CLM",
        tax_enabled: !!fd.tax_enabled,
        tax_rate_percent: Number(fd.tax_rate_percent) || 0,
        low_stock_default: Number(fd.low_stock_default) || 5,
        invoice_footer: fd.invoice_footer || "",
      });
      toast("Business settings saved");
      await refreshHeaderContext();
    } catch (err) { toast(err.message, "err"); }
  };

  root.querySelector("#logo-form").onsubmit = async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    try {
      await api.post("/api/settings/logo", fd);
      toast("Logo uploaded");
      await refreshHeaderContext();
      renderSettings(root);
    } catch (err) { toast(err.message, "err"); }
  };

  root.querySelector("#notif-pref-form").onsubmit = async (e) => {
    e.preventDefault();
    const fd = formData(e.target);
    try {
      await api.put("/api/settings/notifications", {
        job_alerts: !!fd.job_alerts,
        invoice_alerts: !!fd.invoice_alerts,
        low_stock_alerts: !!fd.low_stock_alerts,
        warranty_alerts: !!fd.warranty_alerts,
        daily_summary_alerts: !!fd.daily_summary_alerts,
        system_alerts: true,
      });
      toast("Notification preferences saved");
    } catch (err) { toast(err.message, "err"); }
  };
}

export default {
  route: "settings",
  title: "Settings",
  load: async () => renderSettings,
};
