# Changelog — Auto Workshop Management POS

All notable changes from `1.0.0` through release **`1.2.2`** are documented below.

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
