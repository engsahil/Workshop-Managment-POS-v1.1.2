# Troubleshooting Guide — Auto Workshop Management POS v1.2.2

This guide covers common Windows 10/11, Python 3.14.6 (`py -3`), port, browser cache, and database recovery scenarios.

---

## 1. One-Click Automatic Repair (`repair_windows.bat`)

If `run_windows.bat` fails to install dependencies or start:
1. Double-click **`repair_windows.bat`** (or run `.\repair_windows.bat` in PowerShell).
2. `repair_windows.bat` will:
   - Repair `pip` using `py -3 -m ensurepip --upgrade`
   - Remove any broken `.venv` folder
   - Create a fresh `.venv` virtual environment
   - Install all packages from `requirements.txt`
   - **Preserve `data\auto_workshop.db` completely untouched**

---

## 2. `'python' is not recognized` on Windows (`py -3` vs `python`)

On many Windows 10/11 installations (including Python 3.14.6), Python is installed with the **Windows Python Launcher (`py`)** rather than `python.exe` on `PATH`.
- `run_windows.bat`, `install_windows.bat`, and `repair_windows.bat` in v1.2.2 automatically detect **`py -3`** first and do not assume `python` is on `PATH`.
- If running manual commands in PowerShell or Command Prompt, use `py -3`:
  ```powershell
  py -3 --version
  py -3 -m ensurepip --upgrade
  py -3 -m pip install -r requirements.txt
  py -3 backend\run.py
  ```

---

## 3. Corrupted `pip` on Python 3.14.6 (`No module named 'pip._vendor.rich'`)

If an interrupted `pip` upgrade left your global Python `pip` broken:
```powershell
py -3 -m ensurepip --upgrade
py -3 -m pip install --upgrade --force-reinstall pip
py -3 -m pip install -r requirements.txt
```

---

## 4. PowerShell Requires `.\` Before Script Names

In Windows PowerShell, typing `run_windows.bat` without `.\` produces a command-not-found error by design. Always run:
```powershell
.\run_windows.bat
```
Or pass a custom preferred port:
```powershell
.\run_windows.bat 7290
```

---

## 5. Port 8000 Is Already in Use

In v1.2.2, you do **not** need to manually edit any file if port `8000` is occupied:
- `backend\run.py` automatically checks whether port `8000` is free.
- If port `8000` is occupied, it automatically selects the next available port (e.g. `8001`), prints the exact URL in the terminal:
  ```text
  [NOTICE] Port 8000 is currently occupied. Automatically selected available port 8001.
  [READY] Auto Workshop Management POS v1.2.2 is live and responding!
  Open URL: http://127.0.0.1:8001
  ```
  and opens that exact URL in your browser once `/api/health` responds.
- You can also request a specific port explicitly:
  ```powershell
  .\run_windows.bat 7290
  ```

---

## 6. Browser Shows Cached Older JS Files After Upgrading

If you previously ran an older version (`v1.1.x`, `v1.2.0`, or an early `v1.2.1` build) on the same port and your browser cached old JavaScript modules:
1. Press **`Ctrl + Shift + R`** (or **`Ctrl + F5`**) in Chrome/Edge to perform a hard reload.
2. If you previously installed an older service worker on that port, open DevTools (`F12`) -> **Application** -> **Service Workers** -> click **Unregister**, then reload the page. (v1.2.2 uses versioned cache `awp-shell-v1.2.2` which automatically purges older `awp-shell-*` caches on activation.)

---

## 7. Database Location, Backups & Recovery

- **Live Database File:** `data\auto_workshop.db`
- **Automatic & Manual Backups:** `data\backups\`
- **Application Logs:** `data\logs\app.log`
- Upgrading to v1.2.2 never deletes `data\auto_workshop.db`. To restore a backup, sign in as Administrator and open **Backup & Restore** (`#/backups`) in the left sidebar.
