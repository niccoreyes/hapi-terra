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

  eks_node_group = {
    desired_size               = var.node_desired_capacity
    max_size                   = var.node_max_capacity
    min_size                   = var.node_min_capacity
    instance_types             = [var.node_instance_type]
    capacity_type              = "ON_DEMAND"
    ami_type                   = local.eks_node_ami_type
    create_launch_template     = local.eks_remote_access == null
    use_custom_launch_template = local.eks_remote_access == null
    remote_access              = local.eks_remote_access
  }
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

  eks_managed_node_groups = {
    default = local.eks_node_group
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
