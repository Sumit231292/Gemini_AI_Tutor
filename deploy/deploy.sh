#!/usr/bin/env bash
# ============================================================
# EduNova - Deploy to Google Cloud Run
# 
# Usage:
#   ./deploy.sh [PROJECT_ID] [REGION]
#
# Prerequisites:
#   - gcloud CLI installed and authenticated
#   - Docker installed (for local builds)
#   - Google Cloud project with billing enabled
# ============================================================

set -euo pipefail

# Configuration
PROJECT_ID="${1:-$(gcloud config get-value project 2>/dev/null)}"
REGION="${2:-us-central1}"
SERVICE_NAME="edunova"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

echo "================================================"
echo "  EduNova - Cloud Run Deployment"
echo "================================================"
echo "  Project:  ${PROJECT_ID}"
echo "  Region:   ${REGION}"
echo "  Service:  ${SERVICE_NAME}"
echo "  Image:    ${IMAGE_NAME}"
echo "================================================"
echo ""

# ── Step 1: Enable required APIs ──
echo "📦 Enabling required Google Cloud APIs..."
gcloud services enable \
    run.googleapis.com \
    cloudbuild.googleapis.com \
    containerregistry.googleapis.com \
    aiplatform.googleapis.com \
    --project="${PROJECT_ID}" \
    --quiet

echo "✅ APIs enabled"

# ── Step 2: Build and push container ──
echo ""
echo "🐳 Building and pushing container image..."

# Copy frontend into backend context for Docker build
cp -r ../frontend ../backend/frontend_build 2>/dev/null || true

cd ../backend

# Build using Cloud Build (no local Docker needed)
gcloud builds submit \
    --tag "${IMAGE_NAME}" \
    --project="${PROJECT_ID}" \
    --quiet

# Clean up copied frontend
rm -rf frontend_build 2>/dev/null || true

echo "✅ Container image built and pushed"

# ── Step 3: Deploy to Cloud Run ──
echo ""
echo "🚀 Deploying to Cloud Run..."

gcloud run deploy "${SERVICE_NAME}" \
    --image "${IMAGE_NAME}" \
    --platform managed \
    --region "${REGION}" \
    --project="${PROJECT_ID}" \
    --allow-unauthenticated \
    --port 8080 \
    --memory 1Gi \
    --cpu 2 \
    --min-instances 0 \
    --max-instances 10 \
    --timeout 3600 \
    --set-env-vars "GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_REGION=${REGION}" \
    --session-affinity \
    --quiet

# ── Step 4: Get the URL ──
echo ""
SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" \
    --platform managed \
    --region "${REGION}" \
    --project="${PROJECT_ID}" \
    --format "value(status.url)")

echo "================================================"
echo "  ✅ Deployment Complete!"
echo "================================================"
echo ""
echo "  🌐 URL: ${SERVICE_URL}"
echo ""
echo "  To set the API key (if not using Vertex AI):"
echo "  gcloud run services update ${SERVICE_NAME} \\"
echo "    --region ${REGION} \\"
echo "    --set-env-vars GOOGLE_API_KEY=your-key-here"
echo ""
echo "  To view logs:"
echo "  gcloud run services logs read ${SERVICE_NAME} --region ${REGION}"
echo ""
echo "================================================"
