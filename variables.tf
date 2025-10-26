variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "cluster_name" {
  description = "EKS cluster name"
  type        = string
  default     = "hapi-eks-cluster"
}

variable "k8s_version" {
  description = "Kubernetes version"
  type        = string
  default     = "1.33"
}

variable "node_instance_type" {
  description = "EC2 instance type for worker nodes"
  type        = string
  default     = "t3.medium"
}

variable "node_ami_type" {
  description = "Override the managed node group AMI type when you need a specific Amazon EKS optimized image family"
  type        = string
  default     = ""

  validation {
    condition = var.node_ami_type == "" || contains([
      "AL2_x86_64",
      "AL2_x86_64_GPU",
      "AL2_ARM_64",
      "AL2_ARM_64_GPU",
      "BOTTLEROCKET_x86_64",
      "BOTTLEROCKET_x86_64_NVIDIA",
      "BOTTLEROCKET_ARM_64",
      "BOTTLEROCKET_ARM_64_NVIDIA",
      "AL2023_x86_64_STANDARD",
      "AL2023_x86_64_GPU",
      "AL2023_ARM_64_STANDARD"
    ], var.node_ami_type)
    error_message = "Valid values for node_ami_type are empty string (automatic) or one of the Amazon-provided EKS managed node group AMI identifiers."
  }
}

variable "node_desired_capacity" {
  type    = number
  default = 2
}

variable "node_min_capacity" {
  type    = number
  default = 1
}

variable "node_max_capacity" {
  type    = number
  default = 3
}

variable "ssh_key_name" {
  description = "Optional SSH key for node access (leave empty to not set)"
  type        = string
  default     = ""
}

variable "environment" {
  type    = string
  default = "dev"
}

variable "hapi_chart_version" {
  description = "Helm chart version for hapi-fhir-jpaserver from the official hapifhir repo"
  type        = string
  default     = "0.21.0"
}

variable "hapi_mode" {
  description = "HAPI FHIR configuration mode: 'general', 'terminology', or 'both'"
  type        = string
  default     = "general"

  validation {
    condition     = contains(["general", "terminology", "both"], var.hapi_mode)
    error_message = "Valid values for hapi_mode are: general, terminology, both."
  }
}
