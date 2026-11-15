# Recursos que precisam existir antes de qualquer workflow:
# o bucket do estado do Terraform, o bucket do índice e o acesso OIDC do GitHub.
# Roda pelo terminal uma única vez; o restante da infraestrutura fica em infra/.

terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
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
