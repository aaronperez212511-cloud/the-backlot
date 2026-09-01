"""Model configuration shared by the whole fleet.

Gemini 2.5 Pro and Flash run on Vertex AI's **dynamic shared quota**: there is
no fixed per-project requests-per-minute ceiling to stay under, and no quota
increase to request. Capacity is allocated dynamically, which means contention
surfaces as a `429 RESOURCE_EXHAUSTED` at unpredictable moments rather than at
a documented limit.

That matters here more than in a single-agent app. One Control Room question
fans out to several specialists, each of which makes its own model calls, so a
single user request can be a burst of Gemini traffic — and several judges
trying the hosted demo at once multiplies it. Without retries, a transient 429
reaches the console as a raw error on the one investigation someone is
watching.

Every agent therefore takes a `Gemini` model object carrying retry options,
not a bare model-name string.
"""
from __future__ import annotations

from google.adk.models.google_llm import Gemini
from google.genai import types

PRO = "gemini-2.5-pro"
FLASH = "gemini-2.5-flash"

# Retries cover 429 (shared-quota contention) and the transient 5xx family.
# Roughly 1s, 2s, 4s, 8s between attempts with jitter, capped at 30s — long
# enough to ride out a burst, short enough that a judge is not left staring at
# a spinner. Cloud Run's request timeout is 600s (see deploy/deploy.sh), which
# leaves ample room for this on top of a multi-specialist investigation.
RETRY_OPTIONS = types.HttpRetryOptions(
    attempts=5,
    initial_delay=1.0,
    max_delay=30.0,
    exp_base=2.0,
    jitter=0.3,
    http_status_codes=[429, 500, 502, 503, 504],
)


def gemini(model_name: str) -> Gemini:
    """A Gemini model wired for the fleet's burst pattern."""
    return Gemini(model=model_name, retry_options=RETRY_OPTIONS)
