"""Shared ClickHouse MCP toolset, configured from environment variables.

Every Backlot agent reads from the same `backlot` database in ClickHouse
Cloud through this one toolset. That shared substrate — not six separate
data silos — is what lets the Control Room orchestrator correlate findings
across agents (e.g. a Ghost Ads revenue leak and a Premiere Pulse buffering
spike that turn out to share a root cause).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters

# `adk web` loads the repo .env itself, but nothing else does — tests, eval
# runs, verify_anomalies.py and the custom console server all import agents
# directly. Loading here means every entry point behaves the same.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

_REQUIRED = ("CLICKHOUSE_HOST", "CLICKHOUSE_PASSWORD")


def _require_env() -> None:
    missing = [k for k in _REQUIRED if not os.environ.get(k)]
    if missing:
        raise RuntimeError(
            f"Missing required environment variable(s): {', '.join(missing)}. "
            "Copy .env.example to .env and fill in your ClickHouse Cloud "
            "credentials, or set them in the deployment environment."
        )


def clickhouse_toolset(tool_filter: list[str] | None = None) -> McpToolset:
    _require_env()
    return McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                # Launch the official mcp-clickhouse server through the current
                # interpreter rather than by console-script name. The bare name
                # `mcp-clickhouse` only resolves when the venv's Scripts/bin dir
                # happens to be on PATH; when it isn't, the subprocess spawn
                # fails (WinError 2 / FileNotFoundError), the toolset silently
                # loads zero tools, and every agent then fails at call time with
                # "Tool 'run_query' not found". sys.executable always resolves.
                command=sys.executable,
                args=["-m", "mcp_clickhouse.main"],
                env={
                    "CLICKHOUSE_HOST": os.environ["CLICKHOUSE_HOST"],
                    "CLICKHOUSE_PORT": os.environ.get("CLICKHOUSE_PORT", "8443"),
                    "CLICKHOUSE_USER": os.environ.get("CLICKHOUSE_USER", "default"),
                    "CLICKHOUSE_PASSWORD": os.environ["CLICKHOUSE_PASSWORD"],
                    "CLICKHOUSE_SECURE": os.environ.get("CLICKHOUSE_SECURE", "true"),
                    "CLICKHOUSE_DATABASE": os.environ.get("CLICKHOUSE_DATABASE", "backlot"),
                    "CLICKHOUSE_MCP_SERVER_TRANSPORT": "stdio",
                },
            ),
            # mcp-clickhouse imports its dependency tree and opens a TLS
            # connection to ClickHouse Cloud at startup; the ADK default of 5s
            # is not enough and surfaces as a confusing "session not ready"
            # ConnectionError with an empty toolset.
            timeout=60.0,
        ),
        tool_filter=tool_filter or ["run_query", "list_tables", "list_databases"],
    )
