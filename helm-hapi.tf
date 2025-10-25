data "aws_eks_cluster" "cluster" {
  name = module.eks.cluster_id
}

data "aws_eks_cluster_auth" "cluster" {
  name = module.eks.cluster_id
}

provider "kubernetes" {
  host                   = data.aws_eks_cluster.cluster.endpoint
  token                  = data.aws_eks_cluster_auth.cluster.token
  cluster_ca_certificate = base64decode(data.aws_eks_cluster.cluster.certificate_authority[0].data)
}

provider "helm" {
  kubernetes = {
    host                   = data.aws_eks_cluster.cluster.endpoint
    token                  = data.aws_eks_cluster_auth.cluster.token
    cluster_ca_certificate = base64decode(data.aws_eks_cluster.cluster.certificate_authority[0].data)
  }
}

locals {
  hapi_modes = var.hapi_mode == "both" ? ["general", "terminology"] : [var.hapi_mode]
  hapi_values_files = {
    general      = "${path.module}/hapi-values-general.yaml"
    terminology  = "${path.module}/hapi-values-terminology.yaml"
  }
}

resource "helm_release" "hapi_fhir" {
  for_each = { for mode in local.hapi_modes : mode => mode }

  name       = each.key == "terminology" ? "hapi-fhir-terminology" : "hapi-fhir"
  repository = "https://hapifhir.github.io/hapi-fhir-jpaserver-starter"
  chart      = "hapi-fhir-jpaserver"
  version    = var.hapi_chart_version

  values = [
    file(local.hapi_values_files[each.key])
  ]

  timeout           = 600
  atomic            = true
  dependency_update = true
}
