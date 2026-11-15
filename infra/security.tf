# Quem pode falar com quem: o CloudFront com o ALB, o ALB com a API e a API
# (e a tarefa de carga, que usa o mesmo grupo) com o banco.
# A AWS só aceita caracteres ASCII nas descrições dos grupos de segurança,
# por isso elas estão sem acento.

data "aws_ec2_managed_prefix_list" "cloudfront" {
  name = "com.amazonaws.global.cloudfront.origin-facing"
}

resource "aws_security_group" "alb" {
  name        = "olist-voc-alb"
  description = "ALB - aceita apenas o CloudFront"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "HTTP vindo do CloudFront"
    from_port       = 80
    to_port         = 80
    protocol        = "tcp"
    prefix_list_ids = [data.aws_ec2_managed_prefix_list.cloudfront.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "task" {
  name        = "olist-voc-task"
  description = "Tarefas do ECS - aceitam apenas o ALB"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "API vinda do ALB"
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  # Saída para o Bedrock, o S3, o ECR e o banco
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "db" {
  name        = "olist-voc-db"
  description = "PostgreSQL - aceita apenas as tarefas do ECS"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "PostgreSQL vindo das tarefas"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.task.id]
  }
}
