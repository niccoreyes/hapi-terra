provider "kubernetes" {
  host                   = module.eks.cluster_endpoint
  cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)

  exec {
    api_version = "client.authentication.k8s.io/v1beta1"
    command     = "aws"
    args        = ["eks", "get-token", "--cluster-name", module.eks.cluster_name]
  }
}

provider "helm" {
  kubernetes = {
    host                   = module.eks.cluster_endpoint
    cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)
    exec = {
      api_version = "client.authentication.k8s.io/v1beta1"
      command     = "aws"
      args        = ["eks", "get-token", "--cluster-name", module.eks.cluster_name]
    }
  }
}

locals {
  hapi_modes = var.hapi_mode == "both" ? ["general", "terminology"] : [var.hapi_mode]
  hapi_values_files = {
    general     = "${path.module}/hapi-values-general.yaml"
    terminology = "${path.module}/hapi-values-terminology.yaml"
  }
}

resource "helm_release" "hapi_fhir" {
  for_each = { for mode in local.hapi_modes : mode => mode }

  name = each.key == "terminology" ? "hapi-fhir-terminology" : "hapi-fhir"
  # repository = "https://hapifhir.github.io/hapi-fhir-jpaserver-starter"
  # chart      = "hapi-fhir-jpaserver"
  chart = "hapi-fhir-jpaserver-0.21.0.tgz"
  # version    = var.hapi_chart_version

  values = [
    file(local.hapi_values_files[each.key])
  ]

  timeout           = 1000
  atomic            = true
  dependency_update = true

  depends_on = [
    module.eks,
    aws_eks_addon.ebs_csi,
    kubernetes_storage_class_v1.gp3
  ]
}
