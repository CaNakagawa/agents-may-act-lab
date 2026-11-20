variable "project_id" {
  description = "The participant's disposable GCP project ID."
  type        = string
}

variable "region" {
  description = "Region containing the single-zone training cluster."
  type        = string
  default     = "us-east4"
}

variable "zone" {
  description = "Zone for the training cluster and node pool."
  type        = string
  default     = "us-east4-b"
}

variable "cluster_name" {
  description = "Name for the new training cluster."
  type        = string
  default     = "agents-may-act-lab"
}

variable "machine_type" {
  description = "Node machine type. The default is sized for a small lab, not production."
  type        = string
  default     = "e2-standard-2"
}
