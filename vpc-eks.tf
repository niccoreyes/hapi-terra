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
  eks_node_group = merge(
    {
      desired_size   = var.node_desired_capacity
      max_size       = var.node_max_capacity
      min_size       = var.node_min_capacity
      instance_types = [var.node_instance_type]
      capacity_type  = "ON_DEMAND"
      ami_type       = "AL2_x86_64"
    },
    var.ssh_key_name != "" ? {
      remote_access = {
        ec2_ssh_key = var.ssh_key_name
      }
    } : {}
  )
}

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 21.0"

  name               = var.cluster_name
  kubernetes_version = var.k8s_version
  vpc_id                          = module.vpc.vpc_id
  subnet_ids                      = module.vpc.private_subnets
  enable_cluster_creator_admin_permissions = true

  eks_managed_node_groups = {
    default = local.eks_node_group
  }

  tags = {
    Environment = var.environment
  }
}
