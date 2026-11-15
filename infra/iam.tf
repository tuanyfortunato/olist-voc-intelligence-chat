# Dois papéis: o de execução, que o ECS usa para baixar a imagem e ler os
# segredos, e o da tarefa, que o código da API e da carga usa.

data "aws_iam_policy_document" "ecs_tasks_trust" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }
}

resource "aws_iam_role" "execution" {
  name               = "olist-voc-ecs-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_trust.json
}

resource "aws_iam_role_policy_attachment" "execution" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

data "aws_iam_policy_document" "execution_secrets" {
  statement {
    actions   = ["ssm:GetParameters"]
    resources = [aws_ssm_parameter.access_key.arn, aws_ssm_parameter.db_password.arn]
  }
}

resource "aws_iam_role_policy" "execution_secrets" {
  name   = "olist-voc-read-secrets"
  role   = aws_iam_role.execution.id
  policy = data.aws_iam_policy_document.execution_secrets.json
}

resource "aws_iam_role" "task" {
  name               = "olist-voc-ecs-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_trust.json
}

data "aws_iam_policy_document" "task" {
  statement {
    sid     = "ModelosDoBedrock"
    actions = ["bedrock:InvokeModel"]
    resources = [
      "arn:aws:bedrock:${var.aws_region}::foundation-model/cohere.embed-multilingual-v3",
      "arn:aws:bedrock:${var.aws_region}::foundation-model/amazon.nova-micro-v1:0",
    ]
  }

  statement {
    sid       = "LerOsEmbeddings"
    actions   = ["s3:GetObject"]
    resources = ["arn:aws:s3:::${var.index_bucket}/index/current/*"]
  }
}

resource "aws_iam_role_policy" "task" {
  name   = "olist-voc-task"
  role   = aws_iam_role.task.id
  policy = data.aws_iam_policy_document.task.json
}
