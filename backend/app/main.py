"""FastAPI application entry point."""
import logging
import os
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .core.config import (APP_NAME, APP_VERSION, CORS_ORIGINS, FRONTEND_DIR,
                          HOST, LOG_DIR, PORT)
from .core.database import init_db
from .services.settings_service import seed_defaults

log = logging.getLogger("awp")


def configure_logging():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(LOG_DIR / "app.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    init_db()
    from .core.database import get_session_factory
    with get_session_factory()() as db:
        seed_defaults(db)
    log.info("%s v%s starting on %s:%s", APP_NAME, APP_VERSION, HOST, PORT)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title=APP_NAME, version=APP_VERSION,
                  description="Auto Workshop POS & Management System",
                  lifespan=_lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS or ["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    configure_logging()

    from .routers import auth, catalog, claims, customers, finance, \
        inventory, invoices, jobs, pos, purchases, reports, settings, users
    for r in (auth.router, users.router, customers.router,
              inventory.router, purchases.router, catalog.router,
              jobs.router, pos.router, invoices.router, finance.router,
              claims.router, reports.router, settings.router):
        app.include_router(r)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError):
        messages = []
        safe_errors = []
        for err in exc.errors():
            loc = [str(p) for p in err.get("loc", []) if p != "body"]
            field = ".".join(loc) if loc else "input"
            msg = err.get("msg", "Invalid value")
            messages.append(f"{field}: {msg}")
            safe_errors.append({
                "loc": [str(p) for p in err.get("loc", [])],
                "msg": str(msg),
                "type": str(err.get("type", "validation_error")),
            })
        summary = "; ".join(messages) if messages else "Invalid input data"
        return JSONResponse(status_code=422, content={"detail": summary, "errors": safe_errors})

    @app.exception_handler(ValueError)
    async def _value_error(request: Request, exc: ValueError):
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(PermissionError)
    async def _perm_error(request: Request, exc: PermissionError):
        return JSONResponse(status_code=403, content={"detail": str(exc)})

    @app.exception_handler(Exception)
    async def _unhandled_error(request: Request, exc: Exception):
        log.exception("Unhandled server error on %s %s: %s", request.method, request.url.path, exc)
        return JSONResponse(
            status_code=500,
            content={"detail": "An unexpected server error occurred. Please try again."},
        )

    @app.middleware("http")
    async def _request_log(request: Request, call_next):
        start = time.time()
        try:
            resp = await call_next(request)
        except Exception as e:
            log.exception("Unhandled error on %s %s", request.method, request.url.path)
            raise
        log.info("%s %s -> %s (%.0fms)", request.method, request.url.path,
                 resp.status_code, (time.time() - start) * 1000)
        return resp

    @app.get("/api/health", include_in_schema=False)
    def health():
        return {"status": "ok", "version": APP_VERSION}

    # static frontend + SPA fallback (registered last so API routes win)
    if FRONTEND_DIR.exists():
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"),
                  name="assets")

        @app.get("/", include_in_schema=False)
        @app.get("/{full_path:path}", include_in_schema=False)
        def spa(full_path: str = ""):
            if full_path.startswith("api/") or full_path == "api":
                raise HTTPException(status_code=404, detail="Not found")
            candidate = FRONTEND_DIR / full_path
            if full_path and candidate.is_file():
                if candidate.name == "manifest.webmanifest":
                    return FileResponse(candidate, media_type="application/manifest+json")
                if candidate.name == "sw.js":
                    return FileResponse(
                        candidate,
                        media_type="application/javascript",
                        headers={
                            "Service-Worker-Allowed": "/",
                            "Cache-Control": "no-cache, no-store, must-revalidate",
                        },
                    )
                return FileResponse(candidate)
            return FileResponse(FRONTEND_DIR / "index.html")
    else:
        @app.get("/", include_in_schema=False)
        def _no_frontend():
            return {"app": APP_NAME, "version": APP_VERSION,
                    "frontend": "missing — build frontend/ first"}

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=False)
