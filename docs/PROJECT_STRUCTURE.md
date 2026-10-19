# Project Structure — Auto Workshop Management POS v1.2.2

```text
Auto-Workshop-Management-POS-v1.2.2/
├── START_HERE.txt             # Beginner-friendly Windows double-click launch guide
├── README.md                  # Quick-start, custom port, PWA & deployment guide
├── TROUBLESHOOTING.md         # Windows 10/11, py -3, pip repair, port & DB recovery guide
├── CHANGELOG.md               # Version history from 1.0.0 through 1.2.2
├── RELEASE_NOTES.md           # v1.2.2 release summary
├── TEST_REPORT.md             # Honest PASS / FAIL / NOT TESTED report (88 pytest + 17 smoke steps)
├── PROJECT_PROGRESS.md        # v1.2.2 completion checklist
├── RELEASE_PROGRESS.md        # Root-cause defect matrix & resolutions
├── FEATURE_STATUS.md          # Module-by-module feature status
├── PROJECT_STRUCTURE.md       # Repository layout reference
├── DATABASE_DESIGN.md         # SQLite schema & non-destructive migration design
├── LICENSE_NOTICES.md         # Open-source dependency license notices
├── .gitignore                 # Excludes .venv, __pycache__, data/, *.db, *.log, .env, *.zip
├── .env.example               # Environment variable template
├── requirements.txt           # Pinned Python 3.11–3.14+ dependencies
├── run_windows.bat            # Double-click Windows launcher (detects .venv, py -3, python)
├── install_windows.bat        # Windows .venv setup script
├── repair_windows.bat         # One-click Windows pip & .venv repair utility (preserves data/)
├── run.sh                     # Linux / macOS launcher
├── backend/
│   ├── run.py                 # Entrypoint: auto-port selection + /api/health readiness check
│   ├── requirements.txt       # Backend requirements mirror
│   ├── smoke_test.sh          # 17-step live HTTP end-to-end smoke test
│   ├── tests/                 # 88 automated pytest tests across 11 test modules
│   └── app/                   # FastAPI application (config.py APP_VERSION = "1.2.2", models, schemas, services, routers)
└── frontend/
    ├── index.html             # App shell (v1.2.2, White/Off-White/Beach theme, PWA manifest & Install App button)
    ├── manifest.webmanifest   # Installable PWA Web App Manifest
    ├── sw.js                  # Production-safe Service Worker (awp-shell-v1.2.2; never caches /api/)
    ├── vercel.json            # Optional Vercel static hosting headers
    └── assets/
        ├── css/app.css        # White + Off-White + Beach/Sand design system (Light & Dark modes)
        ├── icons/             # Valid PNG icons (192x192, 512x512, maskable 512x512, apple-touch-icon, favicon)
        └── js/
            ├── core/          # api.js, app.js, ui.js ($, $$, fmtPKR, money, openModal, confirmDialog, etc.)
            └── pages/         # index.js + 20 page modules
```
