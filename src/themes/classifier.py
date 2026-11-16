"""Classificação das avaliações nos temas do painel, em lote, com o Nova Micro.

Cada chamada leva um lote de comentários numerados e pede de volta um JSON com
os temas de cada número. A classificação roda uma vez, fora da API, e o
resultado fica no banco. Quem abre o painel não gera nenhuma chamada ao modelo.

Lotes de 20 comentários deixam o prompt dos temas, que é a maior parte do
texto de entrada, dividido por muitos comentários. Um lote com resposta
inválida é tentado de novo; o que continua sem resposta fica sem classificação
e é tentado na próxima execução, que só pega o que ainda falta.
"""

import json
import logging
import re
from collections.abc import Callable, Iterator, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from src.themes.taxonomy import MAX_THEMES_PER_REVIEW, THEME_IDS, THEMES

logger = logging.getLogger(__name__)

BATCH_SIZE = 20
ATTEMPTS = 2
# Comentários muito longos são raros; o corte limita o custo de um lote
MAX_TEXT_CHARS = 600
MAX_OUTPUT_TOKENS = 700


def _theme_lines() -> str:
    return "\n".join(f"- {theme.id}: {theme.description}" for theme in THEMES)


SYSTEM_PROMPT = f"""Você classifica comentários de clientes de uma loja online brasileira.

Para cada comentário, escolha de 0 a {MAX_THEMES_PER_REVIEW} temas desta lista, \
usando só os identificadores:
{_theme_lines()}

Regras:
- Marque um tema só quando o comentário fala dele de forma explícita.
- Um comentário pode ter reclamação e elogio ao mesmo tempo.
- Comentários genéricos, como "ok", "recomendo" ou "gostei", sem dizer o motivo, \
ficam sem tema.
- Responda só com um objeto JSON, sem texto antes ou depois, com o número de cada \
comentário como chave e a lista de temas como valor. Exemplo: \
{{"1": ["atraso", "sem_resposta"], "2": [], "3": ["entrega_rapida"]}}"""


@dataclass(frozen=True)
class ReviewText:
    review_id: str
    text: str


@dataclass
class ClassificationStats:
    batches: int = 0
    failed_batches: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    classified: int = 0
    unclassified: list[str] = field(default_factory=list)


def build_batch_message(reviews: Sequence[ReviewText]) -> str:
    lines = [
        f"[{number}] {review.text[:MAX_TEXT_CHARS]}" for number, review in enumerate(reviews, 1)
    ]
    return "Comentários:\n" + "\n".join(lines)


def clean_themes(values: object) -> list[str]:
    """Só os temas da lista, sem repetir, na ordem dada, até o máximo por avaliação."""
    if not isinstance(values, list):
        return []
    themes: list[str] = []
    for value in values:
        if isinstance(value, str) and value in THEME_IDS and value not in themes:
            themes.append(value)
    return themes[:MAX_THEMES_PER_REVIEW]


def parse_batch(raw: str, size: int) -> dict[int, list[str]]:
    """Temas de cada número do lote. Números que faltam na resposta ficam de fora;
    texto que não é JSON devolve um dicionário vazio."""
    match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if not match:
        return {}
    try:
        data = json.loads(match.group(0))
    except ValueError:
        return {}
    if not isinstance(data, dict):
        return {}
    result = {}
    for key, values in data.items():
        try:
            number = int(str(key).strip("[] "))
        except ValueError:
            continue
        if 1 <= number <= size:
            result[number] = clean_themes(values)
    return result


def converse(client, model_id: str, message: str) -> tuple[str, int, int]:
    """Uma chamada ao modelo. Devolve o texto e os tokens de entrada e de saída."""
    response = client.converse(
        modelId=model_id,
        system=[{"text": SYSTEM_PROMPT}],
        messages=[{"role": "user", "content": [{"text": message}]}],
        inferenceConfig={"temperature": 0, "maxTokens": MAX_OUTPUT_TOKENS},
    )
    text = response["output"]["message"]["content"][0]["text"]
    usage = response.get("usage", {})
    return text, usage.get("inputTokens", 0), usage.get("outputTokens", 0)


Caller = Callable[[str], tuple[str, int, int]]


@dataclass(frozen=True)
class BatchResult:
    themes: dict[str, list[str]]
    input_tokens: int
    output_tokens: int
    complete: bool


def classify_batch(reviews: Sequence[ReviewText], call: Caller) -> BatchResult:
    """Temas de cada review_id do lote. Os que o modelo não devolveu ficam de fora."""
    message = build_batch_message(reviews)
    found: dict[int, list[str]] = {}
    tokens_in = tokens_out = 0
    for attempt in range(1, ATTEMPTS + 1):
        try:
            raw, used_in, used_out = call(message)
        except Exception:
            logger.warning("etapa=temas tentativa=%d erro=chamada", attempt, exc_info=True)
            continue
        tokens_in += used_in
        tokens_out += used_out
        found.update(parse_batch(raw, len(reviews)))
        if len(found) == len(reviews):
            break
        logger.warning(
            "etapa=temas tentativa=%d erro=resposta_incompleta recebidos=%d de=%d",
            attempt,
            len(found),
            len(reviews),
        )
    themes = {reviews[number - 1].review_id: values for number, values in found.items()}
    return BatchResult(themes, tokens_in, tokens_out, complete=len(found) == len(reviews))


def batches(items: Sequence[ReviewText], size: int = BATCH_SIZE) -> Iterator[Sequence[ReviewText]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def classify_reviews(
    reviews: Sequence[ReviewText],
    call: Caller,
    workers: int = 4,
    on_batch: Callable[[dict[str, list[str]]], None] | None = None,
) -> tuple[dict[str, list[str]], ClassificationStats]:
    """Classifica todos os comentários, com alguns lotes em paralelo.

    on_batch recebe o resultado de cada lote assim que ele termina, para a
    gravação no banco não esperar o fim de tudo.
    """
    stats = ClassificationStats()
    result: dict[str, list[str]] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for done, batch in enumerate(
            pool.map(lambda items: classify_batch(items, call), batches(reviews)), 1
        ):
            stats.batches += 1
            stats.failed_batches += not batch.complete
            stats.input_tokens += batch.input_tokens
            stats.output_tokens += batch.output_tokens
            result.update(batch.themes)
            if on_batch and batch.themes:
                on_batch(batch.themes)
            if done % 100 == 0:
                logger.info("etapa=temas lotes=%d classificadas=%d", done, len(result))
    stats.classified = len(result)
    stats.unclassified = [review.review_id for review in reviews if review.review_id not in result]
    return result, stats
