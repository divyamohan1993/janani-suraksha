resource "google_cloud_run_v2_service" "janani" {
  name     = var.service_name
  location = var.region

  template {
    scaling {
      min_instance_count = var.min_instances
      max_instance_count = var.max_instances
    }

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.janani.repository_id}/${var.service_name}:${var.image_tag}"

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = var.cpu
          memory = var.memory
        }
        cpu_idle          = true
        startup_cpu_boost = true
      }

      env {
        name  = "JANANI_DEBUG"
        value = "false"
      }

      env {
        name  = "JANANI_ALLOWED_ORIGINS"
        value = "[\"https://${var.domain}\", \"https://${var.service_name}-*.run.app\"]"
      }

      env {
        name  = "JANANI_GOOGLE_MAPS_API_KEY"
        value = var.google_maps_api_key
      }

      env {
        name  = "JANANI_DATA_GOV_API_KEY"
        value = var.data_gov_api_key
      }

      env {
        name  = "JANANI_TELEGRAM_BOT_TOKEN"
        value = var.telegram_bot_token
      }

      env {
        name  = "JANANI_TELEGRAM_CHAT_ID"
        value = var.telegram_chat_id
      }

      startup_probe {
        http_get {
          path = "/api/v1/health"
        }
        initial_delay_seconds = 5
        period_seconds        = 10
        failure_threshold     = 3
      }

      liveness_probe {
        http_get {
          path = "/api/v1/health"
        }
        period_seconds = 30
      }
    }

    timeout = "300s"
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }
}

resource "google_cloud_run_v2_service_iam_member" "public" {
  project  = google_cloud_run_v2_service.janani.project
  location = google_cloud_run_v2_service.janani.location
  name     = google_cloud_run_v2_service.janani.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
