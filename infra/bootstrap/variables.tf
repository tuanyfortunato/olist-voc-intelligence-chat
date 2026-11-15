variable "aws_region" {
  description = "Região de todos os recursos do projeto"
  type        = string
  default     = "us-east-1"
}

variable "project" {
  description = "Nome do projeto, usado na etiqueta Project de todos os recursos"
  type        = string
  default     = "olist-voc-intelligence-chat"
}

variable "github_repository" {
  description = "Repositório autorizado a entrar na AWS pelo OIDC, no formato dono/nome"
  type        = string
  default     = "tuanyfortunato/olist-voc-intelligence-chat"
}
