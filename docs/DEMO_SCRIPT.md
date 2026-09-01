# The Backlot — 3-minute demo video script

Devpost requires a demo of the project *as built*, not a cinematic trailer — but nothing stops the framing from being cinematic. Record against the **Control Room console** (`python server.py` → http://localhost:8080, or the deployed Cloud Run URL), not the ADK developer UI: the console shows the specialists lighting up and the SQL they run, which is the whole argument.

Every beat below has been run end to end against live ClickHouse Cloud. The figures are from the current dataset; regenerate and they shift slightly, so read them off the screen rather than from this file.

---

**0:00–0:20 — Cold open, the premise**
Screen: the Control Room console, empty, six specialists idle in the sidebar.
VO: *"Midnight Marquee premieres globally in five minutes. Six things can go wrong tonight — a rights holder underpaid, an ad slot gone blank, a bot ring watching for free, a region buffering out, an exec asking why, an audience quietly leaving. Most studios run six separate tools for these, and none of them talk to each other. The Backlot runs six specialists over one ClickHouse foundation — and one orchestrator whose job is to connect them."*

**0:20–1:10 — The incident, live** *(the money shot)*
Click preset 1: *"What happened during the Midnight Marquee premiere in Brazil? Check both playback health and ad revenue, and tell me whether they share a root cause."*

Point at the sidebar as `premiere_pulse` and `ghost_ads` light up, then open the activity trace to show the real SQL hitting ClickHouse. The answer comes back as one report:

> **Root cause** — playback degradation on CDN node `sa-east-1b` in Brazil, ~19:05–19:20 UTC.
> **Findings** — ~$11.6k of ad revenue lost to SSAI stitch failures; buffering ~9x baseline; drop-off 34%.

VO: *"Two specialists, two different domains, two symptoms — and one root cause. Neither agent could have said that alone: the playback agent can't see ad revenue, and the ads agent can't see CDN telemetry. That correlation is the entire reason this is a fleet and not six demos."*

Say the architectural line out loud, it's the differentiator: *"In ADK this only works because the specialists are attached as tools that return their findings — not as sub-agents that take over the conversation."*

**1:10–1:50 — Chain of Title, the flagship**
Click preset 2: *"Audit the royalty payments. Show me the arithmetic behind any discrepancy."*

Show it pulling the raw `source_clause`, calling Gemini (`parse_rights_clause`) to turn contract prose into computable terms, then the arithmetic on screen: units × base rate below the threshold, units × escalated rate above it, expected vs. paid, the gap. Two findings — an escalation tier that triggered but was paid at base rate, and a flat fee paid short.

VO: *"Every number here is re-derivable from the warehouse: stream counts, watch minutes, attributed ad revenue. Nothing is a magic constant. That's what makes this forensic accounting a lawyer could follow, not a dashboard."*

**1:50–2:20 — Fraud Sentinel + Churn**
Quick cuts. Preset 3 flags one device fingerprint shared by 90 accounts with impossible travel and session concurrency — and, importantly, does **not** flag the hundreds of legitimate multi-account households and venue devices in the same data. Then the churn finding: *Static Bloom* collapsing ~60% in watch time two weeks after release, corroborated by sentiment turning negative over the same days.

VO: *"The ring is hiding in a realistic crowd. Fan-out alone isn't fraud — it takes corroboration."*

**2:20–2:45 — Proof, not vibes**
Cut to a terminal. Run `python clickhouse/verify_anomalies.py` — 18 checks passing against live ClickHouse. Then show `eval/backlot.evalset.json` and the ADK rubric eval command.

VO: *"The ground truth is in the repo. This script asserts every seeded anomaly against the live database, including that the decoys exist so detection isn't trivial. And ADK's rubric judge scores the fleet against 23 rubrics generated from that same file — two of which check the agents DON'T invent findings that aren't there."*

**2:45–3:00 — Close**
Show the architecture diagram for two seconds.
VO: *"Six specialists, one ClickHouse foundation, one orchestrator that connects the dots. Gemini 2.5 on Vertex AI, the Agent Development Kit, and the official ClickHouse MCP server — live, end to end. This is The Backlot."*

---

## Recording checklist
- [ ] Run `python clickhouse/verify_anomalies.py` first — if anything fails, the demo will too
- [ ] Record against the Control Room console, not the ADK dev UI
- [ ] Screen record at 1080p+, agent responses legible at full screen
- [ ] English audio or English burned-in captions (submission requirement)
- [ ] Open the activity trace at least once so real ClickHouse SQL is visible on screen
- [ ] Keep it under 3:00 — only the first three minutes are judged
- [ ] Upload to YouTube/Vimeo as **public**, link it in the Devpost submission
