module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = ">= 3.0"

  name = "${var.cluster_name}-vpc"
  cidr = "10.0.0.0/16"

  azs             = slice(data.aws_availability_zones.available.names, 0, 2)
  public_subnets  = ["10.0.1.0/24", "10.0.2.0/24"]
  private_subnets = ["10.0.101.0/24", "10.0.102.0/24"]

  enable_nat_gateway = true
  single_nat_gateway = true

  tags = {
    Terraform   = "true"
    Environment = var.environment
  }
}

data "aws_availability_zones" "available" {}

locals {
  k8s_version_numeric  = tonumber(replace(var.k8s_version, ".", ""))
  # Default to AL2023 going forward; fall back to AL2 for pre-1.28 clusters.
  eks_default_ami_type = local.k8s_version_numeric >= 128 ? "AL2023_x86_64_STANDARD" : "AL2_x86_64"
  eks_node_ami_type    = var.node_ami_type != "" ? var.node_ami_type : local.eks_default_ami_type

  eks_remote_access = var.ssh_key_name != "" ? {
    ec2_ssh_key = var.ssh_key_name
  } : null

  eks_common_node_group = {
    capacity_type              = "ON_DEMAND"
    ami_type                   = local.eks_node_ami_type
    create_launch_template     = local.eks_remote_access == null
    use_custom_launch_template = local.eks_remote_access == null
    remote_access              = local.eks_remote_access
  }

  eks_default_node_group = merge(local.eks_common_node_group, {
    desired_size   = var.node_desired_capacity
    max_size       = var.node_max_capacity
    min_size       = var.node_min_capacity
    instance_types = [var.node_instance_type]
    labels = {
      workload = "hapi-general"
      role     = "general"
    }
  })

  eks_terminology_node_group = merge(local.eks_common_node_group, {
    desired_size   = var.terminology_node_desired_capacity
    max_size       = var.terminology_node_max_capacity
    min_size       = var.terminology_node_min_capacity
    instance_types = [var.terminology_node_instance_type]
    labels = {
      workload = "hapi-terminology"
      role     = "terminology"
    }
    taints = {
      terminology = {
        key    = "role"
        value  = "terminology"
        effect = "NO_SCHEDULE"
      }
    }
  })
}

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 21.0"

  name                                     = var.cluster_name
  kubernetes_version                       = var.k8s_version
  vpc_id                                   = module.vpc.vpc_id
  subnet_ids                               = module.vpc.private_subnets
  endpoint_public_access                   = true
  endpoint_private_access                  = false
  enable_cluster_creator_admin_permissions = true
  enable_irsa                              = true

  eks_managed_node_groups = {
    default     = local.eks_default_node_group
    terminology = local.eks_terminology_node_group
  }

  addons = {
    coredns = {
      most_recent = true
    }
    kube-proxy = {
      most_recent = true
    }
    vpc-cni = {
      before_compute              = true
      most_recent                 = true
      resolve_conflicts_on_create = "OVERWRITE"
      resolve_conflicts_on_update = "OVERWRITE"
    }
  }

  tags = {
    Environment = var.environment
  }
}

module "ebs_csi_irsa" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts"
  version = "~> 6.0"

  name            = "${var.cluster_name}-ebs-csi"
  use_name_prefix = false

  attach_ebs_csi_policy = true

  oidc_providers = {
    eks = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["kube-system:ebs-csi-controller-sa"]
    }
  }
}

resource "aws_eks_addon" "ebs_csi" {
  cluster_name                = module.eks.cluster_name
  addon_name                  = "aws-ebs-csi-driver"
  service_account_role_arn    = module.ebs_csi_irsa.arn
  resolve_conflicts_on_create = "OVERWRITE"
  resolve_conflicts_on_update = "OVERWRITE"

  depends_on = [module.eks]
}

resource "kubernetes_storage_class_v1" "gp3" {
  metadata {
    name = "gp3"
    annotations = {
      "storageclass.kubernetes.io/is-default-class" = "true"
    }
  }

  storage_provisioner   = "ebs.csi.aws.com"
  reclaim_policy        = "Delete"
  volume_binding_mode   = "WaitForFirstConsumer"
  allow_volume_expansion = true

  parameters = {
    type = "gp3"
  }

  depends_on = [aws_eks_addon.ebs_csi]
}
