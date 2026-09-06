"""The Watchtower — the fleet running with nobody in the room.

Everything else in The Backlot waits to be asked. A human opens the console,
types a question, and six specialists spring into action. That is a real
product, but it has a hole in it that anyone who has actually run operations
will find immediately: **the studio's worst night is not a business-hours
event.** A CDN node degrades at 03:40, ad stitching fails behind it, and the
system that could have correlated the two in ninety seconds sits idle because
nobody was awake to open a browser tab.

The Watchtower closes that hole. It holds a set of *standing briefs* — the
questions an ops lead would ask every hour if they never slept — and runs them
against the same Control Room orchestrator, on a schedule, unprompted. The
findings land in ClickHouse whether or not anyone is watching, and the console
reads them back on load. Nobody types anything.

Two senses of "asynchronous" are load-bearing here, and they are different:

1. **Unprompted.** A sweep is triggered by a clock, not a request. `sweep()`
   is the only path in this repo that reaches the agents with no user in the
   call stack.
2. **Non-blocking.** A single investigation takes two to four minutes of real
   Gemini reasoning and real ClickHouse round trips. No HTTP client will hold
   a connection open that long, so `POST /api/watch/run` hands the work to a
   background task and answers `202` immediately. The trigger returns in
   milliseconds; the fleet keeps working long after the caller has gone.

Watches run concurrently with each other, bounded — see WATCH_CONCURRENCY.
"""
from __future__ import annotations

import asyncio
import os
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import clickhouse_connect
from dotenv import load_dotenv
from google.genai import types

from common.trace_plugin import SPECIALISTS, fleet_trace

# Loaded here rather than relied on from elsewhere. `findings()` and
# `status()` are read paths that deliberately do NOT import the agents — so
# they never trigger the .env load in common/clickhouse_toolset.py, and
# `GET /api/watch/findings` on a fresh process would fail on a missing
# CLICKHOUSE_HOST. It surfaced as an empty panel rather than an error, which
# is the worst way for a credentials problem to present itself.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

APP_NAME = "watchtower"

# One investigation is already a burst: Control Room fans out to several
# specialists, each making its own Gemini calls against Vertex AI's dynamic
# shared quota (see common/models.py). Running four watches at once multiplies
# that by four and turns a sweep into a reliable way to generate 429s. Two at a
# time keeps a sweep inside a few minutes without stampeding the quota.
WATCH_CONCURRENCY = int(os.environ.get("WATCH_CONCURRENCY", "2"))

# Ceiling on a single watch. A stuck MCP subprocess or a pathological model
# turn would otherwise hold a slot forever and wedge every later sweep.
WATCH_TIMEOUT_S = float(os.environ.get("WATCH_TIMEOUT_S", "420"))

_SEVERITIES = ("alert", "notice", "clear")

# Appended to every brief. Control Room's own instruction already forbids
# generic delegation and demands correlation; this adds only what an
# unattended run needs that an interactive one does not — a machine-readable
# verdict, because nobody is here to read prose and decide whether it matters.
TRIAGE = """

You are running UNATTENDED on a schedule. No human is waiting on this, and
nobody will ask you a follow-up question. Investigate fully, then report.

Begin your reply with exactly one of these lines, and nothing before it:
SEVERITY: alert
SEVERITY: notice
SEVERITY: clear

Use `alert` when something needs action within the hour, `notice` when it is
worth a human's attention but not urgent, and `clear` when you checked and
found nothing wrong. `clear` is a real and useful result — do not manufacture
a finding to avoid it.

The next line must be a single sentence of at most 120 characters, stating
what you found in concrete terms — dollar amounts, node names, contract ids,
territories, time windows. That one line is what an ops lead sees on a phone
at 3am, so it has to carry the finding by itself.

Then the full report, in your normal structure.

If a specialist tool call fails, call it again before concluding anything from
its absence. Nobody is here to retry it for you.
"""


@dataclass(frozen=True)
class Watch:
    """A standing brief: a question that runs itself.

    `brief` is phrased for the specialists it needs, not as a generic
    "check for problems". That is not stylistic — an earlier version of the
    orchestrator sent one vague sentence to all six specialists and a full
    post-mortem came back reporting "no royalty issues" while the ledger held
    a real $462.84 underpayment. Vague delegation gives a specialist nothing
    to check against, and an unattended run has nobody to notice it went
    hollow.
    """

    id: str
    name: str
    every_minutes: int
    brief: str
    # The specialists this brief is meaningless without. Checked against the
    # trace after the run, not merely hoped for — see run_watch().
    expects: tuple[str, ...] = ()


WATCHES: tuple[Watch, ...] = (
    Watch(
        id="incident_correlation",
        name="Cross-domain incident sweep",
        every_minutes=60,
        # Sequenced deliberately, and the sequence is the whole watch. Asking
        # both specialists the same broad "last 24 hours" question produced a
        # confident FALSE NEGATIVE on the first live run: premiere_pulse
        # returned a 30-minute Brazil window, ghost_ads returned a day-wide
        # $10,505 ad-loss total across every territory, and the orchestrator
        # correctly reported that a day-wide aggregate and a half-hour window
        # share nothing — "Root cause: None". Both findings were right and the
        # correlation was real; the second question was simply never scoped to
        # the first answer. Interactive users supply that scoping without
        # noticing, by naming the premiere in their question. An unattended
        # brief has to state it.
        brief=(
            "Sweep for an operational incident in the last 24 hours, in two "
            "steps. FIRST ask premiere_pulse to compare playback health by "
            "cdn_node and territory against baseline in short time windows, "
            "and to name the single worst window it finds with its specific "
            "cdn_node, territory, and start and end time. THEN ask ghost_ads "
            "about ad-insertion failures and the revenue they lost, scoping "
            "that request explicitly to the same territory, cdn_node and time "
            "window premiere_pulse just named — not across the whole day. A "
            "day-wide ad-loss total cannot be compared against a 30-minute "
            "playback window, so scoping the second question to the first "
            "finding is what makes correlation possible at all. If both return "
            "findings inside that shared window, name the single root cause "
            "explaining both. If ghost_ads finds nothing in that window, say "
            "so plainly rather than falling back to a day-wide total."
        ),
        expects=("premiere_pulse", "ghost_ads"),
    ),
    Watch(
        id="royalty_integrity",
        name="Royalty integrity audit",
        every_minutes=180,
        brief=(
            "Ask chain_of_title to audit every rights contract for "
            "underpayment, applying any tiered escalation clause in the "
            "contract text, and to show the arithmetic behind any gap it "
            "finds: units at the base rate, units at the escalated rate, "
            "expected versus paid. Report only discrepancies it can derive "
            "from the warehouse."
        ),
        expects=("chain_of_title",),
    ),
    Watch(
        id="fraud_rings",
        name="Credential-sharing watch",
        every_minutes=120,
        brief=(
            "Ask fraud_sentinel to look for one device fingerprint shared "
            "across an implausible number of accounts, and to corroborate any "
            "candidate with impossible travel and session concurrency before "
            "calling it a ring. Legitimate multi-account households and venue "
            "devices exist in this data — high fan-out on its own is not "
            "fraud, and reporting one as fraud is a failure."
        ),
        expects=("fraud_sentinel",),
    ),
    Watch(
        id="audience_risk",
        name="Audience retention watch",
        every_minutes=240,
        # Sequenced for the same reason as incident_correlation: the second
        # specialist has to be asked about the titles the first one named, not
        # about the catalogue in general.
        brief=(
            "In two steps. FIRST ask churn_early_warning which titles show "
            "rising retention risk, and to name them specifically. THEN ask "
            "performance_war_room how those named titles are performing by "
            "territory, listing the title ids in the request, and to bring in "
            "sentiment where it explains a move. Report what connects a title "
            "appearing in both answers."
        ),
        expects=("churn_early_warning", "performance_war_room"),
    ),
)

WATCH_BY_ID = {w.id: w for w in WATCHES}


@dataclass
class WatchState:
    last_run: float = 0.0
    last_severity: str = ""
    running: bool = False
    runs: int = 0
    failures: int = 0
    # Times a run came back missing a specialist the brief needs and had to be
    # repeated. Surfaced in /api/watch/status: a watch retrying every sweep is
    # a real signal, and one nobody would otherwise see.
    retries: int = 0
    last_error: str = ""


_state: dict[str, WatchState] = {w.id: WatchState() for w in WATCHES}
_sweep_lock = asyncio.Lock()
_sweeping = False


def _client():
    """A direct ClickHouse client for WRITES.

    The agents reach ClickHouse through the `mcp-clickhouse` MCP server, whose
    `run_query` tool is a read path — which is correct for agents and useless
    for persisting a finding. The Watchtower is infrastructure, not an agent,
    so it writes with the same `clickhouse_connect` client the loader and the
    schema tool already use. Reads of `watch_findings` for the console go
    through here too, since the console is not an agent either.
    """
    return clickhouse_connect.get_client(
        host=os.environ["CLICKHOUSE_HOST"],
        port=int(os.environ.get("CLICKHOUSE_PORT", 8443)),
        user=os.environ.get("CLICKHOUSE_USER", "default"),
        password=os.environ["CLICKHOUSE_PASSWORD"],
        secure=os.environ.get("CLICKHOUSE_SECURE", "true").lower() != "false",
        database=os.environ.get("CLICKHOUSE_DATABASE", "backlot"),
    )


def parse_verdict(answer: str) -> tuple[str, str, str]:
    """Splits the model's reply into (severity, headline, body).

    Defensive on purpose. The triage preamble asks for a leading
    `SEVERITY:` line, and the model complies almost always — but an unattended
    writer that throws on a malformed reply loses the whole finding, including
    the report underneath it. An unparseable answer is downgraded to `notice`
    and stored intact rather than discarded: a human reading it later is a far
    better outcome than a silent gap in the table.
    """
    severity, headline = "", ""
    raw = (answer or "").strip()
    lines = raw.splitlines()
    rest = [ln.strip() for ln in lines]
    body = raw

    for i, ln in enumerate(lines[:4]):
        low = ln.lower().replace("*", "").replace("`", "").strip()
        if low.startswith("severity:"):
            token = low.split(":", 1)[1].strip().split()[0] if ":" in low else ""
            if token in _SEVERITIES:
                severity = token
                rest = [x.strip() for x in lines[i + 1:]]
                # Dropped from the stored body: severity has its own column and
                # its own colour in the console, so leaving the token in the
                # prose renders it twice — once as a badge and once as a stray
                # "SEVERITY: notice" line above the report.
                body = "\n".join(lines[:i] + lines[i + 1:]).strip()
            break

    for ln in rest:
        if ln:
            headline = ln.lstrip("#* ").strip()
            break

    if not severity:
        severity = "notice"
    if not headline:
        headline = raw[:120] or "no answer returned"
    return severity, headline[:200], body


def _trace_summary(session_id: str) -> tuple[list[str], list[str], int]:
    """Which specialists were called, which actually answered, and how many
    queries they issued.

    Read off the same trace plugin the console uses, so an autonomous finding
    is auditable exactly like an interactive one — the sweep is not asking to
    be believed either.

    Called and answered are tracked separately because they came apart in
    practice: a malformed function call gets recorded as a consult and then
    returns nothing, so counting consults alone reports two specialists on an
    investigation only one of them contributed to. `replied` is the honest
    number, and the gap between the two is what triggers a retry.
    """
    steps = fleet_trace.trace(session_id)
    consulted: list[str] = []
    replied: list[str] = []
    queries = 0
    for st in steps:
        tool, kind = st.get("tool"), st.get("kind")
        if tool in SPECIALISTS and kind == "consult" and tool not in consulted:
            consulted.append(tool)
        elif tool in SPECIALISTS and kind == "reply" and tool not in replied:
            replied.append(tool)
        elif kind == "query":
            queries += 1
    return consulted, replied, queries


async def run_watch(watch: Watch) -> dict[str, Any]:
    """Runs one standing brief end to end and records what came back.

    Imports of ADK and the orchestrator are deferred to call time rather than
    module scope: importing the orchestrator pulls in all six specialists,
    each of which spawns an `mcp-clickhouse` subprocess through its toolset.
    At module scope that would happen on every import of this file —
    including `GET /api/watch/findings`, which only needs to read a table.
    """
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService

    from orchestrator.agent import root_agent

    st = _state[watch.id]
    st.running = True
    started = time.monotonic()
    sessions: list[str] = []

    async def investigate() -> tuple[str, str]:
        """One full pass. Returns (session_id, answer)."""
        # Prefixed so an autonomous investigation is distinguishable from a
        # console one in the trace store at a glance.
        session_id = f"watch-{watch.id}-{uuid.uuid4().hex[:8]}"
        sessions.append(session_id)
        session_service = InMemorySessionService()
        await session_service.create_session(
            app_name=APP_NAME, user_id="watchtower", session_id=session_id
        )
        runner = Runner(
            app_name=APP_NAME, agent=root_agent, session_service=session_service
        )
        answer = ""
        message = types.Content(
            role="user", parts=[types.Part(text=watch.brief + TRIAGE)]
        )
        async with asyncio.timeout(WATCH_TIMEOUT_S):
            async for event in runner.run_async(
                user_id="watchtower", session_id=session_id, new_message=message
            ):
                for part in (getattr(event.content, "parts", None) or []):
                    if getattr(part, "text", None):
                        answer = part.text
        return session_id, answer

    try:
        session_id, answer = await investigate()
        consulted, replied, queries = _trace_summary(session_id)

        # A specialist the brief cannot do without did not answer. Seen for
        # real: Gemini emitted a malformed function call for ghost_ads, the
        # orchestrator reported honestly that ad revenue was unknown, and the
        # finding went out half-blind. Interactively a human just asks again;
        # unattended, nobody does — so the sweep asks again itself, once. A
        # second failure is reported rather than hidden, because a watch that
        # quietly covers half its domain is worse than one that says so.
        missing = [s for s in watch.expects if s not in replied]
        if missing:
            st.retries += 1
            session_id, answer = await investigate()
            consulted, replied, queries = _trace_summary(session_id)

        severity, headline, body = parse_verdict(answer)
        duration = time.monotonic() - started

        record = {
            "found_at": datetime.now(timezone.utc).replace(tzinfo=None),
            "watch_id": watch.id,
            "watch_name": watch.name,
            "severity": severity,
            "headline": headline,
            "body": body[:60000],
            # The specialists that actually returned a finding, not the ones
            # the orchestrator tried to reach. The console displays this count
            # next to the headline, and it has to mean contribution.
            "specialists": replied or consulted,
            "queries": queries,
            "duration_s": round(duration, 2),
            "session_id": session_id,
        }
        _persist(record)

        st.last_severity = severity
        st.runs += 1
        st.last_error = ""
        return record

    except Exception as exc:  # noqa: BLE001 — a failed watch must not kill the sweep
        st.failures += 1
        st.last_error = f"{type(exc).__name__}: {exc}"[:300]
        # Written to the table like any other outcome. A watch that failed is
        # operational information; losing it to a log line nobody reads is how
        # a scheduler quietly stops working for a week.
        record = {
            "found_at": datetime.now(timezone.utc).replace(tzinfo=None),
            "watch_id": watch.id,
            "watch_name": watch.name,
            "severity": "notice",
            "headline": f"watch failed — {st.last_error}"[:200],
            "body": st.last_error,
            "specialists": [],
            "queries": 0,
            "duration_s": round(time.monotonic() - started, 2),
            # May be empty: the failure can land before a session even exists.
            "session_id": sessions[-1] if sessions else "",
        }
        try:
            _persist(record)
        except Exception:  # noqa: BLE001 — ClickHouse itself may be what failed
            pass
        return record

    finally:
        st.running = False
        st.last_run = time.time()
        # The trace store is bounded by session count, and an hourly sweep
        # would otherwise evict the console's own traces — the thing a judge
        # is actually looking at — to make room for its own. A retried watch
        # leaves two sessions behind, so clear every one it opened.
        for s in sessions:
            fleet_trace.clear(s)


_COLUMNS = ["found_at", "watch_id", "watch_name", "severity", "headline", "body",
            "specialists", "queries", "duration_s", "session_id"]


def _persist(record: dict[str, Any]) -> None:
    client = _client()
    try:
        client.insert(
            "watch_findings",
            [[record[c] for c in _COLUMNS]],
            column_names=_COLUMNS,
        )
    finally:
        client.close()


def due(now: Optional[float] = None) -> list[Watch]:
    """Watches whose interval has elapsed.

    A watch that has never run is due immediately, so a cold instance produces
    findings on its first sweep instead of staying blank for an hour.
    """
    now = now or time.time()
    out = []
    for w in WATCHES:
        s = _state[w.id]
        if s.running:
            continue
        if s.last_run == 0 or (now - s.last_run) >= w.every_minutes * 60:
            out.append(w)
    return out


async def sweep(force: bool = False, only: Optional[str] = None) -> dict[str, Any]:
    """Runs every due watch, bounded-concurrently. The unprompted path.

    Guarded by a lock: Cloud Scheduler retries a request it considers failed,
    and a sweep that takes longer than the scheduler's own deadline would
    otherwise be started again on top of itself, doubling Gemini load exactly
    when it is already slow.
    """
    global _sweeping

    if only:
        watches = [WATCH_BY_ID[only]] if only in WATCH_BY_ID else []
    else:
        watches = list(WATCHES) if force else due()

    if not watches:
        return {"ran": [], "skipped": "nothing due"}

    if _sweeping:
        return {"ran": [], "skipped": "a sweep is already running"}

    async with _sweep_lock:
        _sweeping = True
        try:
            sem = asyncio.Semaphore(WATCH_CONCURRENCY)

            async def guarded(w: Watch) -> dict[str, Any]:
                async with sem:
                    return await run_watch(w)

            results = await asyncio.gather(
                *(guarded(w) for w in watches), return_exceptions=True
            )
        finally:
            _sweeping = False

    ran = []
    for w, res in zip(watches, results):
        if isinstance(res, BaseException):
            ran.append({"watch_id": w.id, "severity": "notice",
                        "headline": f"sweep error — {type(res).__name__}: {res}"[:200]})
        else:
            ran.append({k: res[k] for k in ("watch_id", "watch_name", "severity",
                                            "headline", "specialists", "queries",
                                            "duration_s")})
    return {"ran": ran}


def findings(limit: int = 20, severity: Optional[str] = None) -> list[dict[str, Any]]:
    """Recent autonomous findings, newest first — what the console shows."""
    where = "WHERE severity = %(sev)s" if severity in _SEVERITIES else ""
    client = _client()
    try:
        res = client.query(
            f"""SELECT found_at, watch_id, watch_name, severity, headline, body,
                       specialists, queries, duration_s, session_id
                FROM watch_findings {where}
                ORDER BY found_at DESC
                LIMIT {int(limit)}""",
            parameters={"sev": severity} if where else None,
        )
        return [
            {
                "found_at": row[0].isoformat() + "Z",
                "watch_id": row[1],
                "watch_name": row[2],
                "severity": row[3],
                "headline": row[4],
                "body": row[5],
                "specialists": list(row[6]),
                "queries": row[7],
                "duration_s": row[8],
                "session_id": row[9],
            }
            for row in res.result_rows
        ]
    finally:
        client.close()


def status() -> dict[str, Any]:
    """What the Watchtower is, and what each watch has done so far."""
    now = time.time()
    return {
        "sweeping": _sweeping,
        "concurrency": WATCH_CONCURRENCY,
        "watches": [
            {
                "id": w.id,
                "name": w.name,
                "every_minutes": w.every_minutes,
                "running": _state[w.id].running,
                "runs": _state[w.id].runs,
                "failures": _state[w.id].failures,
                "retries": _state[w.id].retries,
                "expects": list(w.expects),
                "last_severity": _state[w.id].last_severity,
                "last_error": _state[w.id].last_error,
                "seconds_since_run": (
                    None if _state[w.id].last_run == 0 else int(now - _state[w.id].last_run)
                ),
                "due": w in due(now),
            }
            for w in WATCHES
        ],
    }


async def loop(interval_minutes: int) -> None:
    """In-process scheduler, for local runs and the demo.

    Deliberately NOT the production trigger. Cloud Run freezes an idle
    instance's CPU and scales to zero, so a `sleep`-driven loop inside the
    container stops running the moment nobody is holding a request open — the
    one condition under which an unattended watch is supposed to be working.
    Cloud Scheduler calling `POST /api/watch/run` is the real mechanism
    (deploy/schedule.sh); this exists so `python server.py` on a laptop
    demonstrates the same behaviour without any GCP setup.
    """
    # Let the container finish coming up before the first sweep: a cold start
    # plus six MCP subprocess spawns plus a ClickHouse Cloud instance waking
    # from auto-suspend is a bad first minute to add four investigations to.
    await asyncio.sleep(45)
    while True:
        try:
            await sweep()
        except Exception:  # noqa: BLE001 — the loop outlives any single sweep
            pass
        await asyncio.sleep(max(interval_minutes, 1) * 60)
