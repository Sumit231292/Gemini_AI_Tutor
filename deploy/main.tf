# ============================================================
# EduNova - Terraform Configuration (Bonus: IaC)
# Infrastructure as Code for automated Cloud deployment
# ============================================================

terraform {
  required_version = ">= 1.5.0"
  
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

# ── Variables ──
variable "project_id" {
  description = "Google Cloud project ID"
  type        = string
}

variable "region" {
  description = "Google Cloud region"
  type        = string
  default     = "us-central1"
}

variable "google_api_key" {
  description = "Google AI API key (optional if using Vertex AI)"
  type        = string
  default     = ""
  sensitive   = true
}

# ── Provider ──
provider "google" {
  project = var.project_id
  region  = var.region
}

# ── Enable Required APIs ──
resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com",
    "cloudbuild.googleapis.com",
    "containerregistry.googleapis.com",
    "aiplatform.googleapis.com",
    "firestore.googleapis.com",
  ])

  project = var.project_id
  service = each.value

  disable_dependent_services = false
  disable_on_destroy         = false
}

# ── Artifact Registry Repository ──
resource "google_artifact_registry_repository" "edunova" {
  location      = var.region
  repository_id = "edunova"
  format        = "DOCKER"
  description   = "Docker repository for EduNova"

  depends_on = [google_project_service.apis]
}

# ── Cloud Run Service ──
resource "google_cloud_run_v2_service" "edunova" {
  name     = "edunova"
  location = var.region

  template {
    containers {
      image = "gcr.io/${var.project_id}/edunova:latest"

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "2"
          memory = "1Gi"
        }
      }

      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }

      env {
        name  = "GOOGLE_CLOUD_REGION"
        value = var.region
      }

      dynamic "env" {
        for_each = var.google_api_key != "" ? [1] : []
        content {
          name  = "GOOGLE_API_KEY"
          value = var.google_api_key
        }
      }
    }

    scaling {
      min_instance_count = 0
      max_instance_count = 10
    }

    timeout = "3600s"

    session_affinity = true
  }

  traffic {
    percent = 100
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
  }

  depends_on = [google_project_service.apis]
}

# ── IAM: Allow unauthenticated access ──
resource "google_cloud_run_v2_service_iam_member" "public" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.edunova.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# ── Outputs ──
output "service_url" {
  description = "The URL of the deployed Cloud Run service"
  value       = google_cloud_run_v2_service.edunova.uri
}

output "project_id" {
  description = "Google Cloud project ID"
  value       = var.project_id
}
