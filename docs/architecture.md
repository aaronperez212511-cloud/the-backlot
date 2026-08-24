# The Backlot — Architecture

## Design rationale

**One data foundation, not six.** The obvious way to build six agents for a hackathon is six independent tools, each with its own toy dataset. That's fast but it caps the ceiling of the idea: nothing one agent finds can ever relate to what another finds. The Backlot instead puts every agent against the same ClickHouse `backlot` database, so a finding in one domain (e.g. a revenue leak in `ghost_ads`) can be checked against another domain (`premiere_pulse`'s playback telemetry) for a shared root cause. `orchestrator/control_room` exists specifically to do that correlation — it is not a router that picks one agent and forwards the answer, it is expected to consult multiple specialists and synthesize.

**Two model tiers, chosen deliberately, not uniformly.** `control_room` (synthesis/correlation across domains) and `chain_of_title` (multi-step financial/contract reasoning, plus a dedicated Gemini call to parse contract prose) run on Gemini 2.5 Pro. The four operational agents (`ghost_ads`, `fraud_sentinel`, `premiere_pulse`, `performance_war_room`, `churn_early_warning`) run on Gemini 2.5 Flash — they're read-mostly SQL-and-summarize agents where latency matters more than the deepest reasoning tier. This is a real cost/latency/quality tradeoff, not an arbitrary default.

**ClickHouse used for what it's actually good at.** Every fact table is partitioned by day and ordered by `(title_id, territory, event_time)` or similar — the access pattern every agent actually uses is "this title, this territory, this time window," so that's the sort/partition key, not an afterthought. At the target scale (`--rows 1000000`+ for `play_events`), the windowed aggregation queries these agents run (buffering percentiles by 15-minute bucket, fill-rate by fill_reason, fingerprint fan-out counts) are exactly the kind of query ClickHouse is built to make fast that a row-oriented OLTP database would not be.

## Data model

See [`clickhouse/schema.sql`](../clickhouse/schema.sql) for the full DDL. Summary of how tables map to agents:

| Table | Primary consumers | What it captures |
|---|---|---|
| `titles` | all (dimension) | catalog metadata: name, genre, release date, budget |
| `play_events` | premiere_pulse, churn_early_warning, performance_war_room, fraud_sentinel (join), chain_of_title (stream counts) | one row per playback session: device, CDN node, bitrate, buffering, drop-off |
| `ad_events` | ghost_ads | one row per ad-pod slot: requested/filled, fill_reason, expected vs. actual revenue |
| `rights_contracts` | chain_of_title | structured royalty terms *and* the raw contract clause they were derived from |
| `royalty_ledger` | chain_of_title | what was actually paid, per contract per period |
| `fraud_signals` | fraud_sentinel | device fingerprint, geo, concurrency features per session |
| `sentiment_events` | churn_early_warning, performance_war_room | review/social/app-rating sentiment per title/territory/day |

`play_events`, `ad_events`, and `fraud_signals` all key off the same `(title_id, territory, event_time)` shape by design — that's what makes cross-table, cross-agent joins (like `ghost_ads` checking `play_events.cdn_node` for the infra context behind an ad failure) a plain SQL join instead of an ETL project.

## Agent orchestration (ADK)

- Each specialist is a `google.adk.Agent` with the shared `clickhouse_toolset()` (an `McpToolset` wired to the official `mcp-clickhouse` MCP server via stdio, configured from environment variables — see `common/clickhouse_toolset.py`) plus, for `chain_of_title` only, one custom function tool (`parse_rights_clause`) that calls Gemini directly to turn contract prose into structured, computable terms.
- `orchestrator/agent.py` defines `control_room` as an `Agent` with `sub_agents=[...]` the six specialists — ADK auto-generates delegation tools from this, so `control_room` can call any specialist directly, or several in sequence, depending on what a question actually needs.
- Every agent's `instruction` encodes a deterministic method (baseline first, then windowed comparison, then name the specific evidence) rather than "look for anomalies" — the hackathon's own framing is "a deterministic agent that resolves a real problem," and vague instructions produce non-deterministic, unverifiable output.

## Why this is one submission, not six

The hackathon rules require each submission to a partner track to be unique and coherent, evaluated on "a complete product experience... not just a technical proof of concept." Six standalone agents each demonstrating one ClickHouse query would read as six proofs of concept bolted together. The shared data foundation plus the correlation responsibility placed explicitly on `control_room` is what turns this into one product: a studio operations command center, not a folder of demos.

## Deployment

- `Dockerfile` packages the ADK app (`orchestrator/`, `agents/`, `common/`) and serves it with `adk web` on Cloud Run.
- `deploy/deploy.sh` builds and deploys to Cloud Run in `the-backlot-fleet`, giving the hackathon's required hosted URL.
- ClickHouse Cloud and Vertex AI (Gemini) credentials are supplied at deploy time as Cloud Run environment variables / secrets — never committed (see `.gitignore`).
- ADK also ships a one-line `adk deploy cloud_run <agent_folder>` for the common case of a single self-contained agent folder. We use a custom Dockerfile instead because `control_room` imports its six specialists from sibling `agents/*` packages plus the shared `common/clickhouse_toolset.py` — all three top-level packages need to ship together, which the custom image does explicitly.
