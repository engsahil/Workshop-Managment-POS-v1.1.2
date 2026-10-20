# Audit Report — Auto Workshop Management POS v1.2.2

**Date:** 2026-10-19
**Branch:** `arena/full-pos-audit-fixes` (base: `main` @ `86dc507`)
**Scope:** Full feature-by-feature audit with regression tests. No schema redesign, no UI redesign, no business-rule changes beyond the defects listed below.

---

## A. Reported defects — root cause and fix

### A1. Dashboard — `operator does not exist: timestamp without time zone >= character varying`
* **Root cause:** `report_service.dashboard()` compared `DateTime` columns against raw strings. SQLite accepts that silently; PostgreSQL rejects it. The same class of bug existed in the other report queries and in the backup timestamps.
* **Fix:** `core/dates.py` now provides `ensure_datetime()` / `range_utc()` that always return **naive UTC `datetime`** objects, plus a dialect-aware `local_date_expr()` so "today" is computed in Asia/Karachi on both SQLite and PostgreSQL. `core/security.utcnow()` also returns naive UTC to match every `TIMESTAMP WITHOUT TIME ZONE` column.
* **Evidence:** `test_reports.py::test_dashboard_date_filter_params` and the full suite run on PostgreSQL 16.2; live `GET /api/reports/dashboard?date_from=…&date_to=…` returns 200 with correct totals.

### A2. Inventory page — `Cannot set properties of null (setting 'innerHTML')`
* **Root cause:** page renderers re-resolved tab targets after an `await`. When the user switched tabs mid-request, the old target had already been removed from the DOM and the stale callback wrote into `null`.
* **Fix:** per-route `.page-view` containers in `core/app.js`; every page keeps its own root; async callbacks bail out when `!isConnected` / stale sequence. Inventory, products, staff, shifts, reports and dashboard were all hardened.
* **Evidence:** `node --check` on all page modules; live endpoints (`/api/inventory/low-stock`, `/api/products`, …) verified; the crash path (tab switch during load) is removed by the `isConnected`/sequence guards.

### A3. Cash Shifts
* **Root causes found:** (1) the UI posted `notes` while the schema expected `opening_notes` → 422 on open; (2) expected cash ignored cash refunds, void reversals and cash expenses; (3) any user could close another user's shift; (4) no ledger view.
* **Fix:** `notes` alias accepted; `cash_shifts.opening_notes` column + additive migration; `expected_cash = opening + cash sales − cash refunds/reversals − cash expenses +/− drawer movements`; own-shift-only close unless admin/manager; `GET /api/shifts/{id}/ledger`.
* **Evidence:** live PostgreSQL run — open shift (50 000), drawer addition (10 000), cash expense (2 000) → expected **58 000**; close accepted; second close → 400.

### A4. Mechanics & Staff — same `innerHTML` null error
* **Root cause:** same stale-async pattern as A2, plus the mechanic form re-rendered the whole page after save and lost focus/scroll.
* **Fix:** guarded render lifecycle (`isConnected`), local list refresh after CRUD, empty/loading states preserved.
* **Evidence:** live `POST/PUT/GET/DELETE /api/mechanics` all 200; staff page uses the same guarded renderer.

### A5. Reports & Analytics — `An unexpected error occurred.`
* **Root causes:** string-vs-timestamp comparisons (same as A1), an unknown `sales_by` field reaching the service layer, and stale responses overwriting newer tabs.
* **Fix:** typed date ranges everywhere; router returns **400** for an unknown breakdown field; per-tab sequence numbers ignore stale responses; error card with **Retry**; all 14 report endpoints verified live.

---

## B. Additional defects fixed

| Area | Defect | Fix |
| :--- | :--- | :--- |
| Backups | `create_backup()` wrote a raw file copy on a live DB; restore had no validation; JSON/PG restore attempted file swaps | SQLite online-backup API + integrity check; JSON snapshot v1 for PostgreSQL; validate → pre-restore backup → rebind; PG restore returns a clear 400 |
| Invoices | Sale-return refund/credit split not persisted; refunds could exceed paid amount; void allowed with open returns | Split fields persisted, refund capped at `paid_paisa`, void blocked until returns are resolved |
| Invoices | `invoice_detail` used `__import__("app.models")` — 500 when the app is imported as `backend.app` | Relative `User` import; `cashier_name` populated |
| Returns | `decide_return` mutated the row before validating the refund cap | Validation first; totals recomputed |
| Stock | Fractional quantities on stock-tracked items; product→service conversion stranded stock | Whole-unit enforcement on invoice/return lines; conversion blocked (400) with stock on hand or history |
| Inventory | `low_stock` / `out_of_stock` semantics mixed; services counted as low stock | Distinct counters; `min_stock > 0`; services excluded |
| Jobs | Cancel did not restore consumed parts; job invoicing had no state guard | Stock restored on cancel; cancelled jobs cannot be invoiced (400) |
| Jobs | Unknown `mechanic_id` on a service line → **500 IntegrityError** | Validated → **400 "Mechanic does not exist"** (create, update, job update) |
| Jobs | Mechanic could generate the final bill | `require_pos` on `POST /api/jobs/{id}/invoice`; billing buttons role-gated in the UI |
| Claims | Non-existent FKs produced 500s; free-form `item_type`/`status` | 400 "… does not exist"; enum validation (422) |
| Customers | Duplicate phone numbers only detected on byte-identical strings | Normalised comparison (`0300-1234567` = `+92 300 1234567`), 409 on create **and** update |
| Vehicles | Registration uniqueness ignored case only (kept as-is) | `_normalise_registration` uppercases/trims; behaviour unchanged |
| Credit | Repayment did not flip an invoice back to `partial` | Status recalculated after payment |
| Reports | `collections` did not subtract refunds | `refunds_paisa` + `net_paisa` added; dashboard shows the sub-line |
| Settings | `alt_phone`, `tax_ntn`, `invoice_footer` were editable in the UI but silently dropped | Added to defaults + schema + receipt `print-data` |
| Settings | `/api/audit` ignored `page_size` | Honours it (cap 200), returns `{items,total,page,page_size}` |
| Settings | Legal PUT required an unused `title` | Accepts `{content}`; 422 on empty content |
| Auth/RBAC | `require_financial` missing on several money-writing routes; daily summary readable by any role; last admin could be deactivated | Guards added; last-admin 400; daily summary requires `require_report` |
| Frontend | Sidebar logo used the raw `logo_path` (broken `<img>`) | Uses `/api/files/<path>` unless already absolute |
| Ops | `configure_logging()` added a new file handler on every `create_app()` | Idempotent |
| Dates | `utcnow()` returned an aware datetime against naive columns | Naive UTC |

---

## C. Feature verification performed

Verified over HTTP against a live server on **PostgreSQL 16.2** and by the automated suite on **SQLite**:

* Auth: first-run setup, login, token, role gates (admin/manager/cashier/mechanic).
* Customers & vehicles: create/update/delete guards, duplicate detection, history.
* Job cards: create → services/parts → approval → status workflow → invoice; stock consumption/restore.
* Inventory: products, receive, adjust, low/out-of-stock, valuation, stock history.
* POS: cash/credit/split payments, discount/tax, overpayment guard, returns (refund & credit), void.
* Purchases: suppliers, POs, partial receive, supplier statement.
* Expenses: categories, CRUD, shift linkage.
* Shifts: open, drawer movements, cash expenses, ledger, close, double-close guard.
* Reports: dashboard, sales-by (7 dimensions), profit, payments, trend, stock, returns, tax, overdue credit, mechanic performance, jobs, daily summary.
* Settings: business (full round-trip), logo, notifications, legal, audit pagination, backups.
* Notifications: list/unread, daily summary (GET/POST).
* Backup/restore: SQLite backup + validation + restore, JSON snapshot on PostgreSQL, upload validation.

---

## D. Automated tests

| Run | Environment | Result |
| :--- | :--- | :--- |
| Full suite, final | SQLite (pytest 9.1.1) | **117 passed** |
| Full suite, final | PostgreSQL 16.2 (`psycopg` 3.3.6) | **115 passed, 2 skipped** |

`backend/tests/test_zz_audit_fixes.py` contains **29** regression tests added by this audit (one per significant fix, named for the defect). The two skips are the SQLite-only backup-restore tests, which are intentionally gated on `IS_SQLITE`.

JavaScript: `node --check` passes for every file in `frontend/assets/js/`.

---

## E. Build, deployment and git

* Launch path verified end-to-end with `backend/run.py` (the documented launcher): startup banner, automatic port fallback (`8012 occupied → 8013`), `/api/health` `1.2.2`, SPA shell, setup, login, product → receive → invoice → receipt.
* No dependency, schema-destructive or configuration changes; the single schema change (`cash_shifts.opening_notes`) is additive and applied by the existing `upgrade_schema()` migration path on both backends.
* No secrets, credentials or generated artifacts are committed.

---

## F. Remaining work / known limitations

1. `audit_service.log()` commits and rolls back internally. Every caller commits its business transaction first, so the current risk is limited to an audit insert failure discarding nothing, but the helper should eventually use its own session.
2. There is no user-delete endpoint; users are deactivated (intentional, keeps audit history).
3. Vehicle registration uniqueness normalises case/whitespace but not punctuation (`ABC-123` vs `ABC 123` are still distinct).
4. COGS uses the product's current `purchase_cost_paisa` (documented methodology; a historical cost snapshot would need a schema change).
5. `expense_service.expenses_by_category()` is currently unused by any route.
6. Frontend verification is static (`node --check`, import/selector review) plus live HTTP; no headless browser is available in this environment, so DOM behaviour is not browser-automated.
7. Printing/PDF export relies on the browser print dialog and is not covered by automated tests.
8. PostgreSQL automatic restore remains intentionally unsupported (JSON snapshots are provided for archival).
