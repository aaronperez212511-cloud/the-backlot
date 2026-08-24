"""Shared ClickHouse MCP toolset, configured from environment variables.

Every Backlot agent reads from the same `backlot` database in ClickHouse
Cloud through this one toolset. That shared substrate — not six separate
data silos — is what lets the Control Room orchestrator correlate findings
across agents (e.g. a Ghost Ads revenue leak and a Premiere Pulse buffering
spike that turn out to share a root cause).
"""
from __future__ import annotations

import os

from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters


def clickhouse_toolset(tool_filter: list[str] | None = None) -> McpToolset:
    return McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command="mcp-clickhouse",
                args=[],
                env={
                    "CLICKHOUSE_HOST": os.environ["CLICKHOUSE_HOST"],
                    "CLICKHOUSE_PORT": os.environ.get("CLICKHOUSE_PORT", "8443"),
                    "CLICKHOUSE_USER": os.environ.get("CLICKHOUSE_USER", "default"),
                    "CLICKHOUSE_PASSWORD": os.environ["CLICKHOUSE_PASSWORD"],
                    "CLICKHOUSE_SECURE": "true",
                },
            ),
        ),
        tool_filter=tool_filter or ["run_query", "list_tables", "list_databases"],
    )
