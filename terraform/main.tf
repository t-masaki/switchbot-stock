terraform {
  required_version = ">= 1.5.0, < 2.0.0"
  required_providers {
    aws     = { source = "hashicorp/aws", version = "~> 6.0" }
    archive = { source = "hashicorp/archive", version = "~> 2.7" }
  }
}
provider "aws" { region = var.aws_region }
data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}
locals {
  parameter_arns = [for key in ["token", "secret", "device-id"] : "arn:${data.aws_partition.current.partition}:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter${var.ssm_prefix}/${key}"]
}
