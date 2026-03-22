resource "google_artifact_registry_repository" "janani" {
  location      = var.region
  repository_id = "janani-suraksha"
  description   = "JananiSuraksha Docker images"
  format        = "DOCKER"

  cleanup_policies {
    id     = "keep-minimum-versions"
    action = "KEEP"
    most_recent_versions {
      keep_count = 5
    }
  }
}
