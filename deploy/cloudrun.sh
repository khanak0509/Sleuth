#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:?set PROJECT_ID}"
REGION="${REGION:-asia-south1}"
SERVICE="${SERVICE:-sleuth-api}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

gcloud config set project "$PROJECT_ID" >/dev/null

gcloud services enable \
  run.googleapis.com cloudbuild.googleapis.com \
  artifactregistry.googleapis.com secretmanager.googleapis.com

PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
RUNTIME_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

put_secret() {
  local name="$1" value="$2"
  if ! gcloud secrets describe "$name" >/dev/null 2>&1; then
    printf %s "$value" | gcloud secrets create "$name" --replication-policy=automatic --data-file=-
  else
    printf %s "$value" | gcloud secrets versions add "$name" --data-file=- >/dev/null
  fi
  gcloud secrets add-iam-policy-binding "$name" \
    --member="serviceAccount:${RUNTIME_SA}" \
    --role=roles/secretmanager.secretAccessor >/dev/null
}

SECRETS="OPENAI_API_KEY=openai-api-key:latest"
if [[ -n "${OPENAI_API_KEY:-}" ]]; then
  put_secret openai-api-key "$OPENAI_API_KEY"
elif ! gcloud secrets describe openai-api-key >/dev/null 2>&1; then
  echo "OPENAI_API_KEY not set" >&2
  exit 1
fi
if [[ -n "${GITHUB_TOKEN:-}" ]]; then
  put_secret github-token "$GITHUB_TOKEN"
fi
if gcloud secrets describe github-token >/dev/null 2>&1; then
  SECRETS="${SECRETS},GITHUB_TOKEN=github-token:latest"
fi

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${RUNTIME_SA}" --role=roles/run.builder \
  --condition=None >/dev/null || true

gcloud run deploy "$SERVICE" \
  --source "${ROOT}/backend" \
  --region "$REGION" \
  --quiet \
  --no-allow-unauthenticated \
  --cpu 2 --memory 4Gi \
  --no-cpu-throttling --cpu-boost \
  --min-instances 0 --max-instances 1 \
  --concurrency 8 --timeout 300 \
  --set-secrets "$SECRETS" \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=${PROJECT_ID}"

gcloud run services describe "$SERVICE" --region "$REGION" --format='value(status.url)'
