# Estado guardado no próprio bucket criado por este bootstrap.
# O nome do bucket é informado no init:
#   terraform init -backend-config="bucket=<state_bucket>"
#
# Na primeira execução o bucket ainda não existe. Por isso este arquivo é
# renomeado para backend.tf.off antes do primeiro apply e volta depois,
# com terraform init -migrate-state (passo a passo em docs/05-infraestrutura.md).
terraform {
  backend "s3" {
    key          = "bootstrap/terraform.tfstate"
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true
  }
}
