# Devpost submission checklist — Agentic Cinema / ClickHouse track

- [ ] Hosted project URL (Cloud Run, via `deploy/deploy.sh`)
- [ ] 3-minute demo video, public on YouTube/Vimeo, English audio or captions (script: `docs/DEMO_SCRIPT.md`)
- [ ] Public GitHub repo with LICENSE visible in the "About" section
- [ ] Repo demonstrates real runtime use of Google Cloud (Vertex AI/Gemini) and ClickHouse — not just mentioned in the README (it doesn't: every agent imports and calls `McpToolset`/ClickHouse at runtime, see `common/clickhouse_toolset.py`)
- [ ] Partner track selected in Devpost form: **ClickHouse**
- [ ] Devpost submission form completed
- [ ] Confirm actual deadline on https://agentic-cinema.devpost.com/rules before submitting (fetched as 2026-09-09, 2:00 PM PT — verify, don't trust this note blindly)

## Still needed from Aaron before this can go live
- [x] ClickHouse Cloud account + instance (`the-backlot` service, East US 2) → `.env` filled in
- [x] Schema applied, 1M+ play_events / 350k ad_events / 1M fraud_signals / full rights+royalty+sentiment data loaded and verified live in ClickHouse
- [ ] Confirm `GOOGLE_CLOUD_PROJECT=the-backlot-fleet` has Vertex AI access approved for the Gemini models used (2.5 Pro / 2.5 Flash)
- [ ] Record and upload the demo video
- [ ] Push the repo to GitHub (public) and add the LICENSE badge/section is auto-detected in "About"

## Data verification log (2026-08-24)
Two real bugs were found and fixed while loading the first full-scale dataset — noted here so the fixes aren't a mystery later:
1. `clickhouse/apply_schema.py` (new file) — the original inline schema loader rejected any SQL statement that *started* with a `--` comment line, which was all of them, so no tables were ever created by it. Fixed by stripping comment lines per-statement instead of discarding the whole chunk.
2. `data/generate_synthetic_data.py` — `cdn_node` was built as a fixed-width NumPy string array (inferred 9 chars from the initial values), so assigning the 10-char `"sa-east-1b"` incident node silently truncated to `"sa-east-1"`, which broke the Ghost Ads seeded anomaly (it never matched the incident node). Fixed with `dtype=object`.

All 4 seeded anomalies re-verified with live queries against ClickHouse Cloud after the fix — CDN incident (2761ms avg buffering vs ~300ms baseline on `sa-east-1b`), Ghost Ads ($15,663 lost to `ssai_stitch_fail`, now the #1 failure reason on that node/window), fraud ring (`fp-ring-77c1`: 90 users, 1 device), Chain of Title underpayments (both mechanistically reproduced from raw ClickHouse query numbers, not just asserted).
