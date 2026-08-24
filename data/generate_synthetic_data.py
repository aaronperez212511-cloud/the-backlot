"""
Synthetic data generator for The Backlot.

Produces CSVs matching clickhouse/schema.sql, with a set of deliberate
anomalies seeded in so every agent has something real to find. The ground
truth for every seeded anomaly is written to data/generated/ANOMALIES.json
so demo narration (and judges) can verify the agents actually found the
right thing, not just *a* thing.

Usage:
    python data/generate_synthetic_data.py --rows 1000000
"""
from __future__ import annotations

import argparse
import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

RNG_SEED = 20260901
OUT_DIR = Path(__file__).parent / "generated"

TITLES = [
    ("t01", "Midnight Marquee", "Thriller", "2026-09-01", 42_000_000),
    ("t02", "Static Bloom", "Drama", "2026-08-15", 18_000_000),
    ("t03", "Crimson Ledger", "Crime", "2026-07-20", 55_000_000),
    ("t04", "Nova Horizon", "Sci-Fi", "2026-06-10", 90_000_000),
    ("t05", "The Last Reel", "Documentary", "2026-08-01", 6_000_000),
    ("t06", "Iron Continuity", "Action", "2026-07-04", 75_000_000),
    ("t07", "Paper Moonlight", "Romance", "2026-08-22", 22_000_000),
    ("t08", "Backlot Shadows", "Horror", "2026-09-01", 15_000_000),
]
PREMIERE_TITLE_ID = "t01"  # Midnight Marquee — the global premiere event
# All timestamps in this generator are naive and implicitly UTC.
PREMIERE_START = datetime(2026, 9, 1, 18, 0)
PREMIERE_END = datetime(2026, 9, 1, 20, 30)

TERRITORIES = ["US", "MX", "BR", "GB", "DE", "FR", "IN", "JP", "KR", "AU"]
TERRITORY_WEIGHTS = np.array([0.22, 0.10, 0.13, 0.09, 0.08, 0.07, 0.12, 0.08, 0.06, 0.05])
DEVICE_TYPES = ["mobile", "tv", "web", "console", "tablet"]
SUB_TIERS = ["basic_ads", "standard", "premium"]
SUB_WEIGHTS = [0.35, 0.4, 0.25]

# --- Seeded incident: a degraded CDN edge node in Brazil during the premiere,
# causing BOTH a viewer buffering spike (Premiere Pulse) AND an ad-insertion
# stitching failure (Ghost Ads) in the same window. This is the cross-domain
# correlation the Control Room orchestrator is built to surface.
INCIDENT_TERRITORY = "BR"
INCIDENT_CDN_NODE = "sa-east-1b"
INCIDENT_START = PREMIERE_START + timedelta(minutes=65)   # 19:05 UTC
INCIDENT_END = PREMIERE_START + timedelta(minutes=80)     # 19:20 UTC

# --- Seeded incident: a credential-sharing / bot ring on the premiere title.
FRAUD_CLUSTER_SIZE = 90
FRAUD_SHARED_FINGERPRINT = "fp-ring-77c1"

# --- Seeded incident: two contracts deliberately, mechanistically underpaid.
# Which contract_ids these turn out to be is resolved at generation time (see
# seed_underpayment_scenarios) so the escalation-clause scenario is picked
# against a contract that actually has enough streams to trigger it.

# --- Seeded incident: Static Bloom tanks in week 2 (sentiment + watch time).
CHURN_TITLE_ID = "t02"

RNG = np.random.default_rng(RNG_SEED)


def gen_titles() -> pd.DataFrame:
    return pd.DataFrame(
        TITLES, columns=["title_id", "title_name", "genre", "release_date", "budget_usd"]
    )


def _timestamps_for_title(title_id: str, n: int) -> np.ndarray:
    if title_id == PREMIERE_TITLE_ID:
        span = (PREMIERE_END - PREMIERE_START).total_seconds()
        offsets = RNG.exponential(scale=span / 6, size=n)
        offsets = np.clip(offsets, 0, span)
        return np.array([PREMIERE_START + timedelta(seconds=float(o)) for o in offsets])
    # Background titles: spread across a 30-day catalog window.
    window_start = PREMIERE_START - timedelta(days=25)
    span = (PREMIERE_END + timedelta(days=5) - window_start).total_seconds()
    offsets = RNG.uniform(0, span, size=n)
    return np.array([window_start + timedelta(seconds=float(o)) for o in offsets])


def gen_play_events(total_rows: int) -> pd.DataFrame:
    # Premiere title gets 45% of volume, the rest split by a budget-weighted draw.
    weights = np.array([1.0 if t[0] != PREMIERE_TITLE_ID else 0.0 for t in TITLES])
    weights = weights / weights.sum()
    premiere_rows = int(total_rows * 0.45)
    background_rows = total_rows - premiere_rows

    bg_title_ids = RNG.choice(
        [t[0] for t in TITLES if t[0] != PREMIERE_TITLE_ID], size=background_rows, p=weights[weights > 0]
    )
    title_ids = np.concatenate([np.full(premiere_rows, PREMIERE_TITLE_ID), bg_title_ids])
    n = len(title_ids)

    event_times = np.concatenate(
        [
            _timestamps_for_title(PREMIERE_TITLE_ID, premiere_rows),
            np.concatenate(
                [
                    _timestamps_for_title(tid, (bg_title_ids == tid).sum())
                    for tid in set(bg_title_ids)
                ]
            ),
        ]
    )

    territory = RNG.choice(TERRITORIES, size=n, p=TERRITORY_WEIGHTS)
    device_type = RNG.choice(DEVICE_TYPES, size=n)
    sub_tier = RNG.choice(SUB_TIERS, size=n, p=SUB_WEIGHTS)
    # dtype=object avoids numpy's fixed-width string truncation — without it,
    # this array's width is inferred from these initial 9-char values, and
    # the later assignment of the (10-char) INCIDENT_CDN_NODE silently gets
    # truncated to fit.
    cdn_node = np.array([f"{terr.lower()}-node-{RNG.integers(1, 4)}" for terr in territory], dtype=object)

    bitrate = RNG.normal(4200, 900, size=n).clip(600, 8000).astype(int)
    buffering_ms = RNG.exponential(300, size=n).clip(0, 4000).astype(int)
    rebuffer_count = RNG.poisson(0.4, size=n)
    watch_seconds = RNG.normal(4800, 1800, size=n).clip(15, 9000).astype(int)
    is_drop_off = (RNG.random(n) < 0.04).astype(int)

    # Inject the CDN incident: elevate buffering/rebuffers/drop-off sharply for
    # the affected territory + time window on the premiere title, and pin the
    # affected sessions to the degraded node so the root cause is traceable.
    in_incident_window = (
        (title_ids == PREMIERE_TITLE_ID)
        & (territory == INCIDENT_TERRITORY)
        & (event_times >= np.datetime64(INCIDENT_START))
        & (event_times <= np.datetime64(INCIDENT_END))
    )
    cdn_node[in_incident_window] = INCIDENT_CDN_NODE
    buffering_ms[in_incident_window] = RNG.exponential(2600, size=in_incident_window.sum()).clip(1200, 9000).astype(int)
    rebuffer_count[in_incident_window] = RNG.poisson(6, size=in_incident_window.sum())
    is_drop_off[in_incident_window] = (RNG.random(in_incident_window.sum()) < 0.35).astype(int)

    session_id = np.array([uuid.uuid4().hex[:16] for _ in range(n)])
    user_id = np.array([uuid.uuid4().hex[:12] for _ in range(n)])
    device_id = np.array([uuid.uuid4().hex[:12] for _ in range(n)])

    df = pd.DataFrame(
        {
            "event_time": event_times,
            "session_id": session_id,
            "user_id": user_id,
            "title_id": title_ids,
            "territory": territory,
            "device_type": device_type,
            "device_id": device_id,
            "cdn_node": cdn_node,
            "bitrate_kbps": bitrate,
            "buffering_ms": buffering_ms,
            "rebuffer_count": rebuffer_count,
            "watch_seconds": watch_seconds,
            "is_drop_off": is_drop_off,
            "subscription_tier": sub_tier,
        }
    )

    # Apply the churn title's slow decay: sessions in week 2+ watch less.
    churn_mask = df["title_id"] == CHURN_TITLE_ID
    week2_cutoff = pd.Timestamp(PREMIERE_START - timedelta(days=11))
    decay_mask = churn_mask & (pd.to_datetime(df["event_time"]) >= week2_cutoff)
    df.loc[decay_mask, "watch_seconds"] = (df.loc[decay_mask, "watch_seconds"] * 0.4).astype(int)
    df.loc[decay_mask, "is_drop_off"] = (RNG.random(decay_mask.sum()) < 0.22).astype(int)

    return df.sort_values("event_time").reset_index(drop=True), in_incident_window.sum()


def gen_ad_events(play_events: pd.DataFrame) -> pd.DataFrame:
    ad_sessions = play_events[play_events["subscription_tier"] == "basic_ads"].copy()
    n = len(ad_sessions)
    ad_pod_id = np.array([uuid.uuid4().hex[:10] for _ in range(n)])
    ad_slot_seq = RNG.integers(1, 4, size=n)
    requested = np.ones(n, dtype=int)

    fill_reason = np.full(n, "ok", dtype=object)
    filled = np.ones(n, dtype=int)
    fail_mask = RNG.random(n) < 0.03  # baseline ~3% no-fill rate
    fill_reason[fail_mask] = RNG.choice(["timeout", "no_fill", "creative_error"], size=fail_mask.sum())
    filled[fail_mask] = 0

    # Same CDN incident also breaks SSAI ad stitching for the affected node.
    in_incident = (
        (ad_sessions["territory"].values == INCIDENT_TERRITORY)
        & (ad_sessions["cdn_node"].values == INCIDENT_CDN_NODE)
    )
    fill_reason[in_incident] = "ssai_stitch_fail"
    filled[in_incident] = 0

    expected_revenue = RNG.uniform(0.008, 0.04, size=n) * 1000  # CPM-ish per pod
    actual_revenue = np.where(filled == 1, expected_revenue, 0.0)

    return pd.DataFrame(
        {
            "event_time": ad_sessions["event_time"].values,
            "session_id": ad_sessions["session_id"].values,
            "title_id": ad_sessions["title_id"].values,
            "territory": ad_sessions["territory"].values,
            "ad_pod_id": ad_pod_id,
            "ad_slot_seq": ad_slot_seq,
            "requested": requested,
            "filled": filled,
            "fill_reason": fill_reason,
            "expected_revenue_usd": expected_revenue.round(4),
            "actual_revenue_usd": actual_revenue.round(4),
        }
    )


RIGHTS_HOLDERS = [
    ("rh01", "Elena Vasquez", "actor"),
    ("rh02", "Marcus Chen", "director"),
    ("rh03", "The Guild of Story Architects", "writer"),
    ("rh04", "Nadia Okafor", "composer"),
    ("rh05", "Tomas Rivera", "actor"),
    ("rh06", "Sophie Lindqvist", "writer"),
    ("rh07", "Kenji Watanabe", "composer"),
    ("rh08", "The Backlot Ensemble Collective", "actor"),
]


def gen_rights_contracts() -> pd.DataFrame:
    rows = []
    cid = 1
    for title_id, *_ in TITLES:
        n_holders = RNG.integers(2, 4)
        holders = RNG.choice(len(RIGHTS_HOLDERS), size=n_holders, replace=False)
        for h in holders:
            rh_id, rh_name, role = RIGHTS_HOLDERS[h]
            territory = RNG.choice(TERRITORIES)
            rate_type = RNG.choice(["per_stream", "per_minute", "revenue_share_pct", "flat_window"])
            rate_value = {
                "per_stream": round(RNG.uniform(0.002, 0.02), 5),
                "per_minute": round(RNG.uniform(0.0005, 0.004), 5),
                "revenue_share_pct": round(RNG.uniform(0.5, 4.0), 2),
                "flat_window": round(RNG.uniform(5000, 60000), 2),
            }[rate_type]
            has_escalation = RNG.random() < 0.4
            contract_id = f"c{cid:03d}"
            rows.append(
                {
                    "contract_id": contract_id,
                    "rights_holder": rh_name,
                    "role": role,
                    "title_id": title_id,
                    "territory": territory,
                    "rate_type": rate_type,
                    "rate_value": rate_value,
                    "window_start": "2026-06-01",
                    "window_end": "2027-06-01",
                    "escalation_threshold_streams": int(RNG.integers(50_000, 500_000)) if has_escalation else None,
                    "escalation_rate_value": round(rate_value * 1.5, 5) if has_escalation else None,
                    "source_clause": (
                        f"\"{rh_name} shall receive {rate_value} per "
                        f"{rate_type.replace('_', ' ')} in {territory}"
                        + (
                            f", escalating to {round(rate_value * 1.5, 5)} after "
                            f"{int(RNG.integers(50_000, 500_000))} streams\""
                            if has_escalation
                            else '"'
                        )
                    ),
                }
            )
            cid += 1
    return pd.DataFrame(rows)


def _owed_streambased(rate_value: float, streams: int, threshold, escalation_rate) -> float:
    """Tiered per_stream/per_minute payout: base rate below threshold,
    escalation rate above it. threshold/escalation_rate may be NaN (no
    escalation clause), in which case it's just streams * rate_value."""
    if pd.isna(threshold) or pd.isna(escalation_rate):
        return streams * rate_value
    threshold = float(threshold)
    base_streams = min(streams, threshold)
    escalated_streams = max(0, streams - threshold)
    return base_streams * rate_value + escalated_streams * escalation_rate


def compute_owed(c: pd.Series, streams: int) -> float:
    """The contractually-correct amount owed — used both as the 'truth' for
    every honestly-paid contract and as the baseline the two seeded
    underpayment scenarios deviate from."""
    if c["rate_type"] == "per_stream":
        return _owed_streambased(c["rate_value"], streams, c["escalation_threshold_streams"], c["escalation_rate_value"])
    if c["rate_type"] == "per_minute":
        return _owed_streambased(c["rate_value"], streams * 4.0, c["escalation_threshold_streams"], c["escalation_rate_value"])
    if c["rate_type"] == "revenue_share_pct":
        return streams * 0.02 * (c["rate_value"] / 100)  # rough revenue proxy
    return c["rate_value"]  # flat_window


def seed_underpayment_scenarios(contracts: pd.DataFrame, play_counts: dict) -> tuple[pd.DataFrame, str, str]:
    """Mutates two contracts so their seeded underpayment is mechanistically
    real and re-derivable by Chain of Title, not an arbitrary discount:

    1. escalation contract: a per_stream/per_minute contract on the premiere
       title, whose escalation threshold is set just below its actual
       stream count, so the escalation tier is genuinely triggered.
    2. flat-shortfall contract: a flat_window contract paid short of the
       flat fee the contract specifies.
    """
    contracts = contracts.copy()

    # Prefer a per_stream/per_minute contract on the premiere title (biggest,
    # most narratively obvious volume), but fall back to whichever such
    # contract has the most actual streams behind it, so this is robust to
    # a different RNG seed or contract mix landing the premiere title with
    # only flat_window contracts.
    stream_candidates = contracts[contracts["rate_type"].isin(["per_stream", "per_minute"])].copy()
    stream_candidates["_streams"] = stream_candidates.apply(
        lambda row: play_counts.get((row["title_id"], row["territory"]), 0), axis=1
    )
    premiere_candidates = stream_candidates[stream_candidates["title_id"] == PREMIERE_TITLE_ID]
    pool = premiere_candidates if len(premiere_candidates) else stream_candidates
    esc_idx = pool["_streams"].idxmax()
    esc_streams = play_counts.get((contracts.loc[esc_idx, "title_id"], contracts.loc[esc_idx, "territory"]), 0)
    esc_threshold = max(1, int(esc_streams * 0.4))
    esc_rate = float(contracts.loc[esc_idx, "rate_value"])
    esc_escalated_rate = round(esc_rate * 1.6, 5)
    contracts.loc[esc_idx, "escalation_threshold_streams"] = esc_threshold
    contracts.loc[esc_idx, "escalation_rate_value"] = esc_escalated_rate
    unit = "stream" if contracts.loc[esc_idx, "rate_type"] == "per_stream" else "minute"
    contracts.loc[esc_idx, "source_clause"] = (
        f'"{contracts.loc[esc_idx, "rights_holder"]} shall receive {esc_rate} per {unit} in '
        f'{contracts.loc[esc_idx, "territory"]}, escalating to {esc_escalated_rate} after {esc_threshold} streams"'
    )
    esc_contract_id = str(contracts.loc[esc_idx, "contract_id"])

    flat_candidates = contracts[(contracts["rate_type"] == "flat_window") & (contracts.index != esc_idx)]
    if len(flat_candidates) == 0:
        flat_candidates = contracts[contracts.index != esc_idx]
    flat_idx = flat_candidates.index[0]
    flat_contract_id = str(contracts.loc[flat_idx, "contract_id"])

    return contracts, esc_contract_id, flat_contract_id


def gen_royalty_ledger(
    contracts: pd.DataFrame, play_events: pd.DataFrame, esc_contract_id: str, flat_contract_id: str
) -> pd.DataFrame:
    rows = []
    pid = 1
    play_counts = play_events.groupby(["title_id", "territory"]).size().to_dict()
    for _, c in contracts.iterrows():
        streams = play_counts.get((c["title_id"], c["territory"]), 0)
        owed = compute_owed(c, streams)
        amount_paid = round(owed, 2)

        if c["contract_id"] == esc_contract_id:
            # Underpayment mechanism: paid at the base rate for every stream,
            # as if the escalation tier the contract specifies never existed.
            amount_paid = round(streams * c["rate_value"] if c["rate_type"] == "per_stream" else streams * 4.0 * c["rate_value"], 2)
        elif c["contract_id"] == flat_contract_id:
            # Underpayment mechanism: a straightforward shortfall against the
            # flat fee the contract specifies.
            amount_paid = round(owed * RNG.uniform(0.55, 0.75), 2)

        rows.append(
            {
                "payment_id": f"p{pid:04d}",
                "contract_id": c["contract_id"],
                "rights_holder": c["rights_holder"],
                "title_id": c["title_id"],
                "territory": c["territory"],
                "period_start": "2026-06-01",
                "period_end": "2026-09-01",
                "amount_paid_usd": amount_paid,
                "paid_at": "2026-09-05 09:00:00",
            }
        )
        pid += 1
    return pd.DataFrame(rows)


def gen_fraud_signals(play_events: pd.DataFrame) -> pd.DataFrame:
    n = len(play_events)
    device_fp = np.array([uuid.uuid4().hex[:14] for _ in range(n)])
    ip_geo = play_events["territory"].values
    account_home = play_events["territory"].values.copy()
    concurrent = RNG.poisson(1, size=n)
    impossible_travel = np.zeros(n, dtype=int)
    device_count_24h = RNG.poisson(1.2, size=n) + 1
    is_bot_ua = (RNG.random(n) < 0.01).astype(int)

    df = pd.DataFrame(
        {
            "event_time": play_events["event_time"].values,
            "session_id": play_events["session_id"].values,
            "user_id": play_events["user_id"].values,
            "device_fingerprint": device_fp,
            "ip_geo_territory": ip_geo,
            "account_home_territory": account_home,
            "concurrent_sessions_5min": concurrent,
            "impossible_travel_flag": impossible_travel,
            "device_count_24h": device_count_24h,
            "is_bot_ua": is_bot_ua,
        }
    )

    # Inject a credential-sharing / bot ring on the premiere title: one shared
    # fingerprint fanned out across many distinct accounts and territories.
    premiere_idx = play_events.index[play_events["title_id"] == PREMIERE_TITLE_ID].to_numpy()
    ring_idx = RNG.choice(premiere_idx, size=min(FRAUD_CLUSTER_SIZE, len(premiere_idx)), replace=False)
    df.loc[ring_idx, "device_fingerprint"] = FRAUD_SHARED_FINGERPRINT
    df.loc[ring_idx, "account_home_territory"] = RNG.choice(TERRITORIES, size=len(ring_idx))
    df.loc[ring_idx, "concurrent_sessions_5min"] = RNG.integers(8, 20, size=len(ring_idx))
    df.loc[ring_idx, "impossible_travel_flag"] = 1
    df.loc[ring_idx, "device_count_24h"] = RNG.integers(15, 40, size=len(ring_idx))

    return df


def gen_sentiment_events() -> pd.DataFrame:
    rows = []
    for title_id, name, *_ in [(t[0], t[1]) for t in TITLES]:
        window_start = PREMIERE_START - timedelta(days=25)
        for day in range(30):
            day_ts = window_start + timedelta(days=day)
            n_events = RNG.integers(3, 12)
            base_sentiment = RNG.uniform(0.1, 0.6)
            if title_id == CHURN_TITLE_ID and day >= 14:
                base_sentiment = RNG.uniform(-0.6, -0.1)  # sharp negative turn in week 2+
            for _ in range(n_events):
                score = float(np.clip(RNG.normal(base_sentiment, 0.25), -1, 1))
                rows.append(
                    {
                        "event_time": day_ts.strftime("%Y-%m-%d %H:%M:%S"),
                        "title_id": title_id,
                        "territory": RNG.choice(TERRITORIES),
                        "source": RNG.choice(["review", "social", "app_rating"]),
                        "sentiment_score": round(score, 3),
                        "text_snippet": f"synthetic sentiment sample for {name}",
                    }
                )
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=200_000, help="total play_events rows to generate")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    titles = gen_titles()
    play_events, incident_rows = gen_play_events(args.rows)
    ad_events = gen_ad_events(play_events)
    contracts = gen_rights_contracts()
    play_counts = play_events.groupby(["title_id", "territory"]).size().to_dict()
    contracts, esc_contract_id, flat_contract_id = seed_underpayment_scenarios(contracts, play_counts)
    ledger = gen_royalty_ledger(contracts, play_events, esc_contract_id, flat_contract_id)
    fraud = gen_fraud_signals(play_events)
    sentiment = gen_sentiment_events()

    titles.to_csv(OUT_DIR / "titles.csv", index=False)
    play_events.to_csv(OUT_DIR / "play_events.csv", index=False)
    ad_events.to_csv(OUT_DIR / "ad_events.csv", index=False)
    contracts.to_csv(OUT_DIR / "rights_contracts.csv", index=False)
    ledger.to_csv(OUT_DIR / "royalty_ledger.csv", index=False)
    fraud.to_csv(OUT_DIR / "fraud_signals.csv", index=False)
    sentiment.to_csv(OUT_DIR / "sentiment_events.csv", index=False)

    underpaid_ids = [esc_contract_id, flat_contract_id]
    underpaid = ledger[ledger["contract_id"].isin(underpaid_ids)]
    anomalies = {
        "cdn_incident": {
            "territory": INCIDENT_TERRITORY,
            "cdn_node": INCIDENT_CDN_NODE,
            "window_utc": [INCIDENT_START.isoformat(), INCIDENT_END.isoformat()],
            "title_id": PREMIERE_TITLE_ID,
            "affected_play_events": int(incident_rows),
            "expected_finding": (
                "Premiere Pulse should flag a buffering/rebuffer/drop-off spike for "
                f"{PREMIERE_TITLE_ID} in {INCIDENT_TERRITORY} on node {INCIDENT_CDN_NODE} "
                "during the window; Ghost Ads should independently flag ssai_stitch_fail "
                "revenue loss on the same node/window. Control Room should correlate the two."
            ),
        },
        "fraud_ring": {
            "shared_fingerprint": FRAUD_SHARED_FINGERPRINT,
            "cluster_size": FRAUD_CLUSTER_SIZE,
            "title_id": PREMIERE_TITLE_ID,
            "expected_finding": (
                "Stream Fraud Sentinel should flag device_fingerprint="
                f"{FRAUD_SHARED_FINGERPRINT} as a credential-sharing/bot ring: one "
                "fingerprint fanned across many accounts/territories with high "
                "concurrent_sessions_5min and impossible_travel_flag=1."
            ),
        },
        "underpaid_contracts": {
            "escalation_clause_ignored": {
                "contract_id": esc_contract_id,
                "expected_finding": (
                    "This contract's escalation tier was genuinely triggered (streams "
                    "exceeded escalation_threshold_streams) but every stream was paid at "
                    "the base rate — Chain of Title should recompute the tiered amount "
                    "and show the gap is exactly the escalation tier that was skipped."
                ),
            },
            "flat_fee_shortfall": {
                "contract_id": flat_contract_id,
                "expected_finding": (
                    "This flat_window contract was paid ~55-75% of the flat fee its "
                    "own contract terms specify — a plain shortfall, no escalation "
                    "clause involved."
                ),
            },
            "sample_underpayment_usd": underpaid[["contract_id", "amount_paid_usd"]].to_dict("records"),
        },
        "churn_title": {
            "title_id": CHURN_TITLE_ID,
            "title_name": dict((t[0], t[1]) for t in TITLES)[CHURN_TITLE_ID],
            "turn_day_offset": 14,
            "expected_finding": (
                "Churn Early-Warning should detect the week-2 collapse in watch_seconds "
                "correlated with a sharp negative swing in sentiment_events for this title."
            ),
        },
    }
    (OUT_DIR / "ANOMALIES.json").write_text(json.dumps(anomalies, indent=2, default=str))

    print(f"Wrote {len(play_events):,} play_events ({incident_rows} in the CDN incident window)")
    print(f"Wrote {len(ad_events):,} ad_events")
    print(f"Wrote {len(contracts)} rights_contracts, {len(ledger)} royalty_ledger rows")
    print(f"Wrote {len(fraud):,} fraud_signals ({FRAUD_CLUSTER_SIZE} in the fraud ring)")
    print(f"Wrote {len(sentiment):,} sentiment_events")
    print(f"Ground truth written to {OUT_DIR / 'ANOMALIES.json'}")


if __name__ == "__main__":
    main()
