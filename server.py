"""
The Backlot — Control Room server.

Serves the studio operations console at `/` and mounts the full ADK API under
`/adk`, so the same process gives you the product UI a judge (or an ops team)
actually uses, plus ADK's developer UI at `/adk/dev-ui/` for inspecting raw
agent traces.

    python server.py                 # local
    PORT=8080 python server.py       # Cloud Run

The console talks to `/adk/run`, reads the event stream back, and renders
which specialists Control Room consulted, the SQL each one ran against
ClickHouse, and the synthesized answer — because "six agents correlated this"
is a claim you have to be able to SEE, not just read in a README.
"""
from __future__ import annotations

import os
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse
from google.adk.cli.fast_api import get_fast_api_app

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"

# Importing this configures the environment (loads .env, validates the
# ClickHouse credentials) before any agent module is imported by the loader.
from common.clickhouse_toolset import clickhouse_toolset  # noqa: E402,F401

adk_app = get_fast_api_app(agents_dir=str(ROOT / "orchestrator"), web=True)

app = FastAPI(title="The Backlot — Control Room")
app.mount("/adk", adk_app)


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "agent": "control_room"}


@app.get("/")
def console() -> FileResponse:
    return FileResponse(WEB / "index.html")


if __name__ == "__main__":
    uvicorn.run(
        app,
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", 8080)),
    )
