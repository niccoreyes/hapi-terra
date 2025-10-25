output "cluster_name" {
  value = module.eks.cluster_id
}

output "kubeconfig" {
  value       = module.eks.kubeconfig
  description = "Kubeconfig (raw). Use aws eks update-kubeconfig instead for direct use."
}

output "hapi_service" {
  value       = { for mode, release in helm_release.hapi_fhir : mode => release.status }
  description = "Helm release status by deployment mode."
}
