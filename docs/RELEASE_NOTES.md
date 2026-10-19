# Release Notes — Auto Workshop Management POS v1.2.2

**Release Archive:** `Auto-Workshop-Management-POS-v1.2.2.zip`  
**Version:** `1.2.2`  
**Release Date:** `2026-10-17`

---

## Summary of Improvements in v1.2.2

1. **Zero Unresolved ES-Module Imports/Exports:**
   - Exported `$`, `$$`, and `fmtPKR` from `frontend/assets/js/core/ui.js`.
   - Exported `openDailySummaryModal` and `refreshHeaderContext` from `frontend/assets/js/core/app.js`.
   - Exported both named `export const pages` and `export default pages` from `frontend/assets/js/pages/index.js`.
   - Verified every single module and all 22 route renderers at runtime using Node.js's ES-module loader against a live FastAPI server.
2. **Windows `py -3` Support & Double-Click Ready `run_windows.bat`:**
   - Automatically detects `.venv\Scripts\python.exe`, `py -3` (Windows Python Launcher for Python 3.14.6), or `python`.
   - Automatically creates `.venv` and installs `requirements.txt` on first run, repairing `pip` via `ensurepip --upgrade` if needed.
   - Includes `repair_windows.bat`, `START_HERE.txt`, and `TROUBLESHOOTING.md`.
3. **Automatic Port Conflict Resolution & Readiness Check (`backend/run.py`):**
   - Defaults to `http://127.0.0.1:8000`; if port `8000` is occupied, automatically switches to the next available port (e.g. `8001`), prints the exact URL, and opens the browser **only after** `/api/health` responds HTTP 200.
4. **Flat Root Archive Layout:**
   - `Auto-Workshop-Management-POS-v1.2.2.zip` places project files directly at the archive root so Windows "Extract All..." extracts cleanly without creating nested duplicate folders.
