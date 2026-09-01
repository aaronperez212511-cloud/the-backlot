"""
Builds the ADK eval set for Control Room straight out of ANOMALIES.json.

The generator writes the ground truth; this turns that same ground truth into
rubrics an LLM judge scores the agents against. Deriving the rubrics from the
file rather than hand-writing them means the eval can never quietly drift out
of sync with the data — regenerate the dataset and the expectations move with
it.

    python eval/build_evalset.py
    python -m google.adk.cli eval orchestrator eval/backlot.evalset.json \
        --config_file_path eval/test_config.json
"""
from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TRUTH = ROOT / "data" / "generated" / "ANOMALIES.json"
OUT = Path(__file__).parent / "backlot.evalset.json"


def rubric(rid: str, text: str) -> dict:
    return {"rubric_id": rid, "rubric_content": {"text_property": text}}


def case(eval_id: str, prompt: str, rubrics: list[dict]) -> dict:
    return {
        "eval_id": eval_id,
        "conversation": [
            {
                "invocation_id": f"{eval_id}-1",
                "user_content": {"role": "user", "parts": [{"text": prompt}]},
                "creation_timestamp": time.time(),
            }
        ],
        "rubrics": rubrics,
        "creation_timestamp": time.time(),
    }


def build(truth: dict) -> dict:
    cdn = truth["cdn_incident"]
    fraud = truth["fraud_ring"]
    esc = truth["underpaid_contracts"]["escalation_clause_ignored"]
    flat = truth["underpaid_contracts"]["flat_fee_shortfall"]
    churn = truth["churn_title"]
    node, terr = cdn["cdn_node"], cdn["territory"]

    cases = [
        # The flagship. This is the case that fails outright if the orchestrator
        # ever goes back to control-transfer delegation, because a single
        # specialist cannot satisfy both halves of it.
        case(
            "premiere_cross_domain_correlation",
            "What happened during the Midnight Marquee premiere in Brazil? "
            "Check both playback health and ad revenue, and tell me whether "
            "they share a root cause.",
            [
                rubric("names_degraded_node",
                       f"The response identifies the specific failing CDN edge node '{node}' "
                       f"in territory {terr} as the location of the problem."),
                rubric("names_time_window",
                       "The response states the specific time window of the degradation "
                       f"(approximately {cdn['window_utc'][0][11:16]}-{cdn['window_utc'][1][11:16]} UTC), "
                       "rather than describing the problem vaguely."),
                rubric("reports_playback_symptom",
                       "The response reports the playback symptom with concrete numbers: "
                       "elevated buffering time, rebuffering, or viewer drop-off rate."),
                rubric("reports_ad_symptom",
                       "The response reports the advertising symptom: SSAI ad-stitching "
                       "failures, quantified as lost revenue in dollars."),
                rubric("correlates_single_root_cause",
                       "The response explicitly concludes that the playback degradation and "
                       "the ad-insertion failures are TWO SYMPTOMS OF ONE root cause on the "
                       "same node in the same window — not two separate unrelated problems "
                       "listed side by side."),
                rubric("consulted_multiple_specialists",
                       "The answer draws on both playback telemetry and advertising data, "
                       "showing more than one specialist domain was consulted."),
            ],
        ),
        case(
            "royalty_forensic_audit",
            "Audit the royalty payments across the catalog. Show me the "
            "arithmetic behind any discrepancy you find.",
            [
                rubric("finds_escalation_contract",
                       f"The response identifies contract {esc['contract_id']} "
                       f"({esc['rights_holder']}) as underpaid."),
                rubric("explains_escalation_cause",
                       "The response explains the root cause of that underpayment as an "
                       "escalation tier that was triggered but paid at the base rate — the "
                       "escalation clause was effectively ignored."),
                rubric("finds_flat_contract",
                       f"The response identifies contract {flat['contract_id']} "
                       f"({flat['rights_holder']}) as underpaid against a flat fee."),
                rubric("shows_arithmetic",
                       "The response shows its working: the unit count (streams, minutes or "
                       "attributed revenue), the rate(s) applied, the expected total, the "
                       "amount actually paid, and the resulting gap in dollars."),
                rubric("gap_magnitudes_correct",
                       f"The reported gaps are approximately ${esc['gap_usd']:,.2f} for "
                       f"{esc['contract_id']} and ${flat['gap_usd']:,.2f} for "
                       f"{flat['contract_id']} (within about 5%)."),
                rubric("no_false_positives",
                       "The response does NOT claim that contracts other than these two are "
                       "materially underpaid. Every other contract is correct to within "
                       "ordinary rounding drift."),
            ],
        ),
        case(
            "fraud_ring_discrimination",
            "Is anyone watching this premiere who shouldn't be? "
            "Rank anything suspicious and tell me why.",
            [
                rubric("identifies_ring_fingerprint",
                       f"The response identifies device fingerprint "
                       f"'{fraud['shared_fingerprint']}' as the top suspicious cluster."),
                rubric("quantifies_blast_radius",
                       f"The response quantifies the ring: approximately "
                       f"{fraud['cluster_size']} distinct accounts sharing one device."),
                rubric("cites_corroborating_signals",
                       "The response justifies the flag with at least two corroborating "
                       "signals — e.g. account fan-out AND impossible travel AND/OR "
                       "session concurrency — not fan-out alone."),
                rubric("does_not_flag_decoys",
                       "The response does NOT flag ordinary shared-device households or "
                       "public/venue devices as fraud. Those have high account fan-out but "
                       "no impossible travel and no concurrency spike, and are legitimate."),
            ],
        ),
        case(
            "churn_early_signal",
            "Is any title losing its audience? If so, when did it turn and why?",
            [
                rubric("identifies_churn_title",
                       f"The response identifies '{churn['title_name']}' "
                       f"({churn['title_id']}) as the title at retention risk."),
                rubric("identifies_turn_date",
                       f"The response names when the decline began, around "
                       f"{churn['turn_date_utc']} (roughly day {churn['turn_day_after_release']} "
                       "after release)."),
                rubric("quantifies_decline",
                       "The response quantifies the decline in average watch time as a "
                       "percentage or absolute change, rather than asserting it vaguely."),
                rubric("corroborates_with_sentiment",
                       "The response cross-checks sentiment data and notes that sentiment "
                       "turned negative over the same period, strengthening the signal."),
            ],
        ),
        # The restraint test. An agent fleet that finds a crisis everywhere is
        # worthless in an ops setting; this scores the ability to say
        # "nothing is wrong here".
        case(
            "restraint_no_invented_incident",
            "Was there any CDN or ad-delivery incident affecting Nova Horizon "
            "in Japan? Be precise.",
            [
                rubric("reports_no_incident",
                       "The response states that no significant incident was found for that "
                       "title/territory, rather than manufacturing one to seem useful."),
                rubric("backs_it_with_data",
                       "The response supports that conclusion with actual queried figures "
                       "(e.g. buffering and fill rates near baseline), not just an assertion."),
                rubric("no_fabrication",
                       "The response does not invent specific incidents, node names, time "
                       "windows or dollar losses that it did not obtain from the data."),
            ],
        ),
    ]

    return {
        "eval_set_id": "backlot_ground_truth",
        "name": "The Backlot — ground-truth agent evaluation",
        "description": (
            "Scores Control Room against the anomalies deliberately seeded into the "
            "ClickHouse dataset. Rubrics are generated from data/generated/ANOMALIES.json, "
            "so they always describe the data that is actually loaded. Includes two "
            "negative cases — no false-positive royalty findings, and no invented incident "
            "— because an agent that always finds something is not a useful one."
        ),
        "eval_cases": cases,
        "creation_timestamp": time.time(),
    }


def main() -> None:
    if not TRUTH.exists():
        raise SystemExit(
            f"{TRUTH} not found — run data/generate_synthetic_data.py first."
        )
    evalset = build(json.loads(TRUTH.read_text()))
    OUT.write_text(json.dumps(evalset, indent=2))
    n_rubrics = sum(len(c["rubrics"]) for c in evalset["eval_cases"])
    print(f"Wrote {OUT}")
    print(f"  {len(evalset['eval_cases'])} eval cases, {n_rubrics} rubrics, "
          "all derived from ANOMALIES.json")


if __name__ == "__main__":
    main()
