# Segredos gerados pelo Terraform e guardados no Parameter Store.
# O ECS injeta os dois na tarefa como variáveis de ambiente.

# Curta e só com minúsculas e números, para ser fácil de digitar na página.
# A cota diária limita o estrago se alguém a adivinhar.
resource "random_password" "access_key" {
  length  = 8
  special = false
  upper   = false
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
