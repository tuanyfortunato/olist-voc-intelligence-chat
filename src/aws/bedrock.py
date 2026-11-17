"""Conexão com o Amazon Bedrock: embeddings do Cohere e chat com o Nova ou o Claude."""

import json
from typing import Literal

import boto3
from botocore.config import Config
from langchain_aws import ChatBedrockConverse

from src.config import Settings

# Limite do Cohere Embed Multilingual v3 por chamada
MAX_TEXTS_PER_CALL = 96

InputType = Literal["search_document", "search_query"]


def get_runtime_client(settings: Settings):
    """Cliente do Bedrock. As novas tentativas longas ficam por conta da indexação."""
    config = Config(retries={"mode": "standard", "max_attempts": 3}, read_timeout=60)
    return boto3.client("bedrock-runtime", region_name=settings.aws_region, config=config)


def embed_texts(
    client, texts: list[str], input_type: InputType, settings: Settings
) -> list[list[float]]:
    """Gera os vetores de até 96 textos em uma única chamada.

    O Cohere trata de forma diferente o texto que vai para o índice
    (search_document) e o texto da pergunta (search_query).
    """
    if not texts or len(texts) > MAX_TEXTS_PER_CALL:
        raise ValueError(f"Cada chamada aceita de 1 a {MAX_TEXTS_PER_CALL} textos.")
    body = json.dumps({"texts": texts, "input_type": input_type, "truncate": "END"})
    response = client.invoke_model(modelId=settings.embedding_model_id, body=body)
    return json.loads(response["body"].read())["embeddings"]


def embed_query(client, text: str, settings: Settings) -> list[float]:
    return embed_texts(client, [text], "search_query", settings)[0]


def get_chat_model(
    settings: Settings, max_tokens: int, model_id: str | None = None
) -> ChatBedrockConverse:
    """Modelo de chat do Bedrock.

    O Nova roda com temperatura 0, para a avaliação dar o mesmo resultado a cada
    execução. O Claude Haiku 5.5 não aceita mudar a temperatura e pensa antes de
    responder por padrão; aqui o raciocínio fica desligado, para a resposta vir
    só com o texto e mais rápido.
    """
    model = model_id or settings.llm_model_id
    if is_claude(model):
        return ChatBedrockConverse(
            model=model,
            region_name=settings.aws_region,
            max_tokens=max_tokens,
            additional_model_request_fields={"thinking": {"type": "disabled"}},
        )
    return ChatBedrockConverse(
        model=model,
        region_name=settings.aws_region,
        temperature=0,
        max_tokens=max_tokens,
    )


def is_claude(model_id: str) -> bool:
    """anthropic.claude-... ou o perfil entre regiões, como us.anthropic.claude-..."""
    return "anthropic.claude" in model_id
