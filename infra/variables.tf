variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region for deployment"
  type        = string
  default     = "asia-south1"
}

variable "service_name" {
  description = "Cloud Run service name"
  type        = string
  default     = "janani-suraksha"
}

variable "image_tag" {
  description = "Docker image tag"
  type        = string
  default     = "latest"
}

variable "max_instances" {
  description = "Maximum Cloud Run instances"
  type        = number
  default     = 10
}

variable "min_instances" {
  description = "Minimum Cloud Run instances (0 for scale-to-zero)"
  type        = number
  default     = 0
}

variable "cpu" {
  description = "CPU allocation per instance"
  type        = string
  default     = "2"
}

variable "memory" {
  description = "Memory allocation per instance"
  type        = string
  default     = "4Gi"
}

variable "domain" {
  description = "Custom domain (optional, configure DNS separately)"
  type        = string
  default     = "jananisuraksha.dmj.one"
}

variable "google_maps_api_key" {
  description = "Google Maps API key for facility maps and geocoding"
  type        = string
  sensitive   = true
  default     = ""
}

variable "data_gov_api_key" {
  description = "data.gov.in API key for real facility data"
  type        = string
  sensitive   = true
  default     = ""
}

variable "telegram_bot_token" {
  description = "Telegram bot token for alerts"
  type        = string
  sensitive   = true
  default     = ""
}

variable "telegram_chat_id" {
  description = "Telegram chat ID for alert delivery"
  type        = string
  default     = ""
}
