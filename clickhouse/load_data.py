"""
Loads the CSVs from data/generated/ into a ClickHouse Cloud instance.

Requires CLICKHOUSE_HOST, CLICKHOUSE_PASSWORD (and optionally
CLICKHOUSE_USER, default 'default') in the environment or a local .env file
(see .env.example). Run clickhouse/schema.sql against the instance first.

Usage:
    python clickhouse/load_data.py
"""
from __future__ import annotations

import os
from pathlib import Path

import clickhouse_connect
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

DATA_DIR = Path(__file__).parent.parent / "data" / "generated"

TABLES = [
    "titles",
    "play_events",
    "ad_events",
    "rights_contracts",
    "royalty_ledger",
    "fraud_signals",
    "sentiment_events",
]

# Columns that must be handed to clickhouse-connect as real date/datetime
# objects, not the plain strings pandas.read_csv produces by default.
DATE_COLUMNS = {
    "titles": ["release_date"],
    "rights_contracts": ["window_start", "window_end"],
    "royalty_ledger": ["period_start", "period_end"],
}
DATETIME_COLUMNS = {
    "play_events": ["event_time"],
    "ad_events": ["event_time"],
    "royalty_ledger": ["paid_at"],
    "fraud_signals": ["event_time"],
    "sentiment_events": ["event_time"],
}


def main() -> None:
    host = os.environ["CLICKHOUSE_HOST"]
    port = int(os.environ.get("CLICKHOUSE_PORT", 8443))
    password = os.environ["CLICKHOUSE_PASSWORD"]
    user = os.environ.get("CLICKHOUSE_USER", "default")

    client = clickhouse_connect.get_client(
        host=host, port=port, user=user, password=password, secure=True, database="backlot"
    )

    for table in TABLES:
        csv_path = DATA_DIR / f"{table}.csv"
        if not csv_path.exists():
            print(f"skip {table}: {csv_path} not found (run generate_synthetic_data.py first)")
            continue
        df = pd.read_csv(csv_path)
        for col in DATE_COLUMNS.get(table, []):
            df[col] = pd.to_datetime(df[col]).dt.date
        for col in DATETIME_COLUMNS.get(table, []):
            df[col] = pd.to_datetime(df[col])
        client.insert_df(f"backlot.{table}", df)
        print(f"loaded {len(df):,} rows into backlot.{table}")


if __name__ == "__main__":
    main()
