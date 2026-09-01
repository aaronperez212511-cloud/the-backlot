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
from common.trace_plugin import fleet_trace  # noqa: E402

adk_app = get_fast_api_app(agents_dir=str(ROOT / "orchestrator"), web=True)

app = FastAPI(title="The Backlot — Control Room")
app.mount("/adk", adk_app)


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "agent": "control_room"}


@app.get("/api/trace")
def trace_keys() -> dict:
    return {"sessions": fleet_trace.keys()}


@app.get("/api/trace/{session_id}")
def trace(session_id: str) -> dict:
    """The real sequence of tool calls the fleet made for this session.

    ADK's own API cannot supply this: `AgentTool` runs each specialist in its
    own invocation context, so their ClickHouse queries never appear in the
    parent session's events. The console reads this endpoint to show which
    specialists were consulted and the exact SQL each one ran.
    """
    return {"session_id": session_id, "steps": fleet_trace.trace(session_id)}


@app.get("/")
def console() -> FileResponse:
    return FileResponse(WEB / "index.html")


if __name__ == "__main__":
    uvicorn.run(
        app,
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", 8080)),
    )
