# Infraestrutura da aplicação: rede, banco vetorial, API no ECS, ALB, CloudFront
# e página. Aplicada pelo workflow Terraform a cada merge na main.

terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # O nome do bucket vem no init: -backend-config="bucket=<TF_STATE_BUCKET>"
  backend "s3" {
    key          = "app/terraform.tfstate"
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project = var.project
    }
  }
}

data "aws_caller_identity" "current" {}
