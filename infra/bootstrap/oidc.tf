# Acesso do GitHub Actions à AWS sem chave guardada: a cada execução o GitHub
# emite um token que identifica o repositório e a branch, e a AWS troca esse
# token por uma credencial temporária do papel abaixo.

resource "aws_iam_openid_connect_provider" "github" {
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
}

data "aws_iam_policy_document" "github_trust" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    # Só este repositório, nas branches do projeto e em PRs. PRs de forks não
    # recebem token do GitHub, e o workflow do Terraform ainda confere a origem.
    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values = [
        "repo:${var.github_repository}:ref:refs/heads/main",
        "repo:${var.github_repository}:ref:refs/heads/develop",
        "repo:${var.github_repository}:ref:refs/heads/feature/*",
        "repo:${var.github_repository}:pull_request",
      ]
    }
  }
}

resource "aws_iam_role" "github_actions" {
  name               = "olist-voc-github-actions"
  assume_role_policy = data.aws_iam_policy_document.github_trust.json
}

# PowerUserAccess cobre os serviços do projeto (S3, ECR, ECS, ALB, CloudFront,
# Bedrock, SSM e CloudWatch), mas não o IAM.
resource "aws_iam_role_policy_attachment" "power_user" {
  role       = aws_iam_role.github_actions.name
  policy_arn = "arn:aws:iam::aws:policy/PowerUserAccess"
}

# O Terraform da aplicação cria os papéis do ECS. Esta permissão de IAM vale
# só para papéis e políticas com o prefixo do projeto.
data "aws_iam_policy_document" "project_iam" {
  statement {
    actions = ["iam:*"]
    resources = [
      "arn:aws:iam::${local.account_id}:role/olist-voc-*",
      "arn:aws:iam::${local.account_id}:policy/olist-voc-*",
      aws_iam_openid_connect_provider.github.arn,
    ]
  }

  statement {
    actions   = ["iam:PassRole"]
    resources = ["arn:aws:iam::${local.account_id}:role/olist-voc-*"]
  }

  # Papel que o ECS cria sozinho na primeira vez que a conta usa o serviço
  statement {
    actions   = ["iam:CreateServiceLinkedRole"]
    resources = ["arn:aws:iam::${local.account_id}:role/aws-service-role/*"]
  }
}

resource "aws_iam_role_policy" "project_iam" {
  name   = "olist-voc-project-iam"
  role   = aws_iam_role.github_actions.id
  policy = data.aws_iam_policy_document.project_iam.json
}
