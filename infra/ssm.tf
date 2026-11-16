# Segredos gerados pelo Terraform e guardados no Parameter Store.
# O ECS injeta a senha do banco na tarefa como variável de ambiente.

# Chave de acesso da página, que deixou de ser usada quando o chat ficou
# aberto. A tarefa não a recebe mais, mas o parâmetro fica até a próxima
# publicação: uma tarefa iniciada com a revisão anterior ainda o lê ao subir,
# e sem ele não subiria. Depois do Deploy, este bloco, a permissão em iam.tf
# e o output podem ser apagados.
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
