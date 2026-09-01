"""Contract Intelligence: turns messy rights-contract prose into computable
royalty rules. This is the one step in The Backlot that a SQL query alone
cannot do — a human still writes these contracts in ordinary language, and
someone (or something) has to turn that language into arithmetic before any
reconciliation is possible.
"""
from __future__ import annotations

import json
import os

from google import genai
from google.genai import types

from common.models import RETRY_OPTIONS

_MODEL = "gemini-2.5-pro"

_PROMPT = """Extract structured royalty terms from this rights-contract clause.
Return strict JSON with exactly these keys:
- rate_type: one of "per_stream", "per_minute", "revenue_share_pct", "flat_window"
- rate_value: number
- territory: ISO-2 country code
- escalation_threshold_units: number or null
- escalation_threshold_unit_name: the unit the threshold is counted in, exactly
  as the clause words it (e.g. "streams", "attributed minutes"), or null
- escalation_rate_value: number or null
- plain_english: one sentence restating the obligation for a non-lawyer

The threshold's unit matters as much as its number: a clause that bills per
attributed minute escalates after a count of MINUTES, not streams. Report the
unit the clause actually names, never the one you would expect.

Clause:
{clause_text}
"""


def parse_rights_clause(clause_text: str) -> dict:
    """Extracts structured, computable royalty terms from a raw rights-contract clause.

    Args:
        clause_text (str): Raw contract language, e.g. "Elena Vasquez shall
            receive 0.014 per stream in BR, escalating to 0.021 after
            200000 streams."

    Returns:
        dict: rate_type, rate_value, territory, escalation_threshold_units,
        escalation_rate_value, and plain_english — ready to compare against
        what was actually paid.
    """
    client = genai.Client(
        vertexai=True,
        project=os.environ["GOOGLE_CLOUD_PROJECT"],
        location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
        # This call is made from inside a tool, mid-audit. A transient 429 from
        # Vertex's shared quota here would abort the whole reconciliation, so
        # it retries on the same terms as the agents' own model calls.
        http_options=types.HttpOptions(retry_options=RETRY_OPTIONS),
    )
    response = client.models.generate_content(
        model=_MODEL,
        contents=_PROMPT.format(clause_text=clause_text),
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    return json.loads(response.text)
