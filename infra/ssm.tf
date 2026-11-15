# Segredos gerados pelo Terraform e guardados no Parameter Store.
# O ECS injeta os dois na tarefa como variáveis de ambiente.

resource "random_password" "access_key" {
  length  = 24
  special = false
}

resource "aws_ssm_parameter" "access_key" {
  name  = "/olist-voc/access-key"
  type  = "SecureString"
  value = random_password.access_key.result
}

resource "random_password" "db" {
  length  = 32
  special = false
}

resource "aws_ssm_parameter" "db_password" {
  name  = "/olist-voc/db-password"
  type  = "SecureString"
  value = random_password.db.result
}
