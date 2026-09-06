# Devpost submission — field by field

Everything in English, as the rules require. Track: **ClickHouse**.
Every claim below is something the repo or the hosted URL can be checked against.

---

# 1 · Resumen del proyecto

## Nombre del proyecto  *(máx. 60)*

```
The Backlot
```

## Discurso de presentación  *(máx. 200 — este usa 198)*

Carries both claims: it runs unprompted, **and** it correlates.

```
Six Gemini specialists on one ClickHouse foundation. An orchestrator correlates them unprompted, on a schedule — because a buffering spike and a blank ad slot are often one incident in two costumes.
```

Previous version, if you would rather lead on correlation alone *(196)*:

```
Six Gemini specialists on one ClickHouse foundation, and an orchestrator that connects their findings — because a buffering spike and a blank ad slot are often the same incident wearing two costumes.
```

---

# 2 · Sobre el proyecto

> Paste the whole block below into the Markdown editor.

```markdown
## Inspiration

Somewhere in every streaming studio there is a person in rights administration
who cannot explain a royalty payment. Not because they are careless — because
the calculation lives across a contract written in prose, a stream count in a
warehouse, and a ledger that says a number with no working shown. When a rights
holder asks "why is this the amount?", the honest answer is often "I'd have to
reconstruct it."

That person has counterparts. The ad-ops engineer who learns a live slot went
blank when the advertiser disputes the invoice. The on-call streaming engineer
who finds out a region degraded from social media. The analyst asked "why did
this title drop?" who can produce a chart but not a cause.

Six people, six problems, six separate tools — and none of those tools can see
what the others see. That last part is the real problem. A buffering spike and a
blank ad slot on the same CDN node in the same fifteen minutes are not two
incidents. They are one incident wearing two costumes, and no tool built to look
at only one domain can ever say so.

## What it does

The Backlot is a studio operations command center: six specialist agents over
**one shared ClickHouse database**, coordinated by an orchestrator whose job is
correlation, not routing.

- **chain_of_title** — forensic royalty reconciliation. Reads the raw contract
  clause with Gemini, recomputes what is actually owed including tiered
  escalation, and shows the arithmetic behind any gap.
- **ghost_ads** — silent server-side ad-insertion failures, quantified in dollars
  rather than incident counts.
- **fraud_sentinel** — credential-sharing and bot rings, from device-fingerprint
  fan-out corroborated by impossible travel and session concurrency.
- **premiere_pulse** — live playback health by CDN node and time window, measured
  against a baseline instead of an absolute threshold.
- **performance_war_room** — title and territory performance, with sentiment
  brought in when the question is really "why".
- **churn_early_warning** — audience retention risk, caught while there is still
  time to act on it.

Ask what happened during a premiere and it consults the two specialists that
matter, then answers with one root cause: a degraded CDN node in Brazil that
produced **both** a buffering spike and an ad-stitching failure inside the same
window. Two symptoms, one incident.

Ask a single-domain question and it consults one specialist. It routes; it does
not fire at everything.

Every answer opens into an audit trail: which specialists were consulted, what
each was asked, what each replied, and the exact SQL each ran against ClickHouse.
Nothing about the answer has to be taken on trust.

**And it does not wait to be asked.** A studio's worst night is not a
business-hours event: a CDN node degrades at 03:40, ad stitching fails behind
it, and a system that only answers questions finds nothing because nobody is
awake to ask one. The Watchtower holds four standing briefs — the questions an
ops lead would ask every hour if they never slept — and runs them against the
same orchestrator on a schedule, unprompted. Findings land in ClickHouse with
their own severity triage, and the console reads them back on load. The panel
fills itself in.

That path is asynchronous in both senses that matter. It is triggered by a
clock rather than a request, and because an investigation is minutes of real
Gemini reasoning and real ClickHouse round trips, the trigger endpoint hands
the work to a background task and returns `202 Accepted` in milliseconds. The
fleet keeps working long after the caller has gone.

## How we built it

- **Google Agent Development Kit (ADK)** — seven agents, wired with `AgentTool`
  rather than `sub_agents`. This is the decision the whole product rests on.
- **Gemini 2.5 Pro and 2.5 Flash on Vertex AI** — Pro for the orchestrator's
  cross-domain synthesis and for contract reasoning; Flash for the four
  read-mostly operational agents. A deliberate cost and latency trade rather than
  a uniform default.
- **ClickHouse Cloud**, queried at runtime by every agent through the official
  **`mcp-clickhouse` MCP server** over stdio. Seven day-partitioned MergeTree
  tables ordered by `(title_id, territory, event_time)` — the access pattern the
  agents actually use, not an afterthought.
- **A custom Control Room console** (FastAPI + vanilla JS), not the ADK
  development UI, with a server-side trace plugin that captures every
  specialist's tool calls and replies so the audit trail can exist at all.
- **Cloud Run** for the hosted deployment, with ClickHouse credentials in Secret
  Manager and Gemini reached through the runtime service account.
- **Cloud Scheduler** as the Watchtower's clock. Not a loop inside the
  container: Cloud Run freezes an idle instance's CPU and scales to zero, so an
  in-process scheduler stops running under exactly the conditions an unattended
  watch exists to cover. An external clock making a real request is the only
  trigger that survives it.

The dataset is synthetic and generated by this repository — around 1M playback
events, 350k ad events and 1M fraud signals, plus contracts, a royalty ledger and
sentiment. Four ground-truth anomalies are seeded into it and written to
`ANOMALIES.json`, so every claim the agents make can be checked against what was
actually planted.

## Challenges we ran into

**Correlation was structurally impossible, and it looked like a prompt problem.**
Built with `sub_agents`, Control Room handed the conversation to `premiere_pulse`,
which replied *"I do not have access to ad revenue data… you might need to consult
another agent"* and ran no queries at all. In ADK, `sub_agents` means control
*transfer* — the orchestrator never gets the floor back, so it can never hold two
findings at once. No amount of instruction tuning fixes that. `AgentTool` returns
the finding to the orchestrator, and the same question then produces one
synthesized root-cause report.

**A full post-mortem reported "no royalty issues" while the ledger held a real
$462.84 underpayment.** The audit trail showed Chain of Title had queried both
numbers it needed. The orchestrator had simply sent the same generic sentence to
all six specialists, and a request that vague gave it nothing to check against.
Delegation has to speak each specialist's own language.

**The MCP toolset silently loaded zero tools.** Launching the server by its
console-script name only resolves when the virtualenv's script directory is on
`PATH`. When it is not, the spawn fails quietly and the failure surfaces much
later as `Tool 'run_query' not found`. Launching via `sys.executable -m <module>`
always resolves.

**Every agent failed with "No API key was provided"** — with Vertex AI enabled,
billing active and ADC configured. ADK builds its client against the AI Studio
backend unless `GOOGLE_GENAI_USE_VERTEXAI=TRUE` is set. The error names an API
key, which sends you looking in exactly the wrong place.

**Our first fraud dataset was a needle in an empty haystack.** Every session had a
unique user and a unique device, so the seeded ring was the only fingerprint
shared by more than one account. Detection was one equality filter. That is not
detection.

**The first unattended sweep came back half-blind, and it read like a success.**
It found the seeded Brazil incident correctly — node `sa-east-1b`, buffering at
9x baseline, drop-off at 37% — and reported ad revenue as unknown, because
Gemini had emitted a malformed function call for `ghost_ads`. The specialist was
recorded as consulted and never answered. The orchestrator handled it honestly,
which is what made it dangerous: the finding was well-written, correctly severe,
and quietly missing half the correlation the watch exists to perform. When a
human is driving they notice a missing answer and ask again. Nobody is driving
here, so each watch now declares the specialists it cannot do without, the trace
is checked for an actual reply from each, and a hollow run is repeated once.

**Then the fixed sweep confidently reported the opposite of the truth.** Both
specialists ran, seven ClickHouse queries between them, and the verdict came
back *"Root cause: None. The two findings do not share a time window, territory
or underlying infrastructure."* Both specialists were right. `premiere_pulse`
returned a 30-minute window in Brazil; `ghost_ads` returned a day-wide $10,505
ad-loss total across every territory, because the brief had asked both of them
the same broad "last 24 hours" question. A day-wide aggregate and a half-hour
window genuinely share nothing, so the orchestrator's reasoning was sound and
its conclusion was wrong. Correlation needs delegation to be **sequenced**, not
merely specific: ask the first specialist for the window, then scope the second
question to the window it named. An interactive user supplies that scoping
without noticing, just by mentioning the premiere in their question — which is
exactly why it survived so long in a system that had only ever been driven by
hand.

## Accomplishments that we're proud of

**The correlation genuinely works, and it is visible.** Two specialists find two
symptoms independently, and the orchestrator names one cause — with the shared
node, territory and time window that prove it, and the SQL behind each number
one click away.

**Every royalty figure is re-derivable from the warehouse.** An earlier version
billed per-minute contracts at an invented "~4 minutes per stream". That constant
existed nowhere the agent could reach, so its arithmetic could never match the
ledger and every such contract was a latent false positive. Now each rate type
maps to one queryable aggregate — so when Chain of Title disagrees with the
ledger, the disagreement is real.

**The anomalies hide in a realistic crowd.** Households sharing devices, venue
devices with high account fan-out and nothing else wrong, a VPN and travel
baseline, honest payments carrying rounding drift. Detection is a discrimination
problem, not a filter.

**We test for restraint, not just recall.** Two of the five evaluation cases check
that the fleet does *not* invent a royalty discrepancy and does *not* find an
incident in a quiet title. An agent that always finds something is worse than
useless in operations, and no positive test catches that.

## What we learned

That the interesting failures in a multi-agent system are architectural, not
conversational. Five of the six hardest bugs — control transfer, generic
delegation, the silent toolset, the half-blind sweep, the unsequenced
correlation — produced *plausible-looking output* rather than errors. A specialist politely saying "you might need to consult another agent"
reads like a reasonable answer, and reports "no issues found" read like good
news. Without a trace showing which agents ran and what SQL they issued, we would
have shipped a system that looked like it worked.

Taking the human out of the loop multiplies that. Every one of those failures was
caught because somebody was sitting there reading the answer and found it
suspicious. An agent running on a schedule has no such reader, so the checks a
human performs by instinct — did the specialist I needed actually answer? — have
to become code, or the system degrades silently and on a timer.

We also learned that synthetic data has to be adversarial to itself, and that a
self-contradicting schema makes a correct agent look wrong: a per-minute contract
whose escalation threshold was worded "after N *streams*" led Chain of Title to
compare minutes against a stream count and report a genuinely underpaid contract
as correctly paid. Its reasoning was right. The data was incoherent.

## What's next for The Backlot

Streaming the audit trail as it happens rather than after the answer. Pushing an
`alert`-severity finding to where an ops lead actually is at 3am — the
Watchtower already triages its own findings, so the missing piece is a channel,
not a judgement. And a seventh agent for licensing and acquisition decisions —
which title to renew, which to let go — because it fits the same shared
foundation without breaking it.
```

---

# 3 · Construido con  *(etiquetas)*

```
google-adk, gemini, gemini-2.5-pro, gemini-2.5-flash, vertex-ai, google-cloud,
cloud-run, cloud-build, cloud-scheduler, secret-manager, clickhouse,
clickhouse-cloud, mcp, model-context-protocol, mcp-clickhouse, python, fastapi,
uvicorn, asyncio, javascript, sql, multi-agent, agentic-ai
```

# 4 · Enlaces para "Pruébalo"

| | |
|---|---|
| Live demo | `https://the-backlot-203953305168.us-central1.run.app` |
| GitHub | `https://github.com/aaronperez212511-cloud/the-backlot` |

# 4b · Galería de imágenes

Devpost recommends 3:2. All four are generated by this repository and exported
at 3840px wide, so they hold up when a judge opens one full screen.

| Order | File | Why it earns the slot |
|---|---|---|
| 1 | `design/gallery-1-identity.png` | The fleet at a glance — six specialists, one command center |
| 2 | `design/the-backlot-flow.png` | How one investigation runs, step by step, ending in a real correlated result |
| 3 | `design/the-backlot-architecture.png` | The system, with the two-way AgentTool arrows that make correlation possible |
| 4 | `design/aurum-reflex-plate-vi.png` | The identity plate |

Lead with identity, then the walkthrough. A judge who opens only the first two
images should already understand what the system does and that it runs itself.

# 5 · Enlace a la demostración en vídeo

*(pendiente — YouTube/Vimeo, público, ≤3:00, inglés o subtítulos en inglés)*

---

# 6 · Información adicional  *(solo jueces)*

| Campo | Respuesta |
|---|---|
| Tipo de remitente | **Individual** |
| Nombre de la organización | `N/A` |
| ¿Empleado del gobierno? | *(responde tú — presumo **No**)* |
| País de residencia | **Mexico** |
| Provincia de Canadá | `N/A` |
| ¿Proyecto nuevo o preexistente? | **New** — primer commit 24 ago 2026, dentro del periodo |
| Programa de socios | **ClickHouse** |
| Personas en el equipo | **1** |
| URL repositorio open source | `https://github.com/aaronperez212511-cloud/the-backlot` |
| URL proyecto alojado | `https://the-backlot-203953305168.us-central1.run.app` |

## ¿Qué productos de Google Cloud utilizaste?

```
Vertex AI — Gemini 2.5 Pro and Gemini 2.5 Flash, called at runtime by every
agent through the google-genai SDK.

Agent Development Kit (google-adk) — all seven agents, the AgentTool
orchestration between them, and the rubric evaluation harness.

Cloud Run — hosts the Control Room console and the ADK API server.

Cloud Build — builds the container image from the repository Dockerfile.

Cloud Scheduler — the Watchtower's clock. Calls POST /api/watch/run hourly so
the fleet investigates unprompted, with no human in the loop.

Secret Manager — stores the ClickHouse Cloud credentials, mounted into the
Cloud Run service at deploy time.

Container Registry (gcr.io) — stores the built image.

IAM — a dedicated runtime service account with aiplatform.user and
secretmanager.secretAccessor.
```

## Enumere todas las demás herramientas o productos

```
ClickHouse Cloud — the shared data foundation. Seven day-partitioned MergeTree
tables; every agent queries it at runtime.

mcp-clickhouse — ClickHouse's official Model Context Protocol server, run as a
stdio subprocess. This is how the agents reach the database; it is not
referenced only in the README.

Model Context Protocol (MCP) — the transport between the agents and ClickHouse.

Python 3.13, FastAPI, Uvicorn — the Control Room console and its API.

pandas, NumPy, clickhouse-connect — synthetic data generation and loading.

Pillow — generation of the brand assets and the architecture diagram.

Pinyon Script and Caveat (SIL Open Font License 1.1) — typography, vendored
with their licences.
```

## ¿Primera vez que utilizas...?

Answer each honestly from your own history. One factual note so you are not
guessing: **you used ClickHouse for the first time in a previous project a few
weeks ago**, so for ClickHouse the truthful answer is *no*. IBM, Grafana,
Parallel and Replit are yours to answer — we used none of them here.

---

# 7 · Antes de enviar

- [ ] Repo **público**, licencia MIT visible en el panel *About* de GitHub
- [ ] URL alojada abierta desde un navegador sin sesión
- [ ] `python clickhouse/verify_anomalies.py` → 20/20
- [ ] Vídeo público y reproducible en incógnito
- [ ] Casilla de Términos y Condiciones marcada
- [ ] **Cierre: 9 sep 2026, 2:00 PM PT = 21:00 UTC = 3:00 PM Ciudad de México**
