# The Backlot — Architecture

## Design rationale

**One data foundation, not six.** The obvious way to build six agents for a hackathon is six independent tools, each with its own toy dataset. That's fast but it caps the ceiling of the idea: nothing one agent finds can ever relate to what another finds. The Backlot instead puts every agent against the same ClickHouse `backlot` database, so a finding in one domain (a revenue leak in `ghost_ads`) can be checked against another (`premiere_pulse`'s playback telemetry) for a shared root cause.

**`AgentTool`, not `sub_agents` — the decision the whole product rests on.** ADK offers two ways to attach a specialist to an orchestrator, and only one of them can support this product.

`sub_agents` means control *transfer*. The orchestrator emits `transfer_to_agent`, the specialist takes over the conversation, and the orchestrator is out of the loop. We built it that way first and measured what happens: asked *"what happened during the premiere in Brazil — check playback and ad revenue, do they share a root cause?"*, Control Room transferred to `premiere_pulse`, which answered the user directly with *"I do not have access to ad revenue data… You might need to consult another agent"* — and ran no queries at all. Two specialists never held the floor at the same time, so correlation was not merely unreliable, it was structurally impossible.

`AgentTool` invokes a specialist as a tool and **returns its answer to the orchestrator**, which keeps control. The same question now produces two tool calls (`premiere_pulse` and `ghost_ads`), both results in Control Room's context, and one synthesized answer naming a single root cause on `sa-east-1b` with the buffering spike and the $11.6k ad-revenue loss as its two symptoms.

If you take one architectural idea from this repo, take that one: for a **consult-and-synthesize** fleet, delegation must return. Control transfer is for handoff, not for correlation.

**Two model tiers, chosen deliberately, not uniformly.** `control_room` (synthesis and correlation across domains) and `chain_of_title` (multi-step financial and contract reasoning, plus a dedicated Gemini call to parse contract prose) run on Gemini 2.5 Pro. The four operational agents run on Gemini 2.5 Flash — read-mostly SQL-and-summarize work where latency matters more than the deepest reasoning tier. A real cost/latency/quality tradeoff, not an arbitrary default.

**ClickHouse used for what it's actually good at.** Every fact table is partitioned by day and ordered by `(title_id, territory, event_time)` or similar — the access pattern every agent actually uses is "this title, this territory, this time window", so that is the sort/partition key rather than an afterthought. At the target scale (1M+ `play_events`), the windowed aggregations these agents run (buffering percentiles by 15-minute bucket, fill-rate by `fill_reason`, fingerprint fan-out counts) are exactly what ClickHouse makes fast and a row-oriented OLTP database does not.

**A shared operating context.** `common/context.py` is appended to every specialist's instruction. It pins the database name, the premiere event's identity and window, and one rule that matters more than it looks: *never ask the user for an identifier you could look up*. An agent sitting on a `titles` table and a SQL tool that replies "please provide the title_id" has failed, and without this instruction they do exactly that.

## Data model

See [`clickhouse/schema.sql`](../clickhouse/schema.sql) for the full DDL.

| Table | Primary consumers | What it captures |
|---|---|---|
| `titles` | all (dimension) | catalog metadata: name, genre, release date, budget |
| `play_events` | premiere_pulse, churn_early_warning, performance_war_room, fraud_sentinel (join), chain_of_title (volume) | one row per playback session: account, device, CDN node, bitrate, buffering, watch time, drop-off |
| `ad_events` | ghost_ads, chain_of_title (revenue share) | one row per ad-pod slot: requested/filled, fill_reason, expected vs. actual revenue |
| `rights_contracts` | chain_of_title | structured royalty terms *and* the raw contract clause they were derived from |
| `royalty_ledger` | chain_of_title | what was actually paid, per contract per period |
| `fraud_signals` | fraud_sentinel | device fingerprint, geo, concurrency features per session |
| `sentiment_events` | churn_early_warning, performance_war_room | review/social/app-rating sentiment per title/territory/day |

`play_events`, `ad_events` and `fraud_signals` all key off the same `(title_id, territory, event_time)` shape by design — that is what makes cross-table, cross-agent joins a plain SQL join instead of an ETL project.

## Why the synthetic data is built the way it is

Two properties are load-bearing, and `clickhouse/verify_anomalies.py` asserts both against the live database.

**Every royalty figure is re-derivable from ClickHouse.** The payout model uses no constant an agent cannot compute for itself:

| rate_type | billable quantity | source |
|---|---|---|
| `per_stream` | `count()` | `play_events` |
| `per_minute` | `sum(watch_seconds)/60` | `play_events` |
| `revenue_share_pct` | `sum(actual_revenue_usd)` | `ad_events` |
| `flat_window` | n/a — fixed fee | contract |

An earlier version billed `per_minute` at an invented "~4 attributed minutes per stream" and `revenue_share_pct` against a magic `$0.02/stream` revenue proxy. Neither number existed anywhere the agent could reach, so the agent's arithmetic could never match the ledger and every such contract was a latent false positive. Now, when Chain of Title disagrees with the ledger, the disagreement is real.

For the same reason, `source_clause` is rendered from the same values as the structured columns. Chain of Title is instructed to read that prose through `parse_rights_clause` and reconcile it against the columns; if the two disagreed, its own contract-parsing step would contradict its own arithmetic and read to a judge as a hallucination. (An earlier version drew the escalation threshold twice from the RNG, so 6 of 7 escalation contracts stated a threshold in prose that differed from the column.)

**The anomalies sit in a realistic background.** Detection has to be a discrimination problem:

- **Finite subscriber base.** ~125k accounts across 1M sessions (~8 each), not one new user per row. Retention and fan-out analysis are meaningless if a `user_id` never recurs.
- **Legitimate device sharing.** Households collide naturally onto shared fingerprints, plus a handful of public/venue devices with 6–13 accounts each and nothing else wrong. Account fan-out alone must not be enough to flag fraud — only the ring shows fan-out *and* impossible travel *and* concurrency together.
- **Coherent geography.** An account has a home market and mostly watches from it; ~5% travel and ~3% VPN produce a ~7% geo-mismatch baseline. Without this the session territory is independent of the account's home country, ~90% of rows look like international travel, and the geo signal is worthless because mismatching is the norm.
- **Partial CDN failure.** ~72% of eligible in-window sessions land on the failing node, so healthy traffic and four other `fill_reason` values coexist in the same window. Finding the incident means isolating a node, not just picking a time range.
- **Honest payments drift.** Correct payments carry ~0.02% rounding/FX noise instead of matching to the exact cent, so the agent's $50 materiality threshold has to actually do work.
- **Titles respect their release dates.** No title accumulates plays before it exists — which also keeps `churn_early_warning`'s "days since release" arithmetic meaningful.

## Evaluation

`eval/build_evalset.py` generates an ADK eval set **from `ANOMALIES.json`**, so the expectations cannot drift out of sync with the data — regenerate the dataset and the rubrics move with it. Five cases, 23 rubrics, scored by `rubric_based_final_response_quality_v1` and `hallucinations_v1` with Gemini 2.5 Pro as judge.

Three cases score positive findings (correlation, royalty audit, fraud ranking). Two score **restraint**: no false-positive royalty discrepancies, and no invented incident for a title/territory where nothing happened. An agent fleet that finds a crisis everywhere is worse than useless in an ops setting, and nothing else in the suite would catch that failure mode.

## Serving

`server.py` runs one FastAPI process that serves both faces of the system:

- `/` — the **Control Room console** (`web/index.html`): the six specialists as live status indicators, preset investigation scenarios, and for every answer an expandable trace of which specialists were consulted and the exact SQL each one ran against ClickHouse. The correlation claim is the product's whole thesis, so it has to be visible, not just asserted in a README.
- `/adk` — the complete ADK API, including its developer UI at `/adk/dev-ui/` for raw event traces.
- `/api/health` — liveness. NOT `/healthz`: Google Front End intercepts that exact path on Cloud Run and returns its own 404 before the request reaches the app.
- `/api/watch/*` — the Watchtower. `POST /api/watch/run` triggers a sweep, `GET /api/watch/findings` reads what previous sweeps concluded, `GET /api/watch/status` reports each watch's cadence and health.

## The unattended path

`common/watchtower.py` is the only code in this repo that reaches the agents with no user in the call stack. Four standing briefs run against the same `control_room` orchestrator on a schedule; each finding is triaged by the orchestrator into `alert` / `notice` / `clear`, written to `backlot.watch_findings`, and read back by the console on load.

Three decisions are worth recording, because each was forced by something that went wrong:

- **Cloud Scheduler, not an in-process loop.** Cloud Run freezes an idle instance's CPU and scales to zero, so a `while True: sleep` scheduler inside the container stops running under exactly the conditions an unattended watch exists to cover. `WATCH_INTERVAL_MIN` still starts an in-process loop, but only so a laptop can demonstrate the behaviour without any GCP setup — it is not the production trigger.
- **`202 Accepted`, not a held connection.** An investigation is minutes of Gemini reasoning and ClickHouse round trips. Cloud Scheduler treats a slow reply as a failure worth retrying, and a retried sweep landing on top of a running one doubles Gemini load precisely when it is already slow. The endpoint hands the work to a background task and answers immediately; a module-level `set` holds the task, because the event loop keeps only a weak reference to a bare `asyncio.create_task` and the collector will otherwise cancel a sweep mid-investigation.
- **Verify the fleet actually ran, then retry once.** The first live sweep found the seeded Brazil incident correctly but reported ad revenue as unknown: Gemini had emitted a malformed function call for `ghost_ads`, so the specialist was recorded as *consulted* and never answered. Interactively a human just asks again. Unattended, nobody does — so each `Watch` declares the specialists it cannot do without, the trace is checked for a `reply` from each after the run, and a hollow investigation is repeated once. A second failure is reported rather than hidden: a watch that quietly covers half its domain is worse than one that says so.

## Deployment

- `Dockerfile` packages `orchestrator/`, `agents/`, `common/`, `web/` and `server.py`, and sets `GOOGLE_GENAI_USE_VERTEXAI=TRUE`. Without that variable the ADK agents build a google-genai client against the AI Studio backend and fail on the first turn with *"No API key was provided"*, even with Vertex AI enabled and credentials present — it is the single most important line in the image.
- `common/clickhouse_toolset.py` launches the MCP server as `sys.executable -m mcp_clickhouse.main` rather than by the console-script name `mcp-clickhouse`. The bare name only resolves when the venv's `Scripts`/`bin` directory happens to be on `PATH`; when it isn't, the subprocess spawn fails, the toolset loads **zero** tools, and every agent fails later with the far less obvious `Tool 'run_query' not found`. The session timeout is raised to 60s because that server opens a TLS connection to ClickHouse Cloud during startup and ADK's 5s default expires first.
- `deploy/deploy.sh` builds and deploys to Cloud Run in `the-backlot-fleet` with 2 GiB / 2 vCPU — each agent holds its own `mcp-clickhouse` subprocess, so the fleet is heavier than a typical single-agent service — and a 600s request timeout, since a six-specialist post-mortem is a genuinely long turn.
- ClickHouse credentials come from Secret Manager at deploy time and are never committed (see `.gitignore`).
- ADK also ships `adk deploy cloud_run <agent_folder>` for a single self-contained agent folder. We use a custom image instead because Control Room imports its six specialists from sibling `agents/*` packages plus shared `common/` code, and because we serve our own console alongside the ADK API.

## Why this is one submission, not six

The hackathon evaluates "a complete product experience… not just a technical proof of concept." Six standalone agents each demonstrating one ClickHouse query would read as six proofs of concept bolted together. The shared data foundation, the correlation responsibility placed on `control_room`, and one console where you can watch six specialists being consulted on a single question are what make this one product: a studio operations command center, not a folder of demos.
