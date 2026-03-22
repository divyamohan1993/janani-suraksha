output "service_url" {
  description = "Cloud Run service URL"
  value       = google_cloud_run_v2_service.janani.uri
}

output "artifact_registry" {
  description = "Artifact Registry repository path"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.janani.repository_id}"
}

output "service_name" {
  description = "Cloud Run service name"
  value       = google_cloud_run_v2_service.janani.name
}
