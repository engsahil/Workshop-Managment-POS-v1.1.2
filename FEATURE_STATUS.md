# Feature Status — Auto Workshop Management POS v1.2.2

All 20 application modules and 22 routes are implemented, connected to persistent SQLite storage, and verified by `88` automated pytest tests + `17` live HTTP smoke test steps + `23` live DOM/Fetch route renders.

- **Authentication & RBAC:** First-run setup, Argon2id login/logout, JWT sessions, role guards (`admin`, `manager`, `cashier`), password change & admin reset.
- **Dashboard (`#/dashboard`):** Live sales, collections, parts vs labor, net profit, receivables, active jobs, low-stock alerts, recent activity tables, and Daily Closing Summary modal.
- **POS Billing (`#/pos`):** Barcode/SKU search, stock badges, discounts, tax, split payments, credit sales, A4 & 80mm thermal receipts.
- **Workshop Job Cards (`#/jobs`):** Vehicle check-in, estimates, customer approval gate, labor & parts issue, printable Job Card, and one-click invoice conversion.
- **Returns & Warranty (`#/returns`):** Sale Returns & Refunds (`/api/invoices/returns`, `/api/invoices/returns/{rid}/decide`) with returnable quantity validation and live refund calculation + Warranty Claims (`/api/claims`) with create, view, search, filter, update, and delete.
- **Inventory, Purchases, Customers, Vehicles, Services, Staff, Expenses, Shifts, Reports, Users, Settings, Backups, Audit Log, Legal & Help:** Complete and verified.
