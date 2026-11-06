#!/usr/bin/env python3
"""Serve the pinned Harbor viewer with local inspection routes only."""
import argparse
import os
from pathlib import Path

os.environ["HARBOR_TELEMETRY"] = "0"
os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"

from fastapi.responses import JSONResponse
from harbor.viewer.server import create_app
import uvicorn

ROOT = Path(__file__).resolve().parent
# Deliberately exclude auth, pricing estimation, launch, upload, analysis,
# streaming/editor, remote-source and all write endpoints.
READ_PATHS = {
    "/api/health", "/api/jobs", "/api/jobs/filters", "/api/compare",
    "/api/jobs/{job_name}", "/api/jobs/{job_name}/config",
    "/api/jobs/{job_name}/tasks", "/api/jobs/{job_name}/tasks/filters",
    "/api/jobs/{job_name}/trials", "/api/jobs/{job_name}/chart-trials",
    "/api/jobs/{job_name}/trials/{trial_name}",
    "/api/jobs/{job_name}/trials/{trial_name}/navigation",
    "/api/jobs/{job_name}/trials/{trial_name}/trajectory",
    "/api/jobs/{job_name}/trials/{trial_name}/interaction",
    "/api/jobs/{job_name}/trials/{trial_name}/verifier-output",
    "/api/jobs/{job_name}/trials/{trial_name}/files",
    "/api/jobs/{job_name}/trials/{trial_name}/files/{file_path:path}",
    "/api/jobs/{job_name}/trials/{trial_name}/artifacts",
    "/api/jobs/{job_name}/trials/{trial_name}/agent-logs",
}


def make_app(folder, static_dir=None):
    folder = Path(folder).resolve()
    app = create_app(folder, static_dir=static_dir)
    # Remove routes as well as denying them in middleware, including WebSockets.
    routes = []
    read_routes = []
    for route in app.router.routes:
        path = getattr(route, "path", "")
        methods = getattr(route, "methods", set()) or set()
        if path in READ_PATHS and methods <= {"GET", "HEAD"}:
            routes.append(route)
            read_routes.append(route)
        elif path in {"/assets", "/fonts", "/favicon.ico", "/favicon.svg", "/{path:path}"}:
            routes.append(route)
    app.router.routes = routes

    @app.middleware("http")
    async def inspection_only(request, call_next):
        path = request.url.path
        if request.method not in {"GET", "HEAD"}:
            return JSONResponse({"detail": "This experiment viewer is read-only."}, status_code=405)
        if path == "/api/config":
            return JSONResponse({"folder": str(folder), "source": "folder", "mode": "jobs",
                                 "environments": [], "capabilities": dict.fromkeys(
                                     ["controls", "analysis", "upload", "workspace", "launch"], False)})
        if path == "/api/auth/status":
            return JSONResponse({"authenticated": False})
        if path.startswith("/api/") and not any(route.path_regex.fullmatch(path) for route in read_routes):
            return JSONResponse({"detail": "Endpoint disabled for local inspection."}, status_code=404)
        return await call_next(request)

    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jobs", type=Path, default=ROOT / "output/jobs")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    static = ROOT / ".cache/harbor/src/harbor/viewer/static"
    if not (static / "index.html").exists():
        parser.error("Viewer assets missing; run bootstrap.py first.")
    if not args.jobs.is_dir():
        parser.error("Export a run first; the jobs directory does not exist.")
    uvicorn.run(make_app(args.jobs, static), host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
