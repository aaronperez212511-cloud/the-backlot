#!/usr/bin/env bash
# Puts The Backlot's fleet on a clock.
#
# This is what makes the system autonomous rather than merely interactive: a
# Cloud Scheduler job calls POST /api/watch/run every hour, the Watchtower
# runs its standing briefs against Control Room with no human in the loop, and
# the findings land in ClickHouse whether or not anyone has the console open.
#
# Why Cloud Scheduler and not a loop inside the container: Cloud Run freezes
# an idle instance's CPU and scales to zero. A `while True: sleep` scheduler
# inside the process therefore stops running the moment nobody is holding a
# request open — the exact condition an unattended watch exists to cover. An
# external clock making a real request is the only trigger that survives it.
#
# Run deploy/deploy.sh first. Requires the scheduler API:
#   gcloud services enable cloudscheduler.googleapis.com --project the-backlot-fleet
set -euo pipefail

PROJECT_ID="the-backlot-fleet"
REGION="us-central1"
SERVICE="the-backlot"
JOB="backlot-watchtower"
SCHEDULE="${SCHEDULE:-0 * * * *}"          # hourly, on the hour
TIMEZONE="${TIMEZONE:-Etc/UTC}"

SERVICE_URL="$(gcloud run services describe "$SERVICE" \
  --project "$PROJECT_ID" --region "$REGION" --format='value(status.url)')"

# The same shared secret the service checks in _authorise(). Created by
# deploy.sh; read back here so the two can never drift apart.
WATCH_TOKEN="$(gcloud secrets versions access latest \
  --secret=watch-token --project "$PROJECT_ID")"

# `create` fails if the job exists, so try update first and fall back. Keeps
# this script safe to re-run, which matters when you are tuning the cadence.
ARGS=(
  --project "$PROJECT_ID"
  --location "$REGION"
  --schedule "$SCHEDULE"
  --time-zone "$TIMEZONE"
  --uri "${SERVICE_URL}/api/watch/run"
  --http-method POST
  # The body is not optional, and its absence fails in a way that looks like
  # nothing happened at all. Cloud Scheduler sends a bodyless POST without a
  # Content-Length header, and Google Front End rejects that with 411 Length
  # Required BEFORE it reaches Cloud Run — so there is no request in the
  # service logs, no error in the app, and the scheduler job simply reports a
  # failed attempt with no detail. Same family as serving health on
  # /api/health rather than /healthz: GFE gets there first.
  --message-body "{}"
  # The endpoint answers 202 in milliseconds and does the work in the
  # background, so this deadline covers the handoff, not the investigation.
  --attempt-deadline 30s
  --description "Runs The Backlot's standing investigations unattended."
)

HEADERS="X-Watch-Token=${WATCH_TOKEN},Content-Type=application/json"

# The header flag is spelled differently on the two subcommands: `create` takes
# --headers, `update` only accepts --update-headers and rejects --headers
# outright. Sharing one ARGS array between them therefore works on the first
# run and fails on every re-run, which is the least useful place for a script
# to break.
if gcloud scheduler jobs describe "$JOB" --project "$PROJECT_ID" --location "$REGION" >/dev/null 2>&1; then
  gcloud scheduler jobs update http "$JOB" "${ARGS[@]}" --update-headers "$HEADERS"
else
  gcloud scheduler jobs create http "$JOB" "${ARGS[@]}" --headers "$HEADERS"
fi

echo
echo "Scheduled '${JOB}' — ${SCHEDULE} (${TIMEZONE}) → ${SERVICE_URL}/api/watch/run"
echo
echo "Run one sweep right now, without waiting for the hour:"
echo "  gcloud scheduler jobs run ${JOB} --project ${PROJECT_ID} --location ${REGION}"
echo
echo "Then read what it found:"
echo "  curl -s ${SERVICE_URL}/api/watch/findings | python -m json.tool"
