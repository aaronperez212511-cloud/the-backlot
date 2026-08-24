# The Backlot — 3-minute demo video script

Devpost requires a demo of the project *as built*, not a cinematic trailer — but nothing stops the framing from being cinematic. Suggested beats:

**0:00–0:20 — Cold open, the premise**
Screen: Control Room chat UI, empty.
VO: "Midnight Marquee premieres globally in five minutes. Six things can go wrong tonight — a rights holder can get underpaid, an ad slot can go blank, a bot ring can be watching for free, a region can buffer out, an exec can ask why, and nobody will notice until it's too late. The Backlot is the one team that's watching all six at once."

**0:20–1:00 — The incident, live**
Ask Control Room: *"Give me a status check on the Midnight Marquee premiere."*
Show it consulting `premiere_pulse` and `ghost_ads`, then synthesizing: a buffering spike AND an ad-stitch failure, same territory, same CDN node, same 15-minute window — one root cause, two symptoms. This is the "why a fleet, not six demos" moment — say it out loud.

**1:00–1:40 — Chain of Title, the flagship**
Ask: *"Audit royalty payments for Midnight Marquee."*
Show `chain_of_title` pulling a raw contract clause, calling Gemini (`parse_rights_clause`) to turn prose into computable terms on screen, then showing the arithmetic: expected vs. paid, dollar gap, root cause ("escalation clause was ignored"). Land the line: "This is forensic accounting a lawyer would recognize, not a dashboard."

**1:40–2:10 — Fraud Sentinel + Churn**
Quick cuts: fraud ring flagged (one device fingerprint, dozens of accounts, impossible travel) → Static Bloom's week-2 collapse in watch time, corroborated by sentiment.

**2:10–2:40 — Performance War Room, the exec view**
Ask: *"Give me the weekend performance digest."*
Show the ranked, budget-aware synthesis across titles.

**2:40–3:00 — Close**
Show the architecture diagram from the README for two seconds. VO: "Six agents, one ClickHouse foundation, one orchestrator that connects the dots. Built on Gemini Enterprise Agent Builder and ClickHouse Cloud, live, end to end. This is The Backlot."

## Recording checklist
- [ ] Screen record at 1080p+, agent responses visible and legible
- [ ] English audio or English burned-in captions (submission requirement)
- [ ] Show real ClickHouse queries running (not just the chat answer) at least once
- [ ] Upload to YouTube/Vimeo as public, link in Devpost submission
