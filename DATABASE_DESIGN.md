# Database Design — Auto Workshop Management POS v1.2.2

Auto Workshop Management POS uses a relational SQLite database (`data/auto_workshop.db`, configurable via `AWP_DATABASE_URL` for SQLite or PostgreSQL) managed by SQLAlchemy 2.0 ORM.

## 1. Non-Destructive Schema Evolution (`init_db()` & `upgrade_schema()`)
On application startup, `backend/app/core/database.py` runs `init_db()` followed by `upgrade_schema()`.
`upgrade_schema()` inspects existing tables and applies non-destructive `ALTER TABLE ... ADD COLUMN` statements for any new columns introduced in newer versions, preserving 100% of existing workshop data across upgrades from v1.0.x, v1.1.x, v1.2.0, and v1.2.1 to v1.2.2.

## 2. Core Accounting & Integrity Invariants
- **Integer Paisa Storage:** All monetary columns (`*_paisa`) store integer paisa (`1 PKR = 100 paisa`).
- **Foreign Keys & WAL Mode:** SQLite connections enable `PRAGMA foreign_keys = ON` and `PRAGMA journal_mode = WAL`.
- **Traceable Stock Ledger:** Every stock change writes an immutable `StockMovement` record (`purchase`, `sale`, `job_issue`, `sale_return`, `purchase_return`, `sale_void`, `adjustment`, `damage`).
- **Sale Returns & Returnable Quantities:** `SaleReturn` and `SaleReturnItem` link directly to `Invoice` and `InvoiceItem`; `_returnable()` in `invoice_service.py` enforces that cumulative approved returns never exceed the original sold quantity.
