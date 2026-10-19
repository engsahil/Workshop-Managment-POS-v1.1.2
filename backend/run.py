"""Run the Auto Workshop Management POS v1.2.2 backend.

Features:
- Defaults to http://127.0.0.1:8000
- If port 8000 (or the requested port) is already occupied, automatically finds
  the next available port (unless AWP_STRICT_PORT=1 is set), displays the exact
  URL in the terminal, and opens that URL in the browser only AFTER /api/health
  is actually responding.

Usage:
    py -3 run.py                  # 127.0.0.1:8000 (or next available port)
    py -3 run.py 7290             # 127.0.0.1:7290 (or next available port)
    PORT=7290 py -3 run.py
    AWP_HOST=0.0.0.0 py -3 run.py
"""
import os
import socket
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def _is_port_available(host: str, port: int) -> bool:
    check_host = "127.0.0.1" if host in ("0.0.0.0", "::") else host
    # 1. Check if any server is already listening on check_host:port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.35)
        if s.connect_ex((check_host, port)) == 0:
            return False
    # 2. Verify we can bind to the port
    bind_host = "0.0.0.0" if host == "0.0.0.0" else check_host
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((bind_host, port))
            return True
        except OSError:
            return False


def _select_port(host: str, preferred_port: int, strict: bool = False) -> int:
    if _is_port_available(host, preferred_port):
        return preferred_port
    if strict:
        print(
            f"[ERROR] Port {preferred_port} on {host} is already in use by another process.",
            file=sys.stderr,
        )
        sys.exit(1)
    for candidate in range(preferred_port + 1, preferred_port + 101):
        if _is_port_available(host, candidate):
            print(
                f"[NOTICE] Port {preferred_port} is currently occupied. "
                f"Automatically selected available port {candidate}."
            )
            return candidate
    # Fallback: ask OS for an ephemeral free port
    bind_host = "127.0.0.1" if host in ("0.0.0.0", "::") else host
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((bind_host, 0))
        ephemeral = s.getsockname()[1]
        print(
            f"[NOTICE] Port {preferred_port} is currently occupied. "
            f"Automatically selected available port {ephemeral}."
        )
        return ephemeral


def _wait_until_ready_and_open_browser(host: str, port: int, open_browser: bool, app_name: str, version: str):
    browser_host = "127.0.0.1" if host in ("0.0.0.0", "::") else host
    base_url = f"http://{browser_host}:{port}"
    health_url = f"{base_url}/api/health"
    for _ in range(150):  # up to ~22.5 seconds
        try:
            with urllib.request.urlopen(health_url, timeout=1.0) as resp:
                if resp.status == 200:
                    print("\n" + "=" * 70, flush=True)
                    print(f"  [READY] {app_name} v{version} is live and responding!", flush=True)
                    print(f"  Open URL: {base_url}", flush=True)
                    print("  Stop Server: Press Ctrl+C in this window", flush=True)
                    print("=" * 70 + "\n", flush=True)
                    if open_browser:
                        try:
                            webbrowser.open(base_url)
                        except Exception:
                            pass
                    return
        except Exception:
            time.sleep(0.15)


# Resolve requested host & port before importing config so config.PORT matches
_req_host = os.environ.get("AWP_HOST") or os.environ.get("HOST") or "127.0.0.1"
_req_port_str = (
    sys.argv[1]
    if len(sys.argv) > 1 and sys.argv[1].isdigit()
    else (os.environ.get("AWP_PORT") or os.environ.get("PORT") or "8000")
)
_req_port = int(_req_port_str)
_strict_port = os.environ.get("AWP_STRICT_PORT", "").strip() in ("1", "true", "yes")

if __name__ == "__main__":
    _chosen_port = _select_port(_req_host, _req_port, strict=_strict_port)
    os.environ["AWP_PORT"] = str(_chosen_port)
    os.environ["PORT"] = str(_chosen_port)

from app.core.config import APP_NAME, APP_VERSION, HOST, PORT  # noqa: E402
from app.main import app  # noqa: E402

if __name__ == "__main__":
    import uvicorn

    display_host = "127.0.0.1" if HOST in ("0.0.0.0", "::") else HOST
    print(f"Initializing {APP_NAME} v{APP_VERSION} on http://{display_host}:{PORT} ...", flush=True)

    should_open_browser = os.environ.get("AWP_OPEN_BROWSER", "").strip() in ("1", "true", "yes")
    if os.environ.get("AWP_NO_BROWSER", "").strip() in ("1", "true", "yes"):
        should_open_browser = False

    watcher = threading.Thread(
        target=_wait_until_ready_and_open_browser,
        args=(HOST, PORT, should_open_browser, APP_NAME, APP_VERSION),
        daemon=True,
    )
    watcher.start()

    uvicorn.run("app.main:app", host=HOST, port=PORT, log_level="info")
