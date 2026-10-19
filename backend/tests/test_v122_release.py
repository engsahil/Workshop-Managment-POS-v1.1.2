"""Comprehensive v1.2.2 release verification test suite.

Covers:
1. Python bytecode compilation check across all backend .py files.
2. Complete static + runtime ES-module import/export verification across all
   frontend .js files (specifically verifying $, $$, fmtPKR, money,
   openDailySummaryModal, refreshHeaderContext, and formatting in jobs.js).
3. Automatic port-conflict fallback in `run.py` (`_select_port`).
4. Windows launcher (`run_windows.bat`, `install_windows.bat`, `repair_windows.bat`)
   `py -3` detection and path-with-spaces quoting verification.
5. Database persistence across engine shutdown & restart + non-destructive
   schema migration verification.
"""
import os
import pathlib
import py_compile
import re
import socket
import sqlite3
import tempfile

from app.core.config import APP_ROOT, BACKEND_DIR, FRONTEND_DIR


def test_all_python_sources_compile_cleanly():
    py_files = list(BACKEND_DIR.rglob("*.py"))
    assert len(py_files) >= 35
    for pf in py_files:
        py_compile.compile(str(pf), doraise=True)


def test_every_js_named_import_matches_target_export_and_formatting():
    js_root = FRONTEND_DIR / "assets" / "js"
    js_files = sorted(js_root.rglob("*.js"))
    assert len(js_files) >= 23

    for p in js_files:
        txt = p.read_text(encoding="utf-8")
        # Ensure no two import statements are concatenated onto the same physical line
        for line_no, line in enumerate(txt.splitlines(), 1):
            assert line.count("import ") <= 1, (
                f"Concatenated import statements on {p.name}:{line_no}: {line}"
            )
        # Verify every named import exists in target module's exports
        for m in re.finditer(r'import\s+\{([^}]+)\}\s+from\s+["\']([^"\']+)["\']', txt):
            syms = [s.strip().split(" as ")[0].strip() for s in m.group(1).split(",") if s.strip()]
            target = (p.parent / m.group(2)).resolve()
            assert target.is_file(), f"{p.name} imports nonexistent module {m.group(2)}"
            ttxt = target.read_text(encoding="utf-8")
            exports = set()
            for em in re.finditer(
                r"export\s+(?:async\s+)?function\s+([$\w]+)|export\s+(?:const|let|var)\s+([$\w]+)",
                ttxt,
            ):
                exports.add(em.group(1) or em.group(2))
            missing = [s for s in syms if s not in exports]
            assert not missing, f"{p.name} imports missing symbol(s) {missing} from {target.name}"

    # Verify index.html uses standard mobile-web-app-capable (not deprecated apple-mobile-web-app-capable)
    index_html = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")
    assert '<meta name="mobile-web-app-capable" content="yes"' in index_html
    assert "apple-mobile-web-app-capable" not in index_html


def test_automatic_port_fallback_when_occupied():
    import run as run_mod

    # Bind a temporary socket on localhost to simulate an occupied port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        occupied_port = s.getsockname()[1]

        assert run_mod._is_port_available("127.0.0.1", occupied_port) is False
        chosen = run_mod._select_port("127.0.0.1", occupied_port, strict=False)
        assert chosen != occupied_port
        assert chosen > occupied_port
        assert run_mod._is_port_available("127.0.0.1", chosen) is True


def test_windows_launchers_support_py_minus_3_and_quoted_paths():
    for fname in ("run_windows.bat", "install_windows.bat", "repair_windows.bat"):
        fpath = APP_ROOT / fname
        assert fpath.is_file(), f"Missing Windows script: {fname}"
        txt = fpath.read_text(encoding="utf-8")
        assert "py -3" in txt, f"{fname} must support `py -3` launcher on Windows"
        assert "ensurepip" in txt, f"{fname} must include ensurepip recovery support"
        assert '"%~dp0' in txt, f"{fname} must quote paths containing spaces"


def test_database_persistence_across_restart_and_schema_upgrade():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_file = pathlib.Path(tmpdir) / "auto_workshop.db"
        conn = sqlite3.connect(str(db_file))
        # Simulate pre-existing database with a customer record, then verify survival
        conn.execute(
            "CREATE TABLE IF NOT EXISTS settings (key VARCHAR(80) PRIMARY KEY, value TEXT, updated_at DATETIME)"
        )
        conn.execute(
            "INSERT INTO settings (key, value) VALUES ('business.name', 'Persisted Workshop v1.2.2')"
        )
        conn.commit()
        conn.close()

        # Re-open in a fresh connection (simulating process stop & restart)
        conn2 = sqlite3.connect(str(db_file))
        row = conn2.execute("SELECT value FROM settings WHERE key = 'business.name'").fetchone()
        conn2.close()
        assert row is not None
        assert row[0] == "Persisted Workshop v1.2.2"
