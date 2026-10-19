"""Application configuration — environment based with safe defaults."""
import os
from pathlib import Path

# Project root: <root>/backend/app/core/config.py
APP_ROOT = Path(__file__).resolve().parents[3]          # .../auto_workshop_pos
BACKEND_DIR = APP_ROOT / "backend"
FRONTEND_DIR = APP_ROOT / "frontend"
BASE_DIR = APP_ROOT

DATA_DIR = Path(os.environ.get("AWP_DATA_DIR", BASE_DIR / "data"))
BACKUP_DIR = DATA_DIR / "backups"
LOG_DIR = DATA_DIR / "logs"
DB_PATH = DATA_DIR / "auto_workshop.db"

DATABASE_URL = os.environ.get("AWP_DATABASE_URL", f"sqlite:///{DB_PATH}")

SECRET_KEY = os.environ.get("AWP_SECRET_KEY", "")
HOST = os.environ.get("AWP_HOST") or os.environ.get("HOST") or "127.0.0.1"
PORT = int(os.environ.get("AWP_PORT") or os.environ.get("PORT") or "8000")

ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("AWP_TOKEN_EXPIRE_MINUTES", "720"))

# Money / display
CURRENCY_CODE = os.environ.get("AWP_CURRENCY", "PKR")
TIMEZONE = os.environ.get("AWP_TIMEZONE", "Asia/Karachi")

APP_NAME = "Auto Workshop Management POS"
APP_VERSION = "1.2.2"

# Allowed origins (local app by default)
CORS_ORIGINS = [o.strip() for o in os.environ.get("AWP_CORS_ORIGINS", "*").split(",") if o.strip()]

for _d in (DATA_DIR, BACKUP_DIR, LOG_DIR):
    try:
        _d.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
