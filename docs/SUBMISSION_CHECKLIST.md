# Devpost submission checklist — Agentic Cinema / ClickHouse track

**Deadline: 9 September 2026, 2:00 PM PT.** Late submissions are disqualified outright.

## Hard requirements from the official rules

- [x] **Hosted project URL** — https://the-backlot-203953305168.us-central1.run.app (Cloud Run, `us-central1`). Verified live: a full cross-domain investigation runs against ClickHouse Cloud and Vertex AI from the deployed container. Satisfies the "must run on web" platform rule.
- [ ] **Public GitHub repo**, open-source license detectable in the "About" section. MIT `LICENSE` is in place — the repo is currently **private** and must be flipped to public before submitting.
- [ ] **Demo video**, ≤3:00, uploaded to YouTube or Vimeo and set **public**, English audio or English captions. Only the first 3 minutes are judged. Script: [`DEMO_SCRIPT.md`](DEMO_SCRIPT.md).
- [ ] **Text description** covering: features and functionality, technologies used, other data sources, and *"your findings and learnings while building"* — that last part is explicitly requested and easy to skip. Draft notes below.
- [ ] **Partner track: ClickHouse** selected on the Devpost form.
- [x] **ClickHouse used at runtime via the official `mcp-clickhouse` MCP server**, connected to ClickHouse Cloud — the track's specific requirement. Every agent loads it in `common/clickhouse_toolset.py`; `python clickhouse/verify_anomalies.py` proves the database is live and populated.
- [x] **Google Cloud AI used at runtime, imported and actually called** — `google-adk` (agents, `AgentTool` orchestration, rubric eval) and `google-genai` (contract parsing), both on Vertex AI. Accepted SDKs per the rules.
- [x] **Only Google Cloud AI tooling in the project.** No non-Google model, agent framework or AI API is used at runtime.
- [x] **New project, built during the contest period** (27 Jul – 9 Sep 2026). First commit 24 Aug 2026.
- [ ] Team ≤ 4 people, all members added on Devpost.

## Judged criteria — equally weighted, and where we stand

| Criterion | What it asks | Where we stand |
|---|---|---|
| Technological implementation | How well is it built, how effectively does it use Google Cloud and the partner service? | Six ADK agents + `AgentTool` orchestration, two deliberate model tiers, MCP toolset, ADK rubric eval, Cloud Run deploy, Cloud Scheduler driving unattended sweeps. |
| Design | A complete, coherent product experience — not a technical proof of concept | The Control Room console (`web/index.html`), not the ADK dev UI. Preset investigations, live specialist status, the actual SQL each agent ran, and a Watchtower panel that fills itself in. |
| Potential impact | Credible, specific case for solving a real problem for a real audience | Six documented industry pain points; findings are dollar-denominated and traceable to raw warehouse aggregates — and arrive before anyone asks, which is the difference between a dashboard and an operations centre. |
| Quality of idea | Creative, non-obvious use of the services; genuine understanding of the problem | One shared data foundation with cross-domain correlation, rather than six point tools. The correlation runs unprompted on a schedule. Ground truth + negative eval cases show the problem was actually thought through. |

## Findings and learnings — raw material for the write-up

The rules ask for this explicitly. The most substantive ones, all discovered by running the thing:

1. **`sub_agents` vs `AgentTool` decides whether a multi-agent product is possible at all.** With `sub_agents`, ADK *transfers control*: Control Room handed the conversation to `premiere_pulse`, which told the user "I do not have access to ad revenue data… you might need to consult another agent" and ran no queries. Cross-domain correlation wasn't unreliable — it was structurally impossible. `AgentTool` returns the specialist's finding to the orchestrator, and the same question then produces one synthesized root-cause report.
2. **`GOOGLE_GENAI_USE_VERTEXAI=TRUE` is load-bearing.** Without it ADK builds a google-genai client against the AI Studio backend and every agent fails with *"No API key was provided"* — even with Vertex AI enabled, billing active and ADC configured. The error names an API key, so it sends you looking in exactly the wrong place.
3. **Launch MCP servers via `sys.executable -m <module>`, not the console-script name.** `command="mcp-clickhouse"` only resolves when the venv's script directory is on `PATH`. When it isn't, the spawn fails, the toolset silently loads **zero** tools, and the failure surfaces much later as `Tool 'run_query' not found`. Also raise ADK's 5s session timeout: that server opens a TLS connection to ClickHouse during startup.
4. **Synthetic data has to be adversarial to itself.** Our first fraud dataset gave every session a unique user and a unique device, so the seeded ring was the only fingerprint shared by more than one account — "detection" was one equality filter against an empty haystack. Adding households, venue devices with high fan-out and nothing else wrong, and a VPN/travel baseline turned it into an actual discrimination problem.
5. **A self-contradicting schema makes a correct agent look wrong.** A per-minute contract whose escalation threshold was worded "after N *streams*" led Chain of Title to compare a minutes threshold against a stream count, find the tier untriggered, and report a genuinely underpaid contract as correctly paid. The agent's reasoning was right; the data was incoherent. Thresholds are now stated in each contract's own billing unit, and `verify_anomalies.py` asserts it.
6. **Every number an agent must reproduce has to be reachable from the warehouse.** Billing per-minute deals at an invented "~4 minutes per stream" made the agent's arithmetic permanently unable to match the ledger. Now every rate type maps to one queryable aggregate.
7. **Evaluate restraint, not just recall.** Two of the five eval cases check that the fleet does *not* report false royalty discrepancies and does *not* invent an incident for a quiet title. An agent that always finds something is worse than useless in operations, and no positive test catches that.

## Verification log

`python clickhouse/verify_anomalies.py` — 20 assertions against live ClickHouse Cloud, covering the four seeded anomalies, the realism of the background they hide in, and dataset integrity. Run it before recording; if it fails, the demo will too.

`python -m google.adk.cli eval orchestrator eval/backlot.evalset.json --config_file_path eval/test_config.json` — 5 cases, 23 rubrics generated from `ANOMALIES.json`, judged by Gemini 2.5 Pro.

## Before you submit

- [ ] Flip the GitHub repo to **public** and confirm the MIT license shows in the "About" panel. Leave real margin before 15:00 CST — GitHub's licence detection is not instant
- [x] Deploy and smoke-test the hosted URL from a logged-out browser — revision `the-backlot-00021-thd`, `/api/health` green
- [x] `./deploy/schedule.sh` — Cloud Scheduler job `backlot-watchtower` is ENABLED and firing hourly. Verified end to end: a scheduler-triggered sweep correlated a CDN failure on `us-west-2a` across playback and ad insertion with no human in the loop
- [x] Apply the schema on the deployed instance's database — `watch_findings` exists and is accumulating; the deployed service and local `.env` point at the same ClickHouse instance
- [ ] Re-run `verify_anomalies.py` against whatever data the deployed instance points at
- [ ] Record, caption and publish the video
- [ ] Decide what to do about the `Co-Authored-By` trailer — it is on **27 commits**, not just the initial one, so this is a decision about rewriting the whole history rather than amending one commit. The rules bar non-Google **AI tooling in the project**, which is about the runtime stack rather than the editor, but the trailer is a gratuitous flag in a repo that gets automated first-round screening

## Landmine found on the way to deploying, worth keeping

`google-adk`'s MCP support sits behind a bare `try: ... except ImportError` that only logs at DEBUG. When `mcp-clickhouse<1` resolved to 0.6.0 — pulling `fastmcp` 4.x and `mcp` 2.x, which ADK 2.7.1 is not built against — the import chain broke, `__all__` was left empty, and the visible error was `cannot import name 'McpToolset'`, accusing the one package that was innocent. Cloud Build went green; the revision never listened on its port.

Nothing in the repo had changed. A rebuild on any day after those releases would have done it, including a rebuild on submission day. `requirements-runtime.txt` now caps that whole chain at the versions actually verified.
