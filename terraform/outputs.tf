output "cluster_name" {
  value = google_container_cluster.lab.name
}

output "connect_command" {
  value = "gcloud container clusters get-credentials ${google_container_cluster.lab.name} --zone=${var.zone} --project=${var.project_id}"
}

output "node_service_account" {
  value = google_service_account.nodes.email
}
