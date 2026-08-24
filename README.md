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

Six teams usually build six separate point tools for these — six data silos, six dashboards, zero correlation between them. **The Backlot is one shared ClickHouse data foundation with six specialist Gemini agents on top, coordinated by one orchestrator that can connect the dots between them.**

## The agents

| Agent | Headache it owns |
|---|---|
| [`chain_of_title`](agents/chain_of_title) | Forensic royalty reconciliation — reads raw contract clauses with Gemini, computes what each rights holder is actually owed, finds underpayments and explains why. |
| [`ghost_ads`](agents/ghost_ads) | Detects silent ad-insertion (SSAI) failures during live events and quantifies the revenue lost, in real time. |
| [`fraud_sentinel`](agents/fraud_sentinel) | Flags credential-sharing / bot rings from device-fingerprint and session-pattern anomalies. |
| [`premiere_pulse`](agents/premiere_pulse) | Live playback-health copilot for premieres — where's it breaking, for whom, right now. |
| [`performance_war_room`](agents/performance_war_room) | Exec-facing title/territory performance analytics, tied to sentiment for the "why". |
| [`churn_early_warning`](agents/churn_early_warning) | Catches a title losing its audience while there's still time to act. |

All six query the **same** `backlot` database in ClickHouse Cloud through the [official ClickHouse MCP server](https://github.com/ClickHouse/mcp-clickhouse) — no silos. [`orchestrator/control_room`](orchestrator) sits on top, routes questions to the right specialist(s), and — the actual point of building this as a fleet instead of six demos — **correlates findings across domains** when they share a root cause (see the seeded CDN incident below).

## Architecture

```
                         ┌─────────────────────────┐
                         │   Control Room (root)    │
                         │  Gemini 2.5 Pro, ADK      │
                         │  routes + correlates      │
                         └────────────┬──────────────┘
                                      │ sub_agents
        ┌───────────┬────────────┬───┴────┬─────────────┬──────────────┐
        ▼           ▼            ▼        ▼             ▼              ▼
  chain_of_title ghost_ads  fraud_sentinel premiere_pulse performance_war_room churn_early_warning
   (Gemini 2.5 Pro +          (Gemini 2.5 Flash, ClickHouse MCP toolset each)
    Contract Intelligence)
        │           │            │        │             │              │
        └───────────┴────────────┴────┬───┴─────────────┴──────────────┘
                                       ▼
                         ClickHouse Cloud — database `backlot`
             titles · play_events · ad_events · rights_contracts
                  royalty_ledger · fraud_signals · sentiment_events
```

See [docs/architecture.md](docs/architecture.md) for the full data model and design rationale.

## The seeded incident (for the demo)

`data/generate_synthetic_data.py` seeds four ground-truth anomalies into the synthetic dataset — including one CDN edge node (`sa-east-1b`, Brazil) that degrades for 15 minutes during the *Midnight Marquee* premiere, causing **both** a viewer-buffering spike (`premiere_pulse`'s finding) **and** an ad-stitching failure (`ghost_ads`'s finding) at the same place and time. Two specialists find two symptoms independently; `control_room` is what ties them to one root cause. Full ground truth: `data/generated/ANOMALIES.json`.

## Tech stack

- **Google Cloud / Gemini Enterprise Agent Builder** — [Agent Development Kit (ADK)](https://github.com/google/adk-python) for agent definition and multi-agent orchestration; Gemini 2.5 Pro/Flash as the reasoning models.
- **ClickHouse Cloud** — the shared data foundation, queried live at runtime by every agent via the official `mcp-clickhouse` MCP server (not just referenced in this README — see `common/clickhouse_toolset.py`).
- **Python 3.13**.

## Project layout

```
agents/<name>/agent.py     — one specialist Agent per headache, ClickHouse MCP-toolset attached
orchestrator/agent.py      — Control Room root agent, sub_agents = the six specialists
common/clickhouse_toolset.py — shared MCP toolset config, one place, six consumers
clickhouse/schema.sql      — the shared data model
clickhouse/load_data.py    — loads generated CSVs into ClickHouse Cloud
data/generate_synthetic_data.py — synthetic dataset + seeded anomalies + ground truth
docs/architecture.md       — design rationale, data model detail, deployment notes
```

## Setup

```bash
python -m venv .venv && source .venv/Scripts/activate   # or .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
cp .env.example .env   # fill in ClickHouse Cloud + GCP project details
```

1. Sign up for [ClickHouse Cloud](https://clickhouse.com/cloud) (hackathon credit: see the Agentic Cinema resources page) and create a service.
2. Apply the schema: `python clickhouse/apply_schema.py`
3. Generate the synthetic dataset: `python data/generate_synthetic_data.py --rows 1000000`
4. Load it: `python clickhouse/load_data.py`
5. Run the fleet locally: `adk web orchestrator` (or `adk web agents/chain_of_title` to run one specialist standalone).

## Google Cloud project

`the-backlot-fleet` — kept independent from any other project/repo of the author's.

## License

MIT — see [LICENSE](LICENSE).
