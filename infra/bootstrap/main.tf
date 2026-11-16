data "aws_caller_identity" "current" {}

locals {
  account_id   = data.aws_caller_identity.current.account_id
  state_bucket = "olist-voc-tfstate-${local.account_id}"
  index_bucket = "olist-voc-index-${local.account_id}"
}

# Estado do Terraform. O versionamento permite recuperar um estado anterior
# se uma execução corromper o arquivo.
resource "aws_s3_bucket" "state" {
  bucket        = local.state_bucket
  force_destroy = true
}

resource "aws_s3_bucket_versioning" "state" {
  bucket = aws_s3_bucket.state.id

  versioning_configuration {
    status = "Enabled"
  }
}

# Embeddings gerados pelo workflow de indexação e lidos pela carga dos vetores no PostgreSQL.
resource "aws_s3_bucket" "index" {
  bucket        = local.index_bucket
  force_destroy = true
}

resource "aws_s3_bucket_versioning" "index" {
  bucket = aws_s3_bucket.index.id

  versioning_configuration {
    status = "Enabled"
  }
}

# Criptografia e bloqueio de acesso público nos dois buckets
resource "aws_s3_bucket_server_side_encryption_configuration" "buckets" {
  for_each = {
    state = aws_s3_bucket.state.id
    index = aws_s3_bucket.index.id
  }

  bucket = each.value

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "buckets" {
  for_each = {
    state = aws_s3_bucket.state.id
    index = aws_s3_bucket.index.id
  }

  bucket                  = each.value
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
