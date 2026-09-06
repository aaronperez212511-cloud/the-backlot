#!/usr/bin/env bash
# Deploys The Backlot to Cloud Run in the-backlot-fleet.
#
# One-time setup (run once, before the first deploy):
#   gcloud secrets create clickhouse-host     --data-file=- <<< "your-instance.clickhouse.cloud"
#   gcloud secrets create clickhouse-user     --data-file=- <<< "default"
#   gcloud secrets create clickhouse-password --data-file=- <<< "your-password"
#   # Shared secret for the Watchtower trigger. The service runs
#   # --allow-unauthenticated so judges need no Google account, which means
#   # /api/watch/run would otherwise be an open button for burning Gemini
#   # quota. Any long random string works:
#   gcloud secrets create watch-token --data-file=- <<< "$(openssl rand -hex 24)"
#   gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
#       aiplatform.googleapis.com secretmanager.googleapis.com \
#       cloudscheduler.googleapis.com
#
# After deploying, put the fleet on a clock with deploy/schedule.sh.
set -euo pipefail

PROJECT_ID="the-backlot-fleet"
REGION="us-central1"
SERVICE="the-backlot"

gcloud builds submit --project "$PROJECT_ID" --tag "gcr.io/${PROJECT_ID}/${SERVICE}"

gcloud run deploy "$SERVICE" \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --image "gcr.io/${PROJECT_ID}/${SERVICE}" \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 600 \
  --concurrency 8 \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_LOCATION=${REGION},GOOGLE_GENAI_USE_VERTEXAI=TRUE" \
  --set-secrets "CLICKHOUSE_HOST=clickhouse-host:latest,CLICKHOUSE_USER=clickhouse-user:latest,CLICKHOUSE_PASSWORD=clickhouse-password:latest,WATCH_TOKEN=watch-token:latest"

echo "Deployed. URL:"
gcloud run services describe "$SERVICE" --project "$PROJECT_ID" --region "$REGION" --format='value(status.url)'
echo
echo "Next: ./deploy/schedule.sh  — puts the Watchtower on an hourly clock."
