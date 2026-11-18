# Horário de funcionamento: o banco liga às 8h40 e a API às 9h; a API desliga
# às 22h e o banco às 22h05, no fuso de São Paulo. Fora desse horário, o
# workflow Start API liga os dois.

locals {
  timezone = "America/Sao_Paulo"
}

# API: o Application Auto Scaling troca o número de tarefas do serviço
resource "aws_appautoscaling_target" "api" {
  service_namespace  = "ecs"
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.api.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  min_capacity       = 0
  max_capacity       = 1
}

resource "aws_appautoscaling_scheduled_action" "api_start" {
  name               = "olist-voc-api-start"
  service_namespace  = aws_appautoscaling_target.api.service_namespace
  resource_id        = aws_appautoscaling_target.api.resource_id
  scalable_dimension = aws_appautoscaling_target.api.scalable_dimension
  schedule           = "cron(0 9 * * ? *)"
  timezone           = local.timezone

  scalable_target_action {
    min_capacity = 1
    max_capacity = 1
  }
}

resource "aws_appautoscaling_scheduled_action" "api_stop" {
  name               = "olist-voc-api-stop"
  service_namespace  = aws_appautoscaling_target.api.service_namespace
  resource_id        = aws_appautoscaling_target.api.resource_id
  scalable_dimension = aws_appautoscaling_target.api.scalable_dimension
  schedule           = "cron(0 22 * * ? *)"
  timezone           = local.timezone

  scalable_target_action {
    min_capacity = 0
    max_capacity = 0
  }

  # Duas ações no mesmo alvo não podem ser criadas ao mesmo tempo
  depends_on = [aws_appautoscaling_scheduled_action.api_start]
}

# Banco: o EventBridge Scheduler chama a própria API do RDS
data "aws_iam_policy_document" "scheduler_trust" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["scheduler.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }
}

resource "aws_iam_role" "scheduler" {
  name               = "olist-voc-scheduler"
  assume_role_policy = data.aws_iam_policy_document.scheduler_trust.json
}

data "aws_iam_policy_document" "scheduler" {
  statement {
    actions   = ["rds:StartDBInstance", "rds:StopDBInstance"]
    resources = [aws_db_instance.main.arn]
  }
}

resource "aws_iam_role_policy" "scheduler" {
  name   = "olist-voc-start-stop-db"
  role   = aws_iam_role.scheduler.id
  policy = data.aws_iam_policy_document.scheduler.json
}

resource "aws_scheduler_schedule" "db_start" {
  name                         = "olist-voc-db-start"
  schedule_expression          = "cron(40 8 * * ? *)"
  schedule_expression_timezone = local.timezone

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = "arn:aws:scheduler:::aws-sdk:rds:startDBInstance"
    role_arn = aws_iam_role.scheduler.arn
    input    = jsonencode({ DbInstanceIdentifier = aws_db_instance.main.identifier })
  }
}

resource "aws_scheduler_schedule" "db_stop" {
  name                         = "olist-voc-db-stop"
  schedule_expression          = "cron(5 22 * * ? *)"
  schedule_expression_timezone = local.timezone

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = "arn:aws:scheduler:::aws-sdk:rds:stopDBInstance"
    role_arn = aws_iam_role.scheduler.arn
    input    = jsonencode({ DbInstanceIdentifier = aws_db_instance.main.identifier })
  }
}
