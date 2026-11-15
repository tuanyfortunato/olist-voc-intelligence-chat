# Lidos pelos workflows de publicação e de carga

output "ecr_repository_url" {
  value = aws_ecr_repository.api.repository_url
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.main.name
}

output "ecs_service_name" {
  value = aws_ecs_service.api.name
}

output "task_family" {
  value = aws_ecs_task_definition.api.family
}

output "task_security_group_id" {
  value = aws_security_group.task.id
}

output "public_subnet_ids" {
  value = aws_subnet.public[*].id
}

output "frontend_bucket" {
  value = aws_s3_bucket.frontend.bucket
}

output "cloudfront_distribution_id" {
  value = aws_cloudfront_distribution.main.id
}

output "cloudfront_url" {
  value = "https://${aws_cloudfront_distribution.main.domain_name}"
}

output "access_key_parameter" {
  value = aws_ssm_parameter.access_key.name
}

output "db_endpoint" {
  value = aws_db_instance.main.address
}
