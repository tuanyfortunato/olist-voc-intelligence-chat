#!/usr/bin/env bash
# Roda um comando numa tarefa avulsa do ECS, com uma imagem dada, dentro da rede
# do banco. Usado pelos workflows de calibração e de avaliação, que precisam do
# PostgreSQL, que o GitHub Actions não alcança.
#
# Uso: scripts/run_ecs_task.sh <imagem> <comando> [argumentos...]
# Precisa de: ECS_CLUSTER_NAME, TASK_FAMILY, SUBNETS, TASK_SECURITY_GROUP_ID.
set -euo pipefail

IMAGE="$1"
shift
COMMAND=$(printf '%s\n' "$@" | jq -R . | jq -sc .)

# Revisão da tarefa só para esta execução, com a imagem da branch. O serviço da
# API continua usando a revisão dele.
aws ecs describe-task-definition --task-definition "$TASK_FAMILY" --query taskDefinition > task.json
jq --arg image "$IMAGE" \
  '.containerDefinitions[0].image = $image
   | del(.taskDefinitionArn, .revision, .status, .requiresAttributes, .compatibilities, .registeredAt, .registeredBy)' \
  task.json > new-task.json
TASK_DEF=$(aws ecs register-task-definition --cli-input-json file://new-task.json \
  --query taskDefinition.taskDefinitionArn --output text)

TASK_ARN=$(aws ecs run-task \
  --cluster "$ECS_CLUSTER_NAME" \
  --task-definition "$TASK_DEF" \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[$SUBNETS],securityGroups=[$TASK_SECURITY_GROUP_ID],assignPublicIp=ENABLED}" \
  --overrides "{\"containerOverrides\":[{\"name\":\"api\",\"command\":$COMMAND}]}" \
  --query 'tasks[0].taskArn' --output text)
echo "Tarefa: $TASK_ARN"

STATUS=""
for _ in $(seq 1 120); do
  STATUS=$(aws ecs describe-tasks --cluster "$ECS_CLUSTER_NAME" --tasks "$TASK_ARN" \
    --query 'tasks[0].lastStatus' --output text)
  [ "$STATUS" = "STOPPED" ] && break
  sleep 30
done

TASK_ID="${TASK_ARN##*/}"
aws logs get-log-events --log-group-name /ecs/olist-voc-api --log-stream-name "api/api/$TASK_ID" \
  --query 'events[].message' --output text | tr '\t' '\n' | tail -40 || true

[ "$STATUS" = "STOPPED" ] || { echo "A tarefa não terminou em 60 minutos."; exit 1; }
EXIT_CODE=$(aws ecs describe-tasks --cluster "$ECS_CLUSTER_NAME" --tasks "$TASK_ARN" \
  --query 'tasks[0].containers[0].exitCode' --output text)
echo "Código de saída: $EXIT_CODE"
[ "$EXIT_CODE" = "0" ]
