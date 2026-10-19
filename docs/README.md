# Auto Workshop Management POS — v1.2.2

Enterprise, local-first & web-deployable **Auto Workshop & Point-of-Sale (POS) Management System** for motorcycle and car repair workshops and spare-parts counters in Pakistan (`PKR`, integer paisa accounting, `Asia/Karachi` timezone).

---

## 1. Windows Quick Start (Double-Click or PowerShell/CMD)

### Prerequisites
- **Windows 10 / 11**
- **Python 3.11 – 3.14+** (verified compatible with **Python 3.14.6** via `py -3` or `python`)

### Launch in 3 Steps
1. Extract **`Auto-Workshop-Management-POS-v1.2.2.zip`** to any folder (for example `C:\AutoWorkshopPOS`).
2. Double-click **`run_windows.bat`** (or in PowerShell inside the folder, run `.\run_windows.bat`).
3. Wait a few seconds while `run_windows.bat` verifies dependencies (`py -3` / `.venv`), initializes `data\auto_workshop.db`, starts the FastAPI server on **`http://127.0.0.1:8000`** (or automatically switches to the next free port such as `8001` if `8000` is occupied), and opens your browser **after** `/api/health` is responding.

See **`START_HERE.txt`** for a beginner-friendly guide and **`TROUBLESHOOTING.md`** (or double-click **`repair_windows.bat`**) if your Python/`pip` environment needs repair.

---

## 2. Custom Port & Command-Line Usage

```powershell
# Default port 8000 (auto-switches if 8000 is busy):
.\run_windows.bat

# Custom preferred port (e.g. 7290):
.\run_windows.bat 7290

# Direct Python launch using Windows Python Launcher (`py -3`):
py -3 backend\run.py
```

---

## 3. Linux / macOS Quick Start

```bash
chmod +x run.sh
./run.sh             # Default http://127.0.0.1:8000 (auto-switches if busy)
./run.sh 7290        # Custom preferred port 7290
```

---

## 4. Progressive Web App (PWA) & White/Off-White/Beach Theme

- **Visual Theme:** Clean White (`#FFFFFF`), Soft Off-White (`#FAF9F6`), Warm Ivory (`#F4F0E8`), Beach Sand (`#DCCBB2`), Muted Sand (`#BBA486`), Deep Charcoal (`#292824`), and Soft Sand Borders (`#E8E2D8`), with full Light & Dark mode switching (`#btn-theme`).
- **Installable PWA:** Valid `/manifest.webmanifest`, `192×192` & `512×512` (including maskable) PNG icons, production-safe `/sw.js` service worker (`awp-shell-v1.2.2`, which never caches `/api/*` or authenticated responses), and topbar **Install App** button (`#btn-install-app`).

---

## 5. Automated Testing (`88 passed, 0 failed`)

```powershell
cd backend
py -3 -m pytest tests/ -v
```
All **88 automated tests** pass (`88 passed, 0 failed`), covering authentication, RBAC, POS billing, job cards, inventory, purchases, expenses, shifts, reports, backups, audit logs, Returns & Warranty (`/api/invoices/returns` & `/api/claims`), ES-module import/export linking across all 24 JS files, automatic port-conflict fallback, and SQLite database persistence across restarts.
