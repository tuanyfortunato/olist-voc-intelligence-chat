output "state_bucket" {
  description = "Bucket do estado do Terraform (variável TF_STATE_BUCKET no GitHub)"
  value       = aws_s3_bucket.state.bucket
}

output "index_bucket" {
  description = "Bucket dos embeddings (variável INDEX_BUCKET no GitHub)"
  value       = aws_s3_bucket.index.bucket
}

output "github_role_arn" {
  description = "Papel assumido pelos workflows (segredo AWS_ROLE_ARN no GitHub)"
  value       = aws_iam_role.github_actions.arn
}
