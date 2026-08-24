"""Applies clickhouse/schema.sql to a ClickHouse Cloud instance.

Requires CLICKHOUSE_HOST, CLICKHOUSE_PASSWORD (and optionally
CLICKHOUSE_PORT, CLICKHOUSE_USER) in the environment or .env.

Usage:
    python clickhouse/apply_schema.py
"""
from __future__ import annotations

import os
from pathlib import Path

import clickhouse_connect
from dotenv import load_dotenv

load_dotenv()

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def statements(sql: str):
    """Splits schema.sql on ';', stripping full-line '--' comments from each
    chunk (rather than discarding a whole statement just because it's
    preceded by a comment line)."""
    for raw_chunk in sql.split(";"):
        lines = [line for line in raw_chunk.splitlines() if not line.strip().startswith("--")]
        stmt = "\n".join(lines).strip()
        if stmt:
            yield stmt


def main() -> None:
    client = clickhouse_connect.get_client(
        host=os.environ["CLICKHOUSE_HOST"],
        port=int(os.environ.get("CLICKHOUSE_PORT", 8443)),
        user=os.environ.get("CLICKHOUSE_USER", "default"),
        password=os.environ["CLICKHOUSE_PASSWORD"],
        secure=True,
    )
    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    for stmt in statements(sql):
        client.command(stmt)
        print("OK:", stmt.splitlines()[0][:60])

    tables = client.query("SHOW TABLES FROM backlot")
    print("Tables:", sorted(row[0] for row in tables.result_rows))


if __name__ == "__main__":
    main()
