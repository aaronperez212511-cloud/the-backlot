# The Backlot — 3-minute demo video script

Record against the **deployed Control Room console**
(`https://the-backlot-203953305168.us-central1.run.app`), not localhost and not
the ADK developer UI. Two reasons: the rules ask for the project running on the
platform it was built for, and the console is the argument — it shows which
specialists were consulted and the SQL they actually ran. The ADK dev UI shows
neither.

Every beat below has been run end to end against live ClickHouse Cloud. Figures
shift when the dataset is regenerated, so **read the numbers off your screen,
not out of this file.**

---

## Read this before you record

**An investigation takes two to four minutes.** That is real Gemini reasoning
plus real ClickHouse round trips, and it will not go faster on camera. Three
investigations do not fit into a three-minute video in real time — so plan the
edit instead of discovering this while recording:

- Run each investigation **live and in full**, then **cut the waiting** in the
  edit. A jump cut between the question and the answer is normal and honest.
- Do **not** stage it: no typing the answer in by hand, no screenshots posing as
  live output. The rules require the project to work as shown, and it does.
- Leave a few seconds of the spinner in the first beat so it reads as real work,
  then cut.

**Warm everything up first.** ClickHouse Cloud auto-suspends and its first query
after idle can take ~30s; Cloud Run cold-starts too. Run one throwaway
investigation a few minutes before recording so neither happens on camera.

**Each beat names the judging criterion it serves.** All four are weighted
equally, so none of them is padding.

---

## 0:00–0:18 — Cold open  *(Potential impact)*

Screen: the Control Room console, empty, six specialists idle in the sidebar.

> *"Midnight Marquee premieres globally in five minutes. Six things can go wrong
> tonight — a rights holder underpaid, an ad slot gone blank, a bot ring watching
> for free, a region buffering out, an executive asking why, an audience quietly
> leaving. Most studios run six separate tools for these, and none of them talk
> to each other."*

## 0:18–1:05 — The incident  *(Quality of idea — the money shot)*

Click preset 01: *"What happened during the Midnight Marquee premiere in Brazil?
Check both playback health and ad revenue, and tell me whether they share a root
cause."*

Let the spinner run a few seconds. Point at the sidebar as **premiere_pulse** and
**ghost_ads** light up. Cut. Then open the activity trace and scroll it — real
SQL against ClickHouse, on screen.

The answer comes back as one report:

> **Root cause** — degradation on CDN node `sa-east-1b` in Brazil, 19:00–19:30 UTC.
> **Findings** — ad revenue lost to stitch failures on that node; buffering ~9x
> baseline; drop-off ~37%.

> *"Two specialists, two domains, two symptoms — one root cause. Neither could
> have said that alone: the playback agent cannot see ad revenue, and the ads
> agent cannot see CDN telemetry. That correlation is the entire reason this is a
> fleet and not six demos."*

Say the architectural line out loud — it is the differentiator:

> *"In ADK this only works because the specialists are attached as tools that
> return their findings. As sub-agents they take over the conversation and never
> hand it back, and the orchestrator never sees two findings at once."*

## 1:05–1:45 — Chain of Title  *(Technological implementation)*

Click preset 02: *"Audit the royalty payments for Midnight Marquee. Show me the
arithmetic behind any discrepancy."*

Show it pull the raw `source_clause`, call Gemini to turn contract prose into
computable terms, then the arithmetic on screen: units at the base rate below the
threshold, units at the escalated rate above it, expected versus paid, the gap.

> *"Every number here is re-derivable from the warehouse — stream counts, watch
> minutes, attributed ad revenue. Nothing is a magic constant. That is what makes
> this forensic accounting a lawyer could follow, instead of a dashboard."*

## 1:45–2:12 — Fraud, and restraint  *(Design)*

Preset 03. One device fingerprint shared across 90 accounts, corroborated by
impossible travel and session concurrency — and note what it does **not** flag:
the legitimate multi-account households and venue devices sitting in the same
data.

> *"The ring is hiding in a realistic crowd. Fan-out alone is not fraud — it takes
> corroboration. And notice it consulted one specialist, not six: this is a
> single-domain question, and the orchestrator routes rather than firing at
> everything."*

## 2:12–2:42 — Proof, not vibes  *(Technological implementation)*

Cut to a terminal. Run `python clickhouse/verify_anomalies.py` — **20 checks**
against live ClickHouse. Then show the ADK rubric eval command.

> *"The ground truth is in the repo. This asserts every seeded anomaly against the
> live database — including that the decoys exist, so detection is not trivial.
> And ADK's rubric judge scores the fleet against 23 rubrics generated from that
> same ground-truth file. Two of them check the agents do not invent findings
> that aren't there."*

## 2:42–3:00 — Close  *(Potential impact)*

Show `design/the-backlot-architecture.png` for three seconds — the two-way arrows
between Control Room and the fleet are the whole story in one frame.

> *"Six specialists, one ClickHouse foundation, one orchestrator that connects the
> dots. Gemini 2.5 on Vertex AI, the Agent Development Kit, and the official
> ClickHouse MCP server — live, end to end. This is The Backlot."*

---

## Recording checklist

- [ ] `python clickhouse/verify_anomalies.py` → **20/20**. If it fails, the demo will too
- [ ] Warm-up investigation run a few minutes before, so no cold start on camera
- [ ] Recording against the **deployed Cloud Run URL**, not localhost
- [ ] 1080p or better; agent responses legible at full screen
- [ ] Activity trace opened at least once, with real ClickHouse SQL visible
- [ ] Waiting time cut in the edit — never staged or re-typed
- [ ] English audio, or English subtitles burned in / uploaded as a track
- [ ] Under 3:00 — only the first three minutes are judged
- [ ] Uploaded to YouTube or Vimeo as **public**, playable from an incognito window
- [ ] URL pasted into the Devpost form (see `DEVPOST.md`)
