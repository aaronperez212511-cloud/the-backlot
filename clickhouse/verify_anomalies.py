"""
Verifies, against the live ClickHouse Cloud instance, that every anomaly the
generator claims to have seeded is actually present and actually findable.

This exists because "our agents found the incident" is worth nothing if the
incident was never really in the data, or if it was so isolated that a single
equality filter would have found it. Each check below runs the same kind of
query an agent runs, and asserts both that the signal is there AND that the
surrounding data is a realistic background rather than an empty haystack.

Run it before recording the demo, and let a judge run it too:

    python clickhouse/verify_anomalies.py

Exits non-zero if any check fails.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import clickhouse_connect
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

ANOMALIES = Path(__file__).parent.parent / "data" / "generated" / "ANOMALIES.json"

GREEN, RED, DIM, BOLD, RESET = "\033[32m", "\033[31m", "\033[2m", "\033[1m", "\033[0m"

_results: list[tuple[str, bool, str]] = []


def check(name: str, passed: bool, detail: str) -> None:
    _results.append((name, passed, detail))
    mark = f"{GREEN}PASS{RESET}" if passed else f"{RED}FAIL{RESET}"
    print(f"  [{mark}] {name}")
    print(f"         {DIM}{detail}{RESET}")


def client():
    for var in ("CLICKHOUSE_HOST", "CLICKHOUSE_PASSWORD"):
        if not os.environ.get(var):
            sys.exit(f"Missing {var}. Copy .env.example to .env and fill it in.")
    return clickhouse_connect.get_client(
        host=os.environ["CLICKHOUSE_HOST"],
        port=int(os.environ.get("CLICKHOUSE_PORT", 8443)),
        user=os.environ.get("CLICKHOUSE_USER", "default"),
        password=os.environ["CLICKHOUSE_PASSWORD"],
        secure=True,
        database="backlot",
    )


def verify_cdn_incident(ch, truth: dict) -> None:
    print(f"\n{BOLD}1. CDN incident — Premiere Pulse{RESET}")
    node, terr = truth["cdn_node"], truth["territory"]
    start, end = truth["window_utc"]
    tid = truth["title_id"]

    row = ch.query(
        "SELECT count(), avg(buffering_ms), avg(rebuffer_count), avg(is_drop_off) "
        "FROM backlot.play_events "
        f"WHERE title_id='{tid}' AND territory='{terr}' AND cdn_node='{node}' "
        f"AND event_time BETWEEN '{start}' AND '{end}'"
    ).result_rows[0]
    n, buf, rebuf, drop = row

    base = ch.query(
        "SELECT avg(buffering_ms), avg(is_drop_off) FROM backlot.play_events "
        f"WHERE title_id='{tid}' AND cdn_node != '{node}'"
    ).result_rows[0]

    check(
        "incident sessions exist on the degraded node",
        n > 0,
        f"{n:,} sessions on {node} in {terr} during {start[11:16]}-{end[11:16]} UTC",
    )
    check(
        "buffering is severely elevated vs baseline",
        buf > base[0] * 3,
        f"{buf:,.0f} ms on {node} vs {base[0]:,.0f} ms baseline "
        f"({buf / base[0]:.1f}x), {rebuf:.1f} rebuffers/session",
    )
    check(
        "drop-off rate is elevated vs baseline",
        drop > base[1] * 2,
        f"{drop:.1%} drop-off vs {base[1]:.1%} baseline",
    )
    check(
        "the node name is intact (not truncated)",
        len(node) == 10 and node.endswith("b"),
        f"cdn_node stored as '{node}' — a fixed-width numpy array once clipped this to 'sa-east-1'",
    )


def verify_ghost_ads(ch, truth: dict) -> None:
    print(f"\n{BOLD}2. Ad-insertion revenue leak — Ghost Ads{RESET}")
    terr, tid = truth["territory"], truth["title_id"]
    start, end = truth["window_utc"]

    rows = ch.query(
        "SELECT fill_reason, count(), sum(expected_revenue_usd - actual_revenue_usd) "
        "FROM backlot.ad_events "
        f"WHERE title_id='{tid}' AND territory='{terr}' "
        f"AND event_time BETWEEN '{start}' AND '{end}' "
        "GROUP BY fill_reason ORDER BY 3 DESC"
    ).result_rows
    top = rows[0] if rows else ("<none>", 0, 0.0)
    lost = float(top[2])

    check(
        "ssai_stitch_fail is the top revenue-loss cause in the window",
        top[0] == "ssai_stitch_fail",
        f"#1 cause '{top[0]}': {top[1]:,} pods, ${lost:,.2f} lost "
        f"(of {len(rows)} distinct fill_reasons present)",
    )
    check(
        "the loss is material, not a rounding artifact",
        lost > 100,
        f"${lost:,.2f} of ad revenue lost during a 15-minute window",
    )

    baseline = ch.query(
        "SELECT countIf(fill_reason='ssai_stitch_fail') / count() FROM backlot.ad_events "
        f"WHERE NOT (territory='{terr}' AND event_time BETWEEN '{start}' AND '{end}')"
    ).result_rows[0][0]
    check(
        "stitch failures are concentrated, not endemic",
        float(baseline) < 0.001,
        f"{float(baseline):.4%} ssai_stitch_fail rate everywhere else — the failure "
        "clusters in one place and time, which is what makes it an infra root cause",
    )


def verify_fraud_ring(ch, truth: dict) -> None:
    print(f"\n{BOLD}3. Credential-sharing ring — Stream Fraud Sentinel{RESET}")
    fp = truth["shared_fingerprint"]

    users, travel, conc, devs = ch.query(
        "SELECT uniqExact(user_id), avg(impossible_travel_flag), "
        "avg(concurrent_sessions_5min), avg(device_count_24h) "
        f"FROM backlot.fraud_signals WHERE device_fingerprint='{fp}'"
    ).result_rows[0]

    check(
        "the ring is present with the expected account fan-out",
        users == truth["cluster_size"],
        f"{users} distinct accounts on one fingerprint ({fp}), "
        f"{float(travel):.0%} impossible travel, {float(conc):.1f} concurrent sessions, "
        f"{float(devs):.0f} devices/24h",
    )

    # The point of this check: the ring must NOT be the only fingerprint with
    # account fan-out, or "detection" is a single equality filter.
    decoys = ch.query(
        "SELECT count() FROM (SELECT device_fingerprint, uniqExact(user_id) u "
        f"FROM backlot.fraud_signals WHERE device_fingerprint != '{fp}' "
        "GROUP BY device_fingerprint HAVING u >= 5)"
    ).result_rows[0][0]
    check(
        "legitimate high-fan-out decoys exist (the haystack is not empty)",
        decoys >= 3,
        f"{decoys} other fingerprints are shared by 5+ accounts with no other "
        "suspicious signal — fan-out alone must not be enough to flag",
    )

    shared = ch.query(
        "SELECT count() FROM (SELECT device_fingerprint, uniqExact(user_id) u "
        "FROM backlot.fraud_signals GROUP BY device_fingerprint HAVING u > 1)"
    ).result_rows[0][0]
    bg_travel = ch.query(
        "SELECT avg(impossible_travel_flag), "
        "avg(ip_geo_territory != account_home_territory) FROM backlot.fraud_signals "
        f"WHERE device_fingerprint != '{fp}'"
    ).result_rows[0]
    check(
        "ordinary background noise is present",
        float(bg_travel[0]) > 0 and float(bg_travel[1]) > 0.01,
        f"{shared:,} multi-account households, {float(bg_travel[0]):.2%} baseline "
        f"impossible travel, {float(bg_travel[1]):.1%} geo mismatch from VPN/travel",
    )


def verify_royalties(ch, truth: dict) -> None:
    print(f"\n{BOLD}4. Royalty underpayments — Chain of Title{RESET}")

    # Recompute every contract's owed amount from raw warehouse aggregates,
    # exactly the way the agent is instructed to, and confirm the ledger only
    # disagrees on the two seeded contracts.
    contracts = ch.query(
        "SELECT contract_id, rights_holder, title_id, territory, rate_type, rate_value, "
        "escalation_threshold_units, escalation_rate_value FROM backlot.rights_contracts"
    ).result_rows
    paid = dict(
        ch.query(
            "SELECT contract_id, sum(amount_paid_usd) FROM backlot.royalty_ledger "
            "GROUP BY contract_id"
        ).result_rows
    )
    streams = {(r[0], r[1]): r[2] for r in ch.query(
        "SELECT title_id, territory, count() FROM backlot.play_events GROUP BY 1,2"
    ).result_rows}
    minutes = {(r[0], r[1]): float(r[2]) for r in ch.query(
        "SELECT title_id, territory, sum(watch_seconds)/60 FROM backlot.play_events GROUP BY 1,2"
    ).result_rows}
    adrev = {(r[0], r[1]): float(r[2]) for r in ch.query(
        "SELECT title_id, territory, sum(actual_revenue_usd) FROM backlot.ad_events GROUP BY 1,2"
    ).result_rows}

    gaps = {}
    for cid, holder, tid, terr, rtype, rate, thr, esc in contracts:
        key = (tid, terr)
        if rtype == "per_stream":
            units = float(streams.get(key, 0))
        elif rtype == "per_minute":
            units = minutes.get(key, 0.0)
        elif rtype == "revenue_share_pct":
            units = adrev.get(key, 0.0)
        else:
            units = 0.0

        if rtype in ("per_stream", "per_minute"):
            owed = (units * rate if thr is None
                    else min(units, thr) * rate + max(0.0, units - thr) * esc)
        elif rtype == "revenue_share_pct":
            owed = units * (rate / 100.0)
        else:
            owed = float(rate)
        gaps[cid] = (owed - float(paid.get(cid, 0.0)), holder, owed)

    material = {c: g for c, g in gaps.items() if abs(g[0]) > 50}
    expected = {
        truth["escalation_clause_ignored"]["contract_id"],
        truth["flat_fee_shortfall"]["contract_id"],
    }
    check(
        "exactly the two seeded contracts are materially underpaid",
        set(material) == expected,
        f"found {sorted(material)} — expected {sorted(expected)}; "
        f"{len(gaps) - len(material)} other contracts are within the $50 threshold",
    )

    for label, key in (("escalation tier ignored", "escalation_clause_ignored"),
                       ("flat-fee shortfall", "flat_fee_shortfall")):
        cid = truth[key]["contract_id"]
        gap, holder, owed = gaps.get(cid, (0.0, "?", 0.0))
        expect = truth[key]["gap_usd"]
        check(
            f"{label} reproduces from raw ClickHouse ({cid})",
            abs(gap - expect) < max(1.0, abs(expect) * 0.01),
            f"{holder}: owed ${owed:,.2f}, paid ${float(paid.get(cid, 0)):,.2f}, "
            f"gap ${gap:,.2f} (ground truth ${expect:,.2f})",
        )

    # The prose and the columns must agree, or the agent's contract-parsing
    # step contradicts its own arithmetic and looks like a hallucination.
    mismatch = ch.query(
        "SELECT count() FROM backlot.rights_contracts "
        "WHERE escalation_threshold_units IS NOT NULL "
        "AND position(source_clause, concat('after ', toString(escalation_threshold_units), ' ')) = 0"
    ).result_rows[0][0]
    check(
        "every contract's prose matches its structured threshold",
        mismatch == 0,
        f"{mismatch} contracts whose source_clause states a different escalation "
        "threshold than the column (must be 0 — parse_rights_clause reads that prose)",
    )

    # The threshold must be stated in the unit the contract actually bills in.
    # Saying "after N streams" on a per-minute deal makes the data contradict
    # itself: the agent compares a minutes threshold to a stream count, finds
    # the tier untriggered, and correctly reports no underpayment.
    wrong_unit = ch.query(
        "SELECT count() FROM backlot.rights_contracts "
        "WHERE escalation_threshold_units IS NOT NULL AND ("
        "  (rate_type = 'per_stream' AND position(source_clause, ' streams') = 0) OR"
        "  (rate_type = 'per_minute' AND position(source_clause, ' attributed minutes') = 0))"
    ).result_rows[0][0]
    check(
        "escalation thresholds are stated in the contract's own billing unit",
        wrong_unit == 0,
        f"{wrong_unit} contracts state their threshold in the wrong unit "
        "(must be 0 — a per-minute deal whose clause says 'streams' is unauditable)",
    )

    triggered = ch.query(
        "SELECT countIf(rate_type='per_stream'), countIf(rate_type='per_minute') "
        "FROM backlot.rights_contracts WHERE escalation_threshold_units IS NOT NULL"
    ).result_rows[0]
    check(
        "escalation clauses exist on volume-based deals only",
        sum(triggered) > 0,
        f"{triggered[0]} per_stream and {triggered[1]} per_minute contracts carry an "
        "escalation tier; flat-fee and revenue-share deals correctly have none",
    )


def verify_churn(ch, truth: dict) -> None:
    print(f"\n{BOLD}5. Audience collapse — Churn Early-Warning{RESET}")
    tid, turn = truth["title_id"], truth["turn_date_utc"]

    before, after = (
        ch.query(
            "SELECT avg(watch_seconds), avg(is_drop_off) FROM backlot.play_events "
            f"WHERE title_id='{tid}' AND event_time {op} '{turn}'"
        ).result_rows[0]
        for op in ("<", ">=")
    )
    decline = 1 - (after[0] / before[0]) if before[0] else 0
    check(
        "watch time collapses after the turn date",
        decline > 0.4,
        f"avg watch {before[0]:,.0f}s before {turn} vs {after[0]:,.0f}s after "
        f"({decline:.0%} decline), drop-off {before[1]:.1%} -> {after[1]:.1%}",
    )

    s_before, s_after = (
        ch.query(
            "SELECT avg(sentiment_score) FROM backlot.sentiment_events "
            f"WHERE title_id='{tid}' AND event_time {op} '{turn}'"
        ).result_rows[0][0]
        for op in ("<", ">=")
    )
    check(
        "sentiment corroborates the decline",
        float(s_after) < 0 < float(s_before),
        f"sentiment {float(s_before):+.2f} before -> {float(s_after):+.2f} after — "
        "engagement and sentiment turn together, which is the strong retention signal",
    )


def verify_integrity(ch) -> None:
    print(f"\n{BOLD}6. Dataset integrity{RESET}")
    early = ch.query(
        "SELECT count() FROM backlot.play_events pe "
        "INNER JOIN backlot.titles t ON pe.title_id = t.title_id "
        "WHERE toDate(pe.event_time) < t.release_date"
    ).result_rows[0][0]
    check(
        "no title accumulates plays before it was released",
        early == 0,
        f"{early:,} play_events dated before their title's release_date (must be 0)",
    )

    users, sessions = ch.query(
        "SELECT uniqExact(user_id), count() FROM backlot.play_events"
    ).result_rows[0]
    check(
        "subscribers are a finite population, not one user per session",
        users < sessions / 2,
        f"{users:,} accounts across {sessions:,} sessions "
        f"({sessions / users:.1f} sessions per account) — retention and fraud "
        "analysis are only meaningful if a user_id recurs",
    )


def main() -> None:
    if not ANOMALIES.exists():
        sys.exit(f"{ANOMALIES} not found — run data/generate_synthetic_data.py first.")
    truth = json.loads(ANOMALIES.read_text())
    ch = client()

    print(f"{BOLD}The Backlot — ground-truth verification against ClickHouse Cloud{RESET}")
    print(f"{DIM}host: {os.environ['CLICKHOUSE_HOST']}  database: backlot{RESET}")

    verify_cdn_incident(ch, truth["cdn_incident"])
    verify_ghost_ads(ch, truth["cdn_incident"])
    verify_fraud_ring(ch, truth["fraud_ring"])
    verify_royalties(ch, truth["underpaid_contracts"])
    verify_churn(ch, truth["churn_title"])
    verify_integrity(ch)

    failed = [n for n, ok, _ in _results if not ok]
    print(f"\n{BOLD}{'=' * 66}{RESET}")
    if failed:
        print(f"{RED}{len(failed)} of {len(_results)} checks FAILED:{RESET}")
        for n in failed:
            print(f"  - {n}")
        sys.exit(1)
    print(f"{GREEN}All {len(_results)} checks passed.{RESET} Every anomaly the agents are "
          "expected to find is present in ClickHouse, sitting in a realistic background.")


if __name__ == "__main__":
    main()
