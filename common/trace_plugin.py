"""Records what the fleet actually did, so the console can show it.

ADK's `/run` returns only the root agent's own events, and `AgentTool` runs
each specialist in its own invocation context — so a specialist's ClickHouse
queries never reach the parent session and are invisible to any client reading
the API. That is a problem for this product specifically: "six specialists
queried one ClickHouse database and the orchestrator correlated them" is the
entire claim, and a claim you cannot inspect is a claim a judge has to take on
faith.

This plugin hooks every tool call across every agent in the fleet, keyed by
session, so `GET /api/trace/{session_id}` can hand the console the real
sequence: which specialist Control Room consulted, and the exact SQL each one
ran against ClickHouse Cloud.
"""
from __future__ import annotations

import contextvars
import time
from collections import OrderedDict
from typing import Any, Optional

from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext

# Bounded so a long-lived Cloud Run instance cannot grow without limit.
_MAX_SESSIONS = 200
_MAX_STEPS_PER_SESSION = 400

ROOT_AGENT = "control_room"
SPECIALISTS = {
    "chain_of_title",
    "ghost_ads",
    "fraud_sentinel",
    "premiere_pulse",
    "performance_war_room",
    "churn_early_warning",
}

# AgentTool runs each specialist in a NEW session with a generated UUID, so a
# specialist's ClickHouse queries land under a session id the client has never
# seen. Control Room's own callback fires first and pins the real session here;
# everything the resulting sub-invocation does is filed against it, so one
# investigation reads as one trace.
_root_session: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "backlot_root_session", default=None
)


class FleetTrace:
    """Captures tool calls from every agent, grouped by session id.

    Attached as each agent's `before_tool_callback` rather than as an ADK
    plugin: `get_fast_api_app(extra_plugins=...)` takes plugin *names* to load
    by string, not instances, so a plugin object passed there is silently
    ignored and the trace comes back empty.
    """

    def __init__(self) -> None:
        self._traces: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
        self._last_root: Optional[str] = None

    def _record(self, session_id: str, step: dict[str, Any]) -> None:
        steps = self._traces.setdefault(session_id, [])
        if len(steps) < _MAX_STEPS_PER_SESSION:
            steps.append(step)
        self._traces.move_to_end(session_id)
        while len(self._traces) > _MAX_SESSIONS:
            self._traces.popitem(last=False)

    def trace(self, session_id: str) -> list[dict[str, Any]]:
        return self._traces.get(session_id, [])

    def keys(self) -> dict[str, int]:
        return {k: len(v) for k, v in self._traces.items()}

    def clear(self, session_id: str) -> None:
        self._traces.pop(session_id, None)

    def __call__(
        self, tool: BaseTool, args: dict[str, Any], tool_context: ToolContext
    ) -> Optional[dict[str, Any]]:
        """ADK `before_tool_callback` signature. Returning None runs the tool."""
        return self._observe(tool, args, tool_context)

    def after(
        self,
        tool: BaseTool,
        args: dict[str, Any],
        tool_context: ToolContext,
        tool_response: Any = None,
    ) -> None:
        """ADK `after_tool_callback`. Records what a specialist actually said.

        Recording only the calls turned out not to be enough: when a
        post-mortem reported "no royalty issues" while the database held two
        real underpayments, the trace showed Chain of Title running exactly the
        right queries and nothing about what it concluded from them — so there
        was no way to tell whether the specialist got it wrong or the
        orchestrator dropped its finding. Capturing the reply makes that
        answerable instead of a guess.
        """
        if tool.name not in SPECIALISTS:
            return None
        session_id = _root_session.get() or self._last_root
        if not session_id:
            return None
        text = tool_response
        if isinstance(text, dict):
            text = text.get("result", text)
        self._record(
            session_id,
            {
                "t": time.time(),
                "agent": tool.name,
                "tool": tool.name,
                "kind": "reply",
                "detail": str(text)[:2000],
            },
        )
        return None

    def _observe(
        self, tool: BaseTool, tool_args: dict[str, Any], tool_context: ToolContext
    ) -> Optional[dict[str, Any]]:
        session = getattr(tool_context, "session", None)
        session_id = getattr(session, "id", None) or session
        if not session_id:
            return None

        agent = getattr(tool_context, "agent_name", None) or "?"
        name = tool.name

        session_id = str(session_id)
        if agent == ROOT_AGENT:
            _root_session.set(session_id)
            self._last_root = session_id
        else:
            # A specialist: file under the investigation that triggered it.
            # The context var survives into the sub-invocation in the normal
            # case; _last_root covers the case where it does not.
            session_id = _root_session.get() or self._last_root or session_id

        if name in SPECIALISTS:
            kind, detail = "consult", str(tool_args.get("request", ""))[:400]
        elif name == "run_query":
            kind, detail = "query", str(tool_args.get("query", ""))[:1200]
        elif name == "parse_rights_clause":
            kind, detail = "gemini", str(tool_args.get("clause_text", ""))[:400]
        else:
            kind, detail = "tool", ""

        self._record(
            session_id,
            {"t": time.time(), "agent": agent, "tool": name, "kind": kind, "detail": detail},
        )
        return None


fleet_trace = FleetTrace()
