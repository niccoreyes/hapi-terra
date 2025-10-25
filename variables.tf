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
  default     = "1.28"
}

variable "node_instance_type" {
  description = "EC2 instance type for worker nodes"
  type        = string
  default     = "t3.medium"
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
  description = "Helm chart version for hapi-fhir-jpaserver in the chgl repo"
  type        = string
  default     = "1.0.0"
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
