resource "aws_ecr_repository" "api" {
  name                 = "olist-voc-api"
  image_tag_mutability = "MUTABLE"
  force_delete         = true
}

# Guarda só as cinco imagens mais recentes
resource "aws_ecr_lifecycle_policy" "api" {
  repository = aws_ecr_repository.api.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Mantém as cinco imagens mais recentes"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 5
      }
      action = { type = "expire" }
    }]
  })
}
