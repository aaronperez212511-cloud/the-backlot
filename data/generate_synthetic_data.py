"""
Synthetic data generator for The Backlot.

Produces CSVs matching clickhouse/schema.sql, with a set of deliberate
anomalies seeded in so every agent has something real to find. The ground
truth for every seeded anomaly is written to data/generated/ANOMALIES.json
so demo narration (and judges) can verify the agents actually found the
right thing, not just *a* thing.

Two properties this generator exists to preserve, because the credibility of
the whole project rests on them:

1. Every royalty figure is RE-DERIVABLE FROM CLICKHOUSE. The payout model
   uses no constant an agent could not compute itself from play_events and
   ad_events. So when Chain of Title disagrees with the ledger, that is a
   real finding rather than an artifact of this file.
2. The anomalies sit in a REALISTIC BACKGROUND. Households genuinely share
   devices, travellers trip geo checks, and honest payments carry rounding
   drift. Detection is therefore a discrimination task, not one equality
   filter against an otherwise empty dataset.

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

# Catalog telemetry window for non-premiere titles. A title's own window
# starts at its release_date when that is later, so no title accumulates
# plays before it exists — which would be obviously wrong to a judge and
# would break churn_early_warning's "days since release" trend outright.
CATALOG_START = PREMIERE_START - timedelta(days=25)
CATALOG_END = PREMIERE_END + timedelta(days=5)

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
# Share of eligible in-window sessions routed to the failing edge node. Below
# 1.0 on purpose: healthy sessions coexist in the same window, so finding the
# incident means isolating a node, not just picking a time range.
INCIDENT_NODE_SHARE = 0.72

# --- Seeded incident: a credential-sharing / bot ring on the premiere title.
FRAUD_CLUSTER_SIZE = 90
FRAUD_SHARED_FINGERPRINT = "fp-ring-77c1"
# Legitimate-but-noisy background, so finding the ring is a discrimination
# problem: households that really do share one device, public/venue devices
# with high account fan-out and nothing else wrong, and ordinary VPN or
# travelling users who trip a geo check on their own.
N_VENUE_DEVICES = 6
VENUE_FANOUT = (6, 14)
VPN_RATE = 0.030
TRAVEL_RATE = 0.050  # share of sessions watched outside the account's home market
BASELINE_IMPOSSIBLE_TRAVEL_RATE = 0.004
BASELINE_BOT_UA_RATE = 0.010

# --- Seeded incident: two contracts deliberately, mechanistically underpaid.
# Which contract_ids these turn out to be is resolved at generation time (see
# seed_underpayment_scenarios) so the escalation-clause scenario lands on a
# contract that actually has the volume to trigger its own escalation tier.

# --- Seeded incident: Static Bloom loses its audience after week two.
CHURN_TITLE_ID = "t02"
CHURN_TURN_DAY = 14  # days after that title's own release_date

# Honest payments still carry small rounding/FX drift; a ledger where every
# correct payment matches to the exact cent is not a realistic audit target,
# and it makes the agent's materiality threshold meaningless. Kept far below
# the $50 threshold Chain of Title treats as reportable.
HONEST_DRIFT_PCT = 0.0002

RNG = np.random.default_rng(RNG_SEED)

RELEASE_DATES = {t[0]: datetime.strptime(t[3], "%Y-%m-%d") for t in TITLES}
TITLE_NAMES = {t[0]: t[1] for t in TITLES}


def gen_titles() -> pd.DataFrame:
    return pd.DataFrame(
        TITLES, columns=["title_id", "title_name", "genre", "release_date", "budget_usd"]
    )


def _title_window(title_id: str) -> tuple[datetime, datetime]:
    if title_id == PREMIERE_TITLE_ID:
        return PREMIERE_START, PREMIERE_END
    return max(CATALOG_START, RELEASE_DATES[title_id]), CATALOG_END


def _timestamps_for_title(title_id: str, n: int) -> np.ndarray:
    """Timestamps drawn inside this title's own availability window."""
    start, end = _title_window(title_id)
    span = (end - start).total_seconds()
    if title_id == PREMIERE_TITLE_ID:
        # Premiere traffic front-loads hard at the top of the event.
        offsets = np.clip(RNG.exponential(scale=span / 6, size=n), 0, span)
    else:
        offsets = RNG.uniform(0, span, size=n)
    return np.array([start + timedelta(seconds=float(o)) for o in offsets])


def gen_play_events(total_rows: int) -> tuple[pd.DataFrame, int, int, np.ndarray]:
    """Builds play_events one title-block at a time.

    Each block's title_ids and event_times are generated together and only
    then concatenated, so a row's timestamp always belongs to the title on
    that same row. (An earlier version generated timestamps grouped by title
    but concatenated them against a shuffled title_id array, silently
    misaligning every background row.)
    """
    premiere_rows = int(total_rows * 0.45)
    bg_titles = [t[0] for t in TITLES if t[0] != PREMIERE_TITLE_ID]
    bg_rows = total_rows - premiere_rows
    per_title = bg_rows // len(bg_titles)

    id_blocks, time_blocks = [], []
    for tid in [PREMIERE_TITLE_ID] + bg_titles:
        if tid == PREMIERE_TITLE_ID:
            k = premiere_rows
        elif tid == bg_titles[-1]:
            k = bg_rows - per_title * (len(bg_titles) - 1)
        else:
            k = per_title
        id_blocks.append(np.full(k, tid))
        time_blocks.append(_timestamps_for_title(tid, k))

    title_ids = np.concatenate(id_blocks)
    event_times = np.concatenate(time_blocks)
    n = len(title_ids)

    # A finite subscriber base, so a user_id means something across sessions
    # (~8 sessions per account) instead of every row being a brand new person,
    # which would make both retention and fraud analysis meaningless.
    n_users = max(2_000, n // 8)
    user_idx = RNG.integers(0, n_users, size=n)
    user_id = np.array([f"u{i:07d}" for i in user_idx], dtype=object)

    # An account has a home market and mostly watches from it. Without this,
    # a session's territory is independent of the account's home country and
    # ~90% of rows look like international travel — which would make the
    # geo-mismatch fraud signal meaningless, since mismatching would be the
    # norm rather than the exception.
    user_home = RNG.choice(TERRITORIES, size=n_users, p=TERRITORY_WEIGHTS)
    territory = user_home[user_idx].copy()
    travelling = RNG.random(n) < TRAVEL_RATE
    territory[travelling] = RNG.choice(
        TERRITORIES, size=int(travelling.sum()), p=TERRITORY_WEIGHTS
    )
    device_type = RNG.choice(DEVICE_TYPES, size=n)
    sub_tier = RNG.choice(SUB_TIERS, size=n, p=SUB_WEIGHTS)
    # dtype=object avoids numpy's fixed-width string truncation — without it
    # this array's width is inferred from these initial 9-char values, and the
    # later assignment of the 10-char INCIDENT_CDN_NODE is silently clipped.
    cdn_node = np.array(
        [f"{terr.lower()}-node-{RNG.integers(1, 4)}" for terr in territory], dtype=object
    )

    bitrate = RNG.normal(4200, 900, size=n).clip(600, 8000).astype(int)
    buffering_ms = RNG.exponential(300, size=n).clip(0, 4000).astype(int)
    rebuffer_count = RNG.poisson(0.4, size=n)
    watch_seconds = RNG.normal(4800, 1800, size=n).clip(15, 9000).astype(int)
    is_drop_off = (RNG.random(n) < 0.04).astype(int)

    # Inject the CDN incident: elevate buffering/rebuffers/drop-off sharply for
    # the affected territory + window on the premiere title, and pin those
    # sessions to the degraded node so the root cause stays traceable.
    # Only a share of eligible sessions land on the degraded edge node: a real
    # CDN incident takes out one node, not an entire country. Keeping healthy
    # traffic in the same window is what gives Premiere Pulse and Ghost Ads a
    # within-window comparison to make, instead of a window where every single
    # session is broken and no discrimination is required.
    in_incident = (
        (title_ids == PREMIERE_TITLE_ID)
        & (territory == INCIDENT_TERRITORY)
        & (event_times >= np.datetime64(INCIDENT_START))
        & (event_times <= np.datetime64(INCIDENT_END))
        & (RNG.random(len(title_ids)) < INCIDENT_NODE_SHARE)
    )
    k = int(in_incident.sum())
    cdn_node[in_incident] = INCIDENT_CDN_NODE
    buffering_ms[in_incident] = RNG.exponential(2600, size=k).clip(1200, 9000).astype(int)
    rebuffer_count[in_incident] = RNG.poisson(6, size=k)
    is_drop_off[in_incident] = (RNG.random(k) < 0.35).astype(int)

    df = pd.DataFrame(
        {
            "event_time": event_times,
            "session_id": np.array([uuid.uuid4().hex[:16] for _ in range(n)]),
            "user_id": user_id,
            "title_id": title_ids,
            "territory": territory,
            "device_type": device_type,
            "device_id": np.array([uuid.uuid4().hex[:12] for _ in range(n)]),
            "cdn_node": cdn_node,
            "bitrate_kbps": bitrate,
            "buffering_ms": buffering_ms,
            "rebuffer_count": rebuffer_count,
            "watch_seconds": watch_seconds,
            "is_drop_off": is_drop_off,
            "subscription_tier": sub_tier,
        }
    )

    # The churn title decays from CHURN_TURN_DAY after its OWN release date.
    churn_turn = RELEASE_DATES[CHURN_TITLE_ID] + timedelta(days=CHURN_TURN_DAY)
    decay = (df["title_id"] == CHURN_TITLE_ID) & (
        pd.to_datetime(df["event_time"]) >= pd.Timestamp(churn_turn)
    )
    df.loc[decay, "watch_seconds"] = (df.loc[decay, "watch_seconds"] * 0.4).astype(int)
    df.loc[decay, "is_drop_off"] = (RNG.random(int(decay.sum())) < 0.22).astype(int)

    df = df.sort_values("event_time").reset_index(drop=True)
    return df, k, n_users, user_home


def gen_ad_events(play_events: pd.DataFrame) -> pd.DataFrame:
    ad_sessions = play_events[play_events["subscription_tier"] == "basic_ads"].copy()
    n = len(ad_sessions)

    fill_reason = np.full(n, "ok", dtype=object)
    filled = np.ones(n, dtype=int)
    fail_mask = RNG.random(n) < 0.03  # baseline ~3% no-fill rate
    fill_reason[fail_mask] = RNG.choice(
        ["timeout", "no_fill", "creative_error"], size=int(fail_mask.sum())
    )
    filled[fail_mask] = 0

    # The same CDN incident also breaks SSAI ad stitching on that node. Keying
    # off cdn_node alone is exact: that node name is only ever assigned to
    # sessions inside the incident window.
    in_incident = (ad_sessions["territory"].values == INCIDENT_TERRITORY) & (
        ad_sessions["cdn_node"].values == INCIDENT_CDN_NODE
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
            "ad_pod_id": np.array([uuid.uuid4().hex[:10] for _ in range(n)]),
            "ad_slot_seq": RNG.integers(1, 4, size=n),
            "requested": np.ones(n, dtype=int),
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

_UNIT_WORD = {
    "per_stream": "stream",
    "per_minute": "attributed minute",
    "revenue_share_pct": "percent of ad revenue",
    "flat_window": "flat licence fee",
}

# Plausible escalation thresholds, per rate type, on the scale of that type's
# own billable unit. A title/territory here runs tens of thousands of streams
# and millions of attributed minutes.
_ESCALATION_RANGE = {
    "per_stream": (20_000, 90_000),
    "per_minute": (1_500_000, 6_000_000),
}


def _clause(holder: str, rate_type: str, rate_value: float, territory: str,
            threshold, escalated) -> str:
    """Renders the human contract language for a set of terms.

    Single source of truth for the prose, so `source_clause` can never state a
    different threshold than the structured column — which is exactly what an
    earlier version did, by drawing the threshold twice from the RNG. Chain of
    Title reads this prose through parse_rights_clause and compares it against
    the columns; any disagreement there is a bug that reads to a judge as the
    agent hallucinating.
    """
    base = f'"{holder} shall receive {rate_value} per {_UNIT_WORD[rate_type]} in {territory}'
    if threshold is None:
        return base + '"'
    # The threshold is expressed in the SAME unit the contract bills in. Saying
    # "after N streams" on a per-minute contract would be a self-contradiction:
    # the agent would compare a minutes threshold against a stream count, find
    # the tier untriggered, and correctly conclude the underpayment is not
    # there — which is exactly how an earlier version hid its own seeded bug.
    return base + f', escalating to {escalated} after {threshold} {_UNIT_WORD[rate_type]}s"'


def gen_rights_contracts() -> pd.DataFrame:
    rows = []
    cid = 1
    for title_id, *_ in TITLES:
        n_holders = RNG.integers(2, 4)
        holders = RNG.choice(len(RIGHTS_HOLDERS), size=n_holders, replace=False)
        for h in holders:
            _, rh_name, role = RIGHTS_HOLDERS[h]
            territory = RNG.choice(TERRITORIES)
            rate_type = RNG.choice(["per_stream", "per_minute", "revenue_share_pct", "flat_window"])
            rate_value = {
                "per_stream": round(RNG.uniform(0.002, 0.02), 5),
                "per_minute": round(RNG.uniform(0.0005, 0.004), 5),
                "revenue_share_pct": round(RNG.uniform(0.5, 4.0), 2),
                "flat_window": round(RNG.uniform(5000, 60000), 2),
            }[rate_type]
            # One draw, used for BOTH the structured column and the prose.
            # Escalation tiers only exist on volume-based deals, and the
            # threshold is drawn on the scale of that deal's own unit — a
            # per-minute contract counts millions of minutes where a per-stream
            # contract counts tens of thousands of streams, so one shared range
            # would make the tier either always or never trigger.
            threshold = None
            if rate_type in _ESCALATION_RANGE and RNG.random() < 0.45:
                lo, hi = _ESCALATION_RANGE[rate_type]
                threshold = int(RNG.integers(lo, hi))
            escalated = round(rate_value * 1.5, 5) if threshold is not None else None
            rows.append(
                {
                    "contract_id": f"c{cid:03d}",
                    "rights_holder": rh_name,
                    "role": role,
                    "title_id": title_id,
                    "territory": territory,
                    "rate_type": rate_type,
                    "rate_value": rate_value,
                    "window_start": "2026-06-01",
                    "window_end": "2027-06-01",
                    "escalation_threshold_units": threshold,
                    "escalation_rate_value": escalated,
                    "source_clause": _clause(
                        rh_name, rate_type, rate_value, territory, threshold, escalated
                    ),
                }
            )
            cid += 1
    return pd.DataFrame(rows)


def _tiered(units: float, rate: float, threshold, escalated) -> float:
    """Base rate below the threshold, escalation rate above it."""
    if pd.isna(threshold) or pd.isna(escalated):
        return units * rate
    threshold = float(threshold)
    return min(units, threshold) * rate + max(0.0, units - threshold) * escalated


def contract_units(c: pd.Series, basis: dict) -> float:
    """The billable quantity for a contract, straight out of the warehouse.

    Every one of these is a plain aggregate an agent can reproduce in SQL:
      per_stream        COUNT(*) FROM play_events
      per_minute        SUM(watch_seconds)/60 FROM play_events
      revenue_share_pct SUM(actual_revenue_usd) FROM ad_events
      flat_window       n/a — the fee does not depend on volume
    """
    b = basis.get((c["title_id"], c["territory"]), {})
    if c["rate_type"] == "per_stream":
        return float(b.get("streams", 0))
    if c["rate_type"] == "per_minute":
        return float(b.get("minutes", 0.0))
    if c["rate_type"] == "revenue_share_pct":
        return float(b.get("ad_revenue", 0.0))
    return 0.0


def compute_owed(c: pd.Series, basis: dict) -> float:
    """The contractually correct amount owed."""
    units = contract_units(c, basis)
    if c["rate_type"] in ("per_stream", "per_minute"):
        return _tiered(
            units, c["rate_value"],
            c["escalation_threshold_units"], c["escalation_rate_value"],
        )
    if c["rate_type"] == "revenue_share_pct":
        return units * (c["rate_value"] / 100.0)
    return float(c["rate_value"])  # flat_window


def seed_underpayment_scenarios(contracts: pd.DataFrame, basis: dict) -> tuple[pd.DataFrame, str, str]:
    """Mutates two contracts so their underpayment is mechanistically real and
    re-derivable by Chain of Title, rather than an arbitrary discount:

    1. escalation contract: a per_stream/per_minute contract whose escalation
       threshold sits below its actual volume, so the tier genuinely triggers.
    2. flat-shortfall contract: a flat_window contract paid short of its own
       stated fee.
    """
    contracts = contracts.copy()

    # Prefer a per_stream/per_minute contract on the premiere title (biggest,
    # most narratively obvious volume), falling back to whichever such contract
    # carries the most units, so this stays robust to a different RNG seed.
    cand = contracts[contracts["rate_type"].isin(["per_stream", "per_minute"])].copy()
    cand["_units"] = cand.apply(lambda r: contract_units(r, basis), axis=1)
    premiere = cand[cand["title_id"] == PREMIERE_TITLE_ID]
    pool = premiere if len(premiere) and premiere["_units"].max() > 0 else cand
    esc_idx = pool["_units"].idxmax()

    units = contract_units(contracts.loc[esc_idx], basis)
    threshold = max(1, int(units * 0.4))
    base_rate = float(contracts.loc[esc_idx, "rate_value"])
    escalated = round(base_rate * 1.6, 5)
    contracts.loc[esc_idx, "escalation_threshold_units"] = threshold
    contracts.loc[esc_idx, "escalation_rate_value"] = escalated
    contracts.loc[esc_idx, "source_clause"] = _clause(
        contracts.loc[esc_idx, "rights_holder"],
        contracts.loc[esc_idx, "rate_type"],
        base_rate,
        contracts.loc[esc_idx, "territory"],
        threshold,
        escalated,
    )
    esc_contract_id = str(contracts.loc[esc_idx, "contract_id"])

    flat = contracts[(contracts["rate_type"] == "flat_window") & (contracts.index != esc_idx)]
    if len(flat) == 0:
        flat = contracts[contracts.index != esc_idx]
    flat_contract_id = str(contracts.loc[flat.index[0], "contract_id"])

    return contracts, esc_contract_id, flat_contract_id


def gen_royalty_ledger(
    contracts: pd.DataFrame, basis: dict, esc_contract_id: str, flat_contract_id: str
) -> pd.DataFrame:
    rows = []
    for pid, (_, c) in enumerate(contracts.iterrows(), start=1):
        owed = compute_owed(c, basis)

        if c["contract_id"] == esc_contract_id:
            # Underpayment mechanism: every unit paid at the base rate, as if
            # the escalation tier the contract specifies did not exist.
            amount = contract_units(c, basis) * c["rate_value"]
        elif c["contract_id"] == flat_contract_id:
            # Underpayment mechanism: a plain shortfall against the flat fee.
            amount = owed * RNG.uniform(0.55, 0.75)
        else:
            # Paid correctly, with realistic rounding/FX drift.
            amount = owed * (1.0 + RNG.normal(0, HONEST_DRIFT_PCT))

        rows.append(
            {
                "payment_id": f"p{pid:04d}",
                "contract_id": c["contract_id"],
                "rights_holder": c["rights_holder"],
                "title_id": c["title_id"],
                "territory": c["territory"],
                "period_start": "2026-06-01",
                "period_end": "2026-09-01",
                "amount_paid_usd": round(amount, 2),
                "paid_at": "2026-09-05 09:00:00",
            }
        )
    return pd.DataFrame(rows)


def gen_fraud_signals(play_events: pd.DataFrame, n_users: int, user_home: np.ndarray) -> pd.DataFrame:
    """Session/device features with a realistic legitimate background.

    The ring must NOT be findable by a single equality filter. So the data
    also contains households that really do share one device, venue devices
    with high account fan-out and nothing else suspicious, and ordinary
    VPN/travel users who trip a geo check on their own. Only the ring shows
    extreme fan-out AND impossible travel AND session concurrency together —
    which is exactly the corroboration rule fraud_sentinel is instructed to
    apply.
    """
    n = len(play_events)
    user_idx = play_events["user_id"].str[1:].astype(int).to_numpy()

    # Most accounts own their device; collisions in this mapping produce the
    # natural long tail of 2-3 account households.
    n_devices = int(n_users * 0.88)
    user_device = RNG.integers(0, n_devices, size=n_users)

    # A handful of public/venue devices: genuinely high account fan-out, but
    # no impossible travel and no concurrency spike. Decoys, by design.
    venue_devices = RNG.choice(n_devices, size=N_VENUE_DEVICES, replace=False)
    venue_users: list[int] = []
    for dev in venue_devices:
        k = int(RNG.integers(*VENUE_FANOUT))
        picked = RNG.choice(n_users, size=k, replace=False)
        user_device[picked] = dev
        venue_users.extend(picked.tolist())
    is_venue_user = np.zeros(n_users, dtype=bool)
    is_venue_user[np.array(venue_users, dtype=int)] = True

    fp_pool = np.array([f"fp-{i:08x}" for i in range(n_devices)], dtype=object)

    # The ring: one fingerprint fanned across many accounts watching the
    # premiere, from scattered home territories.
    premiere_users = np.unique(user_idx[play_events["title_id"].to_numpy() == PREMIERE_TITLE_ID])
    ring_users = RNG.choice(
        premiere_users, size=min(FRAUD_CLUSTER_SIZE, len(premiere_users)), replace=False
    )
    is_ring_user = np.zeros(n_users, dtype=bool)
    is_ring_user[ring_users] = True

    device_fp = fp_pool[user_device[user_idx]]
    row_is_ring = is_ring_user[user_idx]
    device_fp[row_is_ring] = FRAUD_SHARED_FINGERPRINT
    row_is_venue = is_venue_user[user_idx] & ~row_is_ring

    territory = play_events["territory"].to_numpy()
    account_home = user_home[user_idx]

    # Ordinary VPN / travelling users: geo mismatch with nothing else wrong.
    ip_geo = territory.copy()
    vpn = (RNG.random(n) < VPN_RATE) & ~row_is_ring
    ip_geo[vpn] = RNG.choice(TERRITORIES, size=int(vpn.sum()))

    impossible_travel = (RNG.random(n) < BASELINE_IMPOSSIBLE_TRAVEL_RATE).astype(int)
    concurrent = RNG.poisson(1, size=n).astype(int)
    device_count = (RNG.poisson(1.2, size=n) + 1).astype(int)
    is_bot_ua = (RNG.random(n) < BASELINE_BOT_UA_RATE).astype(int)

    # Venue devices: more accounts and more devices seen, ordinary everything else.
    kv = int(row_is_venue.sum())
    concurrent[row_is_venue] = RNG.integers(1, 4, size=kv)
    device_count[row_is_venue] = RNG.integers(2, 6, size=kv)

    # The ring: every corroborating signal at once.
    kr = int(row_is_ring.sum())
    impossible_travel[row_is_ring] = 1
    concurrent[row_is_ring] = RNG.integers(8, 20, size=kr)
    device_count[row_is_ring] = RNG.integers(15, 40, size=kr)
    ip_geo[row_is_ring] = RNG.choice(TERRITORIES, size=kr)

    return pd.DataFrame(
        {
            "event_time": play_events["event_time"].values,
            "session_id": play_events["session_id"].values,
            "user_id": play_events["user_id"].values,
            "device_fingerprint": device_fp,
            "ip_geo_territory": ip_geo,
            "account_home_territory": account_home,
            "concurrent_sessions_5min": concurrent,
            "impossible_travel_flag": impossible_travel,
            "device_count_24h": device_count,
            "is_bot_ua": is_bot_ua,
        }
    )


def gen_sentiment_events() -> pd.DataFrame:
    rows = []
    for title_id, name, *_ in TITLES:
        start, end = _title_window(title_id)
        # Sentiment tracks the title from release, not from the premiere date.
        start = max(CATALOG_START, RELEASE_DATES[title_id])
        n_days = max(1, (CATALOG_END - start).days)
        turn = RELEASE_DATES[title_id] + timedelta(days=CHURN_TURN_DAY)
        for day in range(n_days):
            day_ts = start + timedelta(days=day)
            base = RNG.uniform(0.1, 0.6)
            if title_id == CHURN_TITLE_ID and day_ts >= turn:
                base = RNG.uniform(-0.6, -0.1)  # sharp negative turn
            for _ in range(int(RNG.integers(3, 12))):
                score = float(np.clip(RNG.normal(base, 0.25), -1, 1))
                stamp = day_ts + timedelta(minutes=int(RNG.integers(0, 1440)))
                rows.append(
                    {
                        "event_time": stamp.strftime("%Y-%m-%d %H:%M:%S"),
                        "title_id": title_id,
                        "territory": RNG.choice(TERRITORIES),
                        "source": RNG.choice(["review", "social", "app_rating"]),
                        "sentiment_score": round(score, 3),
                        "text_snippet": f"synthetic sentiment sample for {name}",
                    }
                )
    return pd.DataFrame(rows)


def build_basis(play_events: pd.DataFrame, ad_events: pd.DataFrame) -> dict:
    """Per (title, territory) billing basis — all three aggregates an agent
    can reproduce with one GROUP BY each."""
    grp = play_events.groupby(["title_id", "territory"])
    streams = grp.size()
    minutes = grp["watch_seconds"].sum() / 60.0
    ad_rev = ad_events.groupby(["title_id", "territory"])["actual_revenue_usd"].sum()
    basis: dict = {}
    for key, s in streams.items():
        basis[key] = {
            "streams": int(s),
            "minutes": float(minutes.get(key, 0.0)),
            "ad_revenue": float(ad_rev.get(key, 0.0)),
        }
    return basis


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=200_000, help="total play_events rows to generate")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    titles = gen_titles()
    play_events, incident_rows, n_users, user_home = gen_play_events(args.rows)
    ad_events = gen_ad_events(play_events)
    basis = build_basis(play_events, ad_events)

    contracts = gen_rights_contracts()
    contracts, esc_contract_id, flat_contract_id = seed_underpayment_scenarios(contracts, basis)
    ledger = gen_royalty_ledger(contracts, basis, esc_contract_id, flat_contract_id)

    fraud = gen_fraud_signals(play_events, n_users, user_home)
    sentiment = gen_sentiment_events()

    titles.to_csv(OUT_DIR / "titles.csv", index=False)
    play_events.to_csv(OUT_DIR / "play_events.csv", index=False)
    ad_events.to_csv(OUT_DIR / "ad_events.csv", index=False)
    contracts.to_csv(OUT_DIR / "rights_contracts.csv", index=False)
    ledger.to_csv(OUT_DIR / "royalty_ledger.csv", index=False)
    fraud.to_csv(OUT_DIR / "fraud_signals.csv", index=False)
    sentiment.to_csv(OUT_DIR / "sentiment_events.csv", index=False)

    esc = contracts[contracts["contract_id"] == esc_contract_id].iloc[0]
    flat = contracts[contracts["contract_id"] == flat_contract_id].iloc[0]
    esc_owed = compute_owed(esc, basis)
    esc_paid = float(ledger.loc[ledger.contract_id == esc_contract_id, "amount_paid_usd"].iloc[0])
    flat_owed = compute_owed(flat, basis)
    flat_paid = float(ledger.loc[ledger.contract_id == flat_contract_id, "amount_paid_usd"].iloc[0])
    churn_turn = RELEASE_DATES[CHURN_TITLE_ID] + timedelta(days=CHURN_TURN_DAY)

    anomalies = {
        "cdn_incident": {
            "territory": INCIDENT_TERRITORY,
            "cdn_node": INCIDENT_CDN_NODE,
            "window_utc": [INCIDENT_START.isoformat(), INCIDENT_END.isoformat()],
            "title_id": PREMIERE_TITLE_ID,
            "title_name": TITLE_NAMES[PREMIERE_TITLE_ID],
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
            "cluster_size": int(FRAUD_CLUSTER_SIZE),
            "title_id": PREMIERE_TITLE_ID,
            "decoys_present": (
                f"{N_VENUE_DEVICES} venue devices with {VENUE_FANOUT[0]}-{VENUE_FANOUT[1]} accounts "
                "each and no other suspicious signal, plus household device sharing and a "
                f"{VPN_RATE:.1%} VPN/geo-mismatch baseline"
            ),
            "expected_finding": (
                "Stream Fraud Sentinel should rank device_fingerprint="
                f"{FRAUD_SHARED_FINGERPRINT} first: extreme account fan-out AND impossible "
                "travel AND session concurrency together. It should NOT flag the venue "
                "devices, which have fan-out alone."
            ),
        },
        "underpaid_contracts": {
            "escalation_clause_ignored": {
                "contract_id": esc_contract_id,
                "rights_holder": str(esc["rights_holder"]),
                "rate_type": str(esc["rate_type"]),
                "expected_owed_usd": round(esc_owed, 2),
                "actually_paid_usd": round(esc_paid, 2),
                "gap_usd": round(esc_owed - esc_paid, 2),
                "expected_finding": (
                    "This contract's escalation tier genuinely triggered (volume exceeded "
                    "escalation_threshold_units) but every unit was paid at the base rate. "
                    "Chain of Title should recompute the tiered amount and show the gap is "
                    "exactly the escalation tier that was skipped."
                ),
            },
            "flat_fee_shortfall": {
                "contract_id": flat_contract_id,
                "rights_holder": str(flat["rights_holder"]),
                "expected_owed_usd": round(flat_owed, 2),
                "actually_paid_usd": round(flat_paid, 2),
                "gap_usd": round(flat_owed - flat_paid, 2),
                "expected_finding": (
                    "This flat_window contract was paid ~55-75% of the flat fee its own "
                    "terms specify — a plain shortfall, no escalation clause involved."
                ),
            },
            "note": (
                "Every other contract is paid correctly to within a "
                f"{HONEST_DRIFT_PCT:.2%} rounding drift, well under the $50 materiality "
                "threshold, so a correct audit reports exactly these two and no others."
            ),
        },
        "churn_title": {
            "title_id": CHURN_TITLE_ID,
            "title_name": TITLE_NAMES[CHURN_TITLE_ID],
            "release_date": RELEASE_DATES[CHURN_TITLE_ID].date().isoformat(),
            "turn_day_after_release": CHURN_TURN_DAY,
            "turn_date_utc": churn_turn.date().isoformat(),
            "expected_finding": (
                f"Churn Early-Warning should detect the collapse in watch_seconds from "
                f"{churn_turn.date().isoformat()} (day {CHURN_TURN_DAY} after release), "
                "correlated with a sharp negative swing in sentiment_events for this title."
            ),
        },
    }
    (OUT_DIR / "ANOMALIES.json").write_text(json.dumps(anomalies, indent=2, default=str))

    print(f"Wrote {len(play_events):,} play_events ({incident_rows} in the CDN incident window)")
    print(f"  across {n_users:,} distinct subscriber accounts")
    print(f"Wrote {len(ad_events):,} ad_events")
    print(f"Wrote {len(contracts)} rights_contracts, {len(ledger)} royalty_ledger rows")
    print(f"  underpaid: {esc_contract_id} (gap ${esc_owed - esc_paid:,.2f}), "
          f"{flat_contract_id} (gap ${flat_owed - flat_paid:,.2f})")
    print(f"Wrote {len(fraud):,} fraud_signals ({FRAUD_CLUSTER_SIZE} accounts in the ring)")
    print(f"Wrote {len(sentiment):,} sentiment_events")
    print(f"Ground truth written to {OUT_DIR / 'ANOMALIES.json'}")


if __name__ == "__main__":
    main()
