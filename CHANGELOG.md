# Changelog — Auto Workshop Management POS

All notable changes from `1.0.0` through release **`1.2.2`** are documented below.

---

## [Unreleased] — Full audit & hardening (2026-10-19)

### Fixed (reported defects)
- **Dashboard 500 on PostgreSQL:** `report_service.dashboard()` compared timestamp columns to plain strings (`operator does not exist: timestamp without time zone >= character varying`). All report date filters now pass typed naive-UTC datetimes, with dialect-aware "today" boundaries. Live PostgreSQL verification: dashboard returns correct totals for explicit ranges and single-day ranges.
- **Inventory / Mechanics & Staff `innerHTML` of null:** page renderers wrote into DOM targets that had been replaced by a tab switch. Per-route `.page-view` roots plus `isConnected`/stale-sequence guards remove the crash.
- **Cash Shifts:** opening a shift posted `notes` while the API expected `opening_notes` (422). Expected cash now includes cash refunds, void reversals and shift-tied cash expenses. Only the owning cashier may close a shift unless an admin/manager overrides; the ledger endpoint backs the new reconciliation view.
- **Reports & Analytics:** unknown `sales_by` breakdown returns 400 instead of a server error; stale tab responses are ignored; the page shows a Retry card on load failure.

### Fixed (additional audit findings)
- Backups: SQLite online-backup + integrity validation, JSON v1 snapshot for PostgreSQL, safe restore with pre-restore backup, clear 400 for unsupported restores.
- Invoices/returns: refund/credit split persisted, refund capped at paid amount, void blocked with open returns, `cashier_name` fixed (broken `__import__("app.models")` path).
- Stock: whole-unit quantities for stock-tracked items; low/out-of-stock semantics; services excluded from low-stock; negative-stock policy honoured on adjustments.
- Job cards: cancel restores consumed parts; cancelled jobs cannot be invoiced; unknown `mechanic_id` now returns 400 instead of a 500 IntegrityError; job invoicing requires POS roles.
- Claims: reference validation (400) and enum validation (422) on create/update.
- Customers: duplicate phone detection across formatting (`0300-1234567` = `+92 300 1234567`) on create and update (409).
- Credit: repayments flip invoices back to `partial`.
- Dashboard `collections` now exposes `refunds_paisa` and `net_paisa`.
- Settings: `alt_phone`, `tax_ntn`, `invoice_footer` are persisted and printed; audit log honours `page_size`; legal documents accept `{content}` only.
- RBAC: `require_financial` on money-writing routes, `require_report` on reports and daily summaries, last-admin protection, role-gated billing buttons and Daily Summary control.
- Frontend: sidebar logo resolves through `/api/files/`, guarded optional buttons, idempotent logging setup, naive-UTC `utcnow()`.

### Tests
- `backend/tests/test_zz_audit_fixes.py`: 29 regression tests for the fixes above.
- Final suites: **117 passed** on SQLite; **115 passed, 2 skipped** on PostgreSQL 16.2 (the skips are SQLite-only backup-restore tests).

---

## [1.2.2] — 2026-10-17

### Fixed (ES-Module Exports, First-Run Setup Payload & Meta Tag Deprecation)
- **Complete ES-Module Import/Export Alignment (`frontend/assets/js/core/ui.js`, `frontend/assets/js/core/app.js`, `frontend/assets/js/pages/index.js`):**
  - Exported `$` (`(sel, ctx = document) => ctx.querySelector(sel)`), `$$`, and `fmtPKR` (`export const fmtPKR = money;`) from `frontend/assets/js/core/ui.js` so `app.js` and `returns.js` import them without `SyntaxError`.
  - Updated `confirmDialog()` in `frontend/assets/js/core/ui.js` to accept both string `(message, title)` and object `({ title, message, danger })` arguments.
  - Exported `openDailySummaryModal` and `refreshHeaderContext` aliases from `frontend/assets/js/core/app.js` so `dashboard.js`, `jobs.js`, `pos.js`, `settings.js`, and `shifts.js` resolve all named imports cleanly.
  - Verified clean single-line import formatting in `frontend/assets/js/pages/jobs.js` and across all 24 frontend `.js` files.
  - Fixed `#setup-form` submission in `frontend/assets/js/core/app.js` to include `password_confirm` in `POST /api/auth/setup` and made `SetupAdminIn.password_confirm` optional when omitted by API callers.
  - Replaced deprecated `<meta name="apple-mobile-web-app-capable" content="yes" />` in `frontend/index.html` with standard `<meta name="mobile-web-app-capable" content="yes" />`.

### Added (Windows `py -3` Launcher, Auto-Port Fallback & Post-Health Browser Launch)
- **Windows Launcher & Recovery (`run_windows.bat`, `install_windows.bat`, `repair_windows.bat`):**
  - Updated all Windows `.bat` scripts to detect `.venv\Scripts\python.exe`, `py -3` (Windows Python Launcher for Python 3.11–3.14.6), and `python` without assuming `python` is on `PATH`.
  - `run_windows.bat` now automatically creates `.venv` on first run if needed, repairs a broken `pip` via `ensurepip --upgrade`, installs `requirements.txt`, handles folder paths containing spaces, and launches the backend.
  - Added `repair_windows.bat`, `START_HERE.txt`, `TROUBLESHOOTING.md`, and `.gitignore`.
- **Automatic Port Conflict Resolution & Readiness Check (`backend/run.py`):**
  - Defaults to `http://127.0.0.1:8000`; if port `8000` (or the requested port) is occupied, automatically selects the next available port (e.g. `8001`), prints the exact URL, polls `/api/health` until HTTP 200, and opens the browser **only after** the server is responding.
- **Expanded Automated Regression Suite (`backend/tests/test_v122_release.py`):**
  - Added 5 new test suites (`88 passed` total) verifying bytecode compilation of all Python files, static + Node.js ES-module import/export linking across all frontend JS files, automatic port-conflict fallback, Windows `py -3` launcher scripts, and SQLite persistence across restarts.
- **Archive Structure (`Auto-Workshop-Management-POS-v1.2.2.zip`):**
  - Packaged project files directly at the archive root so Windows "Extract All..." extracts cleanly without creating nested duplicate folders.

---

## [1.2.1] — 2026-10-17
- Fixed Returns & Warranty (`/api/invoices/returns`, `/api/invoices/returns/{rid}/decide`, `/api/claims`) and `pages/index.js` named `pages` export.
- Replaced application color scheme with White + Off-White + Beach/Sand palette (`#FFFFFF`, `#FAF9F6`, `#F4F0E8`, `#DCCBB2`, `#BBA486`, `#292824`, `#706C64`, `#E8E2D8`) with Light & Dark modes.
- Added installable PWA support (`/manifest.webmanifest`, `192×192` & `512×512` maskable PNG icons, production-safe `/sw.js`, `#btn-install-app`).

---

## [1.2.0] — 2026-10-17
- Resolved Windows `ZoneInfoNotFoundError`, hardened Customer/Vehicle/Job/Expense/Claim/Backup/Password workflows, and added printable Job Cards, Audit Log viewer, and Daily Closing Summary.
