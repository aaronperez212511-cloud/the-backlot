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

The `/api/watch/*` endpoints drive the Watchtower (common/watchtower.py): the
same fleet running on a schedule with nobody in the room. That path is
asynchronous in both senses — triggered by a clock rather than a request, and
handed off to a background task so the trigger returns in milliseconds while
the investigation keeps running for minutes.
"""
from __future__ import annotations

import asyncio
import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Header, HTTPException, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from google.adk.cli.fast_api import get_fast_api_app

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"

# Importing this configures the environment (loads .env, validates the
# ClickHouse credentials) before any agent module is imported by the loader.
from common.clickhouse_toolset import clickhouse_toolset  # noqa: E402,F401
from common.trace_plugin import fleet_trace  # noqa: E402
from common import watchtower  # noqa: E402

adk_app = get_fast_api_app(agents_dir=str(ROOT / "orchestrator"), web=True)

# Background sweeps are held here for the process lifetime. The event loop
# keeps only a weak reference to a bare `asyncio.create_task(...)`, so without
# this the garbage collector is free to cancel an in-flight sweep
# mid-investigation — which looks exactly like the fleet silently deciding not
# to run, and is miserable to diagnose after the fact.
_tasks: set[asyncio.Task] = set()


def _spawn(coro) -> None:
    task = asyncio.create_task(coro)
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Off unless asked for. On Cloud Run the real trigger is Cloud Scheduler
    # calling /api/watch/run (deploy/schedule.sh), because an idle instance's
    # CPU is frozen and a sleep-driven loop inside the container stops running
    # under exactly the conditions an unattended watch is meant to cover.
    # WATCH_INTERVAL_MIN runs the same autonomous behaviour on a laptop with
    # no GCP setup at all.
    interval = int(os.environ.get("WATCH_INTERVAL_MIN", "0"))
    if interval > 0:
        _spawn(watchtower.loop(interval))
    yield


app = FastAPI(title="The Backlot — Control Room", lifespan=lifespan)
app.mount("/adk", adk_app)
# Brand assets: the Pinyon Script face the specialist marks are set in, its
# OFL licence, and the rendered letter PNGs. Served as plain static files so
# the console needs no font CDN for its own marks.
app.mount("/marks", StaticFiles(directory=str(WEB / "marks")), name="marks")


@app.get("/api/health")
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


def _authorise(token: str | None) -> None:
    """Gates the one endpoint that costs money to call.

    The service runs `--allow-unauthenticated` so judges can open the console
    without a Google account, which also means anything reachable is reachable
    by anyone. Every other route here is a cheap read; `/api/watch/run` fans
    out to six specialists across Vertex AI, so left open it is a free button
    for burning the project's shared Gemini quota. Set WATCH_TOKEN in the
    deployment and Cloud Scheduler sends it back as a header.

    Unset means open, which is right for `python server.py` on a laptop and
    wrong in production — deploy/schedule.sh sets it.
    """
    expected = os.environ.get("WATCH_TOKEN")
    if not expected:
        return
    # compare_digest, not ==. Python's string equality returns as soon as two
    # bytes differ, so how long the comparison takes leaks how much of the
    # token was right, and this endpoint is reachable by anyone on the
    # internet. The cost of not caring is a slow guessing oracle; the cost of
    # caring is one import.
    if not token or not secrets.compare_digest(token, expected):
        raise HTTPException(status_code=401, detail="bad or missing X-Watch-Token")


@app.post("/api/watch/run", status_code=202)
async def watch_run(
    response: Response,
    force: bool = False,
    only: str | None = None,
    x_watch_token: str | None = Header(default=None),
) -> dict:
    """Triggers a sweep and returns immediately. The asynchronous path.

    A sweep is minutes of real Gemini reasoning and real ClickHouse round
    trips. Cloud Scheduler gives an HTTP target 30 minutes at most and treats
    a slow reply as a failure worth retrying, and retrying a sweep on top of
    itself doubles the load precisely when it is already slow. So the work is
    handed to a background task and the caller gets 202 Accepted about a
    millisecond later — the findings land in ClickHouse whenever they are
    ready, and `GET /api/watch/findings` is where anyone reads them.

    `?force=true` ignores each watch's interval, `?only=<watch_id>` runs a
    single brief — both there so a demo does not have to wait an hour for a
    schedule to come round.
    """
    _authorise(x_watch_token)
    _spawn(watchtower.sweep(force=force, only=only))
    response.headers["Cache-Control"] = "no-store"
    return {
        "accepted": True,
        "detail": "sweep started; poll /api/watch/findings for results",
        "watches": [w.id for w in watchtower.WATCHES] if not only else [only],
    }


@app.get("/api/watch/findings")
def watch_findings(limit: int = 20, severity: str | None = None) -> dict:
    """What the fleet found while nobody was asking."""
    try:
        return {"findings": watchtower.findings(limit=min(limit, 100), severity=severity)}
    except Exception as exc:  # noqa: BLE001
        # Before the first sweep the table is empty, and before `apply_schema`
        # it does not exist. Neither is an error worth breaking the console
        # over — the panel simply has nothing to show yet.
        return {"findings": [], "error": f"{type(exc).__name__}: {exc}"[:200]}


@app.get("/api/watch/status")
def watch_status() -> dict:
    return watchtower.status()


@app.get("/")
def console() -> FileResponse:
    return FileResponse(WEB / "index.html")


if __name__ == "__main__":
    uvicorn.run(
        app,
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", 8080)),
    )
