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
      # Em teste como modelo da resposta, para citações mais fiéis
      "arn:aws:bedrock:${var.aws_region}::foundation-model/amazon.nova-lite-v1:0",
    ]
  }

  # Claude Haiku 5.5 e 4.5 em teste como modelo da resposta, chamados direto ou
  # pelo perfil entre regiões dos EUA, que pode mandar a chamada a outra região
  statement {
    sid     = "ClaudeHaikuNaResposta"
    actions = ["bedrock:InvokeModel"]
    resources = [
      "arn:aws:bedrock:*::foundation-model/anthropic.claude-haiku-5-5",
      "arn:aws:bedrock:${var.aws_region}:${data.aws_caller_identity.current.account_id}:inference-profile/us.anthropic.claude-haiku-5-5",
      "arn:aws:bedrock:*::foundation-model/anthropic.claude-haiku-4-5-20251001-v1:0",
      "arn:aws:bedrock:${var.aws_region}:${data.aws_caller_identity.current.account_id}:inference-profile/us.anthropic.claude-haiku-4-5-20251001-v1:0",
    ]
  }

  statement {
    sid       = "LerOsEmbeddings"
    actions   = ["s3:GetObject"]
    resources = ["arn:aws:s3:::${var.index_bucket}/index/current/*"]
  }

  # A calibração e a avaliação rodam em tarefas avulsas, dentro da rede do
  # banco, e deixam as tabelas em results/ para o workflow baixar
  statement {
    sid       = "GravarResultados"
    actions   = ["s3:PutObject"]
    resources = ["arn:aws:s3:::${var.index_bucket}/results/*"]
  }
}

resource "aws_iam_role_policy" "task" {
  name   = "olist-voc-task"
  role   = aws_iam_role.task.id
  policy = data.aws_iam_policy_document.task.json
}
