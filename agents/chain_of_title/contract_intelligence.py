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

_MODEL = "gemini-2.5-pro"

_PROMPT = """Extract structured royalty terms from this rights-contract clause.
Return strict JSON with exactly these keys:
- rate_type: one of "per_stream", "per_minute", "revenue_share_pct", "flat_window"
- rate_value: number
- territory: ISO-2 country code
- escalation_threshold_streams: number or null
- escalation_rate_value: number or null
- plain_english: one sentence restating the obligation for a non-lawyer

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
        dict: rate_type, rate_value, territory, escalation_threshold_streams,
        escalation_rate_value, and plain_english — ready to compare against
        what was actually paid.
    """
    client = genai.Client(
        vertexai=True,
        project=os.environ["GOOGLE_CLOUD_PROJECT"],
        location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
    )
    response = client.models.generate_content(
        model=_MODEL,
        contents=_PROMPT.format(clause_text=clause_text),
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    return json.loads(response.text)
