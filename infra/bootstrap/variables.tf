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
  description = <<-EOT
    Repositório autorizado a entrar na AWS pelo OIDC, no formato que o GitHub
    usa no token: dono@id_do_dono/nome@id_do_repositorio. Os números não mudam
    se o repositório for renomeado e impedem que outro repositório criado com
    o mesmo nome seja aceito.
  EOT
  type        = string
  default     = "tuanyfortunato@41431841/olist-voc-intelligence-chat@1452026236"
}
