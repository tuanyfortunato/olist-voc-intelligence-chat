# Infraestrutura

Toda a infraestrutura do projeto é descrita em Terraform, na pasta `infra/`, e fica na região `us-east-1`. Todos os recursos recebem a etiqueta `Project = olist-voc-intelligence-chat`, o que facilita conferir custos e encontrar sobras na remoção.

## Bootstrap

A pasta `infra/bootstrap/` cria o que precisa existir antes de qualquer workflow: o bucket que guarda o estado do Terraform, o bucket do índice do Chroma e o acesso do GitHub Actions à AWS por OIDC. É a única parte que roda pelo terminal, porque é ela que cria o acesso usado pelos workflows depois.

Com o OIDC, o GitHub não guarda nenhuma chave da AWS. A cada execução ele emite um token que identifica o repositório e a branch, e a AWS troca esse token por uma credencial temporária do papel `olist-voc-github-actions`. O papel só aceita este repositório, nas branches `main`, `develop` e `feature/*` e em PRs. Pull requests vindos de forks não recebem esse token. As permissões são as da política `PowerUserAccess`, que cobre os serviços do projeto mas não o IAM, e uma política própria que libera o IAM apenas para papéis e políticas com o prefixo `olist-voc-`.

Na primeira execução o bucket do estado ainda não existe, então o estado começa local e é levado para o S3 logo depois. Os comandos, a partir da raiz do repositório e com credenciais de administrador da conta, são estes:

```bash
cd infra/bootstrap
mv backend.tf backend.tf.off
terraform init
terraform apply
mv backend.tf.off backend.tf
terraform init -migrate-state -backend-config="bucket=$(terraform output -raw state_bucket)"
rm -f terraform.tfstate terraform.tfstate.backup
```

Depois, os valores gerados são cadastrados no repositório do GitHub: o segredo `AWS_ROLE_ARN` com o output `github_role_arn`, o segredo `KAGGLE_ACCESS_TOKEN` com o token do Kaggle e as variáveis `TF_STATE_BUCKET` e `INDEX_BUCKET` com os nomes dos buckets.
