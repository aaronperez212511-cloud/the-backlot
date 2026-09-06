# The Backlot

**An agent fleet for the operational headaches a streaming studio never puts in a press release.**

Built for the [Agentic Cinema Hackathon](https://agentic-cinema.devpost.com/) — Google Cloud / Gemini Enterprise Agent Builder × **ClickHouse** partner track.

---

## The problem

Every streaming studio is bleeding money and trust in six ordinary, well-known ways at once:

1. Rights holders get underpaid because royalty math is a "black box" nobody can audit (real lawsuits, real headlines).
2. Live-event ad slots go blank silently — advertisers notice before ops does.
3. Bot rings and credential sharing quietly drain subscriber and ad revenue.
4. Premieres degrade in specific regions and nobody notices until social media does.
5. Execs ask "how's title X doing and why" and get a dashboard, not an answer.
6. Titles lose their audience for weeks before anyone flags it.

Six teams usually build six separate point tools for these — six data silos, six dashboards, zero correlation between them. **The Backlot is one shared ClickHouse data foundation with six specialist Gemini agents on top, coordinated by one orchestrator that connects the dots between them.**

## The agents

| Agent | Headache it owns |
|---|---|
| [`chain_of_title`](agents/chain_of_title) | Forensic royalty reconciliation — reads raw contract clauses with Gemini, computes what each rights holder is actually owed, finds underpayments and explains why. |
| [`ghost_ads`](agents/ghost_ads) | Detects silent ad-insertion (SSAI) failures during live events and quantifies the revenue lost, in real time. |
| [`fraud_sentinel`](agents/fraud_sentinel) | Flags credential-sharing / bot rings from device-fingerprint and session-pattern anomalies. |
| [`premiere_pulse`](agents/premiere_pulse) | Live playback-health copilot for premieres — where's it breaking, for whom, right now. |
| [`performance_war_room`](agents/performance_war_room) | Exec-facing title/territory performance analytics, tied to sentiment for the "why". |
| [`churn_early_warning`](agents/churn_early_warning) | Catches a title losing its audience while there's still time to act. |

All six query the **same** `backlot` database in ClickHouse Cloud through the [official ClickHouse MCP server](https://github.com/ClickHouse/mcp-clickhouse) — no silos. [`orchestrator/control_room`](orchestrator) sits on top and **consults several specialists on one question, then correlates their findings** when they share a root cause.

## Architecture

```
                        ┌──────────────────────────────┐
                        │  Control Room (root agent)    │
                        │  Gemini 2.5 Pro · ADK          │
                        │  consults · correlates         │
                        └───────────────┬────────────────┘
                                        │ AgentTool  (results return here)
      ┌───────────┬────────────┬────────┴───┬─────────────┬──────────────┐
      ▼           ▼            ▼            ▼             ▼              ▼
chain_of_title ghost_ads fraud_sentinel premiere_pulse performance_war_room churn_early_warning
 (Gemini 2.5 Pro +          (Gemini 2.5 Flash · ClickHouse MCP toolset each)
  Contract Intelligence)
      │           │            │            │             │              │
      └───────────┴────────────┴─────┬──────┴─────────────┴──────────────┘
                                     ▼
                       ClickHouse Cloud — database `backlot`
           titles · play_events · ad_events · rights_contracts
                royalty_ledger · fraud_signals · sentiment_events
```

Each specialist is attached to Control Room as an **`AgentTool`, not a `sub_agent`** — and that distinction is the whole product. `sub_agents` in ADK means control *transfer*: Control Room would hand the conversation to one specialist and never get it back, so it could never hold two findings at once to compare them. `AgentTool` returns each specialist's answer to the orchestrator, which is what makes cross-domain correlation possible at all. See [docs/architecture.md](docs/architecture.md).

## The Watchtower — the fleet with nobody in the room

A studio's worst night is not a business-hours event. A CDN node degrades at 03:40, ad stitching fails behind it, and a system that only answers questions finds nothing — because nobody is awake to ask one.

`common/watchtower.py` holds four **standing briefs** and runs them against the same Control Room orchestrator on a schedule, unprompted. Each finding is triaged by the orchestrator itself into `alert` / `notice` / `clear`, written to `backlot.watch_findings`, and read back by the console on load — the sidebar panel fills itself in.

| Watch | Cadence | What it stands over |
|---|---|---|
| `incident_correlation` | hourly | playback health **and** ad-insertion failures, correlated to one root cause |
| `royalty_integrity` | 3h | every contract audited for underpayment, arithmetic shown |
| `fraud_rings` | 2h | shared device fingerprints, corroborated before being called a ring |
| `audience_risk` | 4h | retention risk cross-read against title performance |

Two senses of *asynchronous* are load-bearing here, and they are different:

- **Unprompted.** A sweep is triggered by a clock, not a request. It is the only path in this repo that reaches the agents with no user in the call stack.
- **Non-blocking.** An investigation is minutes of real Gemini reasoning and real ClickHouse round trips, so `POST /api/watch/run` hands the work to a background task and returns `202 Accepted` in milliseconds. The fleet keeps working long after the caller has gone.

```bash
./deploy/schedule.sh                      # Cloud Scheduler → hourly sweeps
WATCH_INTERVAL_MIN=60 python server.py    # same behaviour locally, no GCP needed
curl -X POST "localhost:8080/api/watch/run?only=incident_correlation"
curl localhost:8080/api/watch/findings
```

Cloud Scheduler rather than a loop inside the container is deliberate: Cloud Run freezes an idle instance's CPU and scales to zero, so an in-process scheduler stops running under exactly the conditions an unattended watch exists to cover.

`design/the-backlot-flow.png` walks one investigation end to end — the two ways in, the sequenced delegation, and the correlated result — with real output from an unattended run rather than a mock-up.

## The seeded incident (for the demo)

`data/generate_synthetic_data.py` seeds four ground-truth anomalies into the dataset — including one CDN edge node (`sa-east-1b`, Brazil) that degrades for 15 minutes during the *Midnight Marquee* premiere, causing **both** a viewer-buffering spike (`premiere_pulse`'s finding) **and** an ad-stitching failure (`ghost_ads`'s finding) at the same place and time. Two specialists find two symptoms independently; `control_room` is what ties them to one root cause.

The anomalies are planted in a **realistic background**, not an empty dataset: households genuinely share devices, ~7% of sessions are watched away from the account's home market, honest royalty payments carry rounding drift, and healthy sessions continue on other nodes throughout the incident window. Finding the ring or the underpayment is a discrimination problem, not a single equality filter.

## Verify it yourself

Ground truth lives in `data/generated/ANOMALIES.json`. Two commands prove the agents are graded against something real:

```bash
python clickhouse/verify_anomalies.py
```

Runs 18 assertions against **live ClickHouse Cloud**: that each seeded anomaly is present and material, that legitimate decoys exist so detection isn't trivial, that no title has plays before its release date, that subscribers are a finite recurring population, and that both underpaid contracts reproduce to the cent from raw warehouse aggregates.

```bash
python eval/build_evalset.py
python -m google.adk.cli eval orchestrator eval/backlot.evalset.json --config_file_path eval/test_config.json
```

Scores Control Room with ADK's rubric-based LLM judge against 23 rubrics generated from that same ground-truth file — including two **negative** cases (don't report false royalty discrepancies; don't invent an incident that isn't there), because an agent that always finds something is not a useful one.

## Tech stack

- **Google Cloud / Gemini Enterprise Agent Builder** — [Agent Development Kit (ADK)](https://github.com/google/adk-python) for agent definition, `AgentTool` orchestration and rubric-based evaluation; Gemini 2.5 Pro/Flash on Vertex AI as the reasoning models.
- **ClickHouse Cloud** — the shared data foundation, queried live at runtime by every agent via the official `mcp-clickhouse` MCP server (see `common/clickhouse_toolset.py`).
- **Python 3.13**, FastAPI + Uvicorn for the Control Room console.

## Project layout

```
server.py                      — Control Room console at /, full ADK API at /adk
web/index.html                 — the operations console UI
agents/<name>/agent.py         — one specialist Agent per headache, ClickHouse MCP toolset attached
orchestrator/agent.py          — Control Room root agent, specialists attached as AgentTools
common/clickhouse_toolset.py   — shared MCP toolset config, one place, six consumers
common/context.py              — operating context every agent shares (schema, premiere, answer style)
common/watchtower.py           — standing briefs the fleet runs on a schedule, unprompted
common/trace_plugin.py         — captures every specialist's tool calls so the trail can be shown
deploy/deploy.sh               — build + deploy to Cloud Run
deploy/schedule.sh             — Cloud Scheduler job that triggers unattended sweeps
design/render_architecture.py  — the system diagram: what this is built from
design/render_flow.py          — the sequence diagram: what happens, in what order
clickhouse/schema.sql          — the shared data model
clickhouse/apply_schema.py     — applies the schema to ClickHouse Cloud
clickhouse/load_data.py        — loads generated CSVs into ClickHouse Cloud
clickhouse/verify_anomalies.py — asserts the ground truth against the live database
data/generate_synthetic_data.py — synthetic dataset + seeded anomalies + ground truth
eval/build_evalset.py          — builds the ADK evalset from ANOMALIES.json
docs/architecture.md           — design rationale, data model detail, deployment notes
```

## Setup

```bash
python -m venv .venv && source .venv/Scripts/activate   # or .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
cp .env.example .env   # fill in ClickHouse Cloud + GCP project details
gcloud auth application-default login
```

> **`GOOGLE_GENAI_USE_VERTEXAI=TRUE` is not optional.** Without it the ADK agents build a
> google-genai client against the AI Studio backend and fail on the first turn with
> *"No API key was provided"* — even with Vertex AI enabled and ADC configured.
> It ships in `.env.example`, the `Dockerfile` and `deploy/deploy.sh`.

1. Sign up for [ClickHouse Cloud](https://clickhouse.com/cloud) and create a service.
2. Apply the schema: `python clickhouse/apply_schema.py`
3. Generate the dataset: `python data/generate_synthetic_data.py --rows 1000000`
4. Load it: `python clickhouse/load_data.py`
5. Confirm it landed: `python clickhouse/verify_anomalies.py`
6. Run the console: `python server.py` → http://localhost:8080

ADK's developer UI is served alongside the console at `/adk/dev-ui/` for inspecting raw agent traces.

## Deploy

```bash
./deploy/deploy.sh
```

Builds the image and deploys to Cloud Run in `the-backlot-fleet`, with ClickHouse credentials supplied from Secret Manager and never committed.

## Google Cloud project

`the-backlot-fleet` — kept independent from any other project of the author's.

## License

MIT — see [LICENSE](LICENSE).
