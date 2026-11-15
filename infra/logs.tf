resource "aws_cloudwatch_log_group" "api" {
  name              = "/ecs/olist-voc-api"
  retention_in_days = var.log_retention_days
}
