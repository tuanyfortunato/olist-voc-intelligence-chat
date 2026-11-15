variable "aws_region" {
  description = "Região de todos os recursos do projeto"
  type        = string
  default     = "us-east-1"
}

variable "project" {
  description = "Nome do projeto, usado na etiqueta Project de todos os recursos"
  type        = string
  default     = "olist-voc-intelligence-chat"
}

variable "index_bucket" {
  description = "Bucket criado pelo bootstrap, com os embeddings em index/current/"
  type        = string
}

variable "task_cpu" {
  description = "CPU da tarefa da API, em unidades do ECS (512 = 0,5 vCPU)"
  type        = number
  default     = 512
}

variable "task_memory" {
  description = "Memória da tarefa da API, em MB"
  type        = number
  default     = 1024
}

variable "use_fargate_spot" {
  description = "Usa Fargate Spot, mais barato, mas sujeito a interrupção e a falta de capacidade"
  type        = bool
  default     = false
}

variable "log_retention_days" {
  description = "Dias de retenção dos logs da API no CloudWatch"
  type        = number
  default     = 7
}

variable "db_instance_class" {
  description = "Classe da instância do PostgreSQL"
  type        = string
  # Na db.t4g.micro (1 GB) o índice HNSW não cabe na memória e é construído em
  # disco, em uns 17 minutos. Como a carga só roda quando os embeddings mudam,
  # a micro basta. Se a busca ficar lenta, db.t4g.small tem 2 GB.
  default = "db.t4g.micro"
}

variable "db_allocated_storage" {
  description = "Disco do PostgreSQL, em GB"
  type        = number
  default     = 20
}
