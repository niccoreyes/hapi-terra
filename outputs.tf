output "cluster_name" {
  value       = module.eks.cluster_name
  description = "EKS cluster name."
}

output "cluster_endpoint" {
  value       = module.eks.cluster_endpoint
  description = "EKS control plane endpoint URL."
}

output "cluster_certificate_authority_data" {
  value       = module.eks.cluster_certificate_authority_data
  description = "Base64-encoded cluster CA certificate."
  sensitive   = true
}

output "hapi_service" {
  value       = { for mode, release in helm_release.hapi_fhir : mode => release.status }
  description = "Helm release status by deployment mode."
}
