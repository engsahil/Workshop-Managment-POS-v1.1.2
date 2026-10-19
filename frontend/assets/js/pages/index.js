// Page registry — maps route keys to lazy/direct renderers.
// Exposes both named `pages` export and `default` export to preserve router contract.
import { renderDashboard } from "./dashboard.js";
import { renderPOS } from "./pos.js";
import { renderInvoices } from "./invoices.js";
import { renderCustomers } from "./customers.js";
import { renderVehicles } from "./vehicles.js";
import { renderProducts } from "./products.js";
import { renderJobs } from "./jobs.js";
import { renderServices } from "./services.js";
import { renderStaff } from "./staff.js";
import { renderPurchases } from "./purchases.js";
import { renderExpenses } from "./expenses.js";
import { renderShifts } from "./shifts.js";
import { renderReturns } from "./returns.js";
import { renderReports } from "./reports.js";
import { renderUsers } from "./users.js";
import { renderSettings } from "./settings.js";
import { renderBackups } from "./backups.js";
import { renderAudit } from "./audit.js";
import { renderLegal, renderLegalPublic } from "./legal.js";
import { renderHelp } from "./help.js";

export const pages = [
  { route: "dashboard", title: "Dashboard", load: async () => renderDashboard },
  { route: "pos", title: "POS Billing", load: async () => renderPOS },
  { route: "invoices", title: "Invoices", load: async () => renderInvoices },
  { route: "customers", title: "Customers", load: async () => renderCustomers },
  { route: "vehicles", title: "Vehicles", load: async () => renderVehicles },
  { route: "products", title: "Parts & Inventory", load: async () => renderProducts },
  { route: "jobs", title: "Job Cards", load: async () => renderJobs },
  { route: "services", title: "Services & Labor", load: async () => renderServices },
  { route: "staff", title: "Mechanics & Staff", load: async () => renderStaff },
  { route: "purchases", title: "Purchases & Suppliers", load: async () => renderPurchases },
  { route: "expenses", title: "Expenses", load: async () => renderExpenses },
  { route: "shifts", title: "Cash Shifts", load: async () => renderShifts },
  { route: "returns", title: "Returns & Warranty", load: async () => renderReturns },
  { route: "reports", title: "Reports & Analytics", load: async () => renderReports },
  { route: "users", title: "Users & Roles", load: async () => renderUsers },
  { route: "settings", title: "Settings", load: async () => renderSettings },
  { route: "backups", title: "Backup & Restore", load: async () => renderBackups },
  { route: "audit", title: "Audit Log", load: async () => renderAudit },
  { route: "legal", title: "Legal Documents", load: async () => renderLegal },
  { route: "privacy", title: "Privacy Policy", load: async () => (root) => renderLegal(root, "privacy_policy") },
  { route: "terms", title: "Terms & Conditions", load: async () => (root) => renderLegal(root, "terms_conditions") },
  { route: "help", title: "Help & Guide", load: async () => renderHelp },
];

// Attach direct route-key functions onto `pages` so both array lookup
// (`pages.find(p => p.route === key)`) and property access (`pages[key]`) work.
for (const entry of pages) {
  pages[entry.route] = async (root, params) => {
    const fn = await entry.load();
    return fn(root, params);
  };
}
pages.legal = renderLegal;
pages.legalPublic = renderLegalPublic;

export default pages;
