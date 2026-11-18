"""Classificação e reescrita da pergunta (camada 1 de proteção).

Uma única chamada ao Nova Micro, com saída estruturada, classifica a pergunta
(no escopo, saudação ou fora do escopo) e devolve o tema da busca e a pergunta
limpa, sem números nem premissas do gestor. Se o modelo falhar duas vezes, a
pergunta segue como está, tratada como no escopo, e as camadas seguintes (score
mínimo e instrução no prompt da resposta) continuam valendo.
"""

import json
import logging
import re
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ValidationError, field_validator

from src.rag.prompts import ANALYSIS_PROMPT, FILTERS_INTRO, HISTORY_INTRO
from src.rag.schemas import ConversationTurn, SearchFilters

logger = logging.getLogger(__name__)

ATTEMPTS = 2

# Palavras que descrevem o tipo de análise pedida, e não o que o cliente escreve.
# O prompt pede ao modelo que as tire do tema da busca, mas o Nova Micro nem
# sempre obedece, e elas afastam a busca dos comentários.
ANALYSIS_WORDS = [
    r"\bpadr(?:ão|ões)\b",
    r"\brecorrentes?\b",
    r"\bfrequentes?\b",
    r"\bprincipais\b",
    r"\b(?:determinadas\s+)?categorias\s+de\s+produtos\b",
    r"\b(?:nas|das|em)\s+avaliações(?:\s+(?:de|dos|das))?\b",
]
EDGE_WORDS = {"a", "o", "ao", "e", "de", "da", "do", "das", "dos", "em", "na", "no", "nas", "nos"}

# A nota só vira filtro quando a própria pergunta fala dela. Sem isto, o modelo
# chegou a marcar notas 1 e 2 em perguntas que só falavam de reclamações.
RATING_CUE = re.compile(
    r"\b(?:notas?|estrelas?|insatisfeit\w*|satisfeit\w*|negativ\w*|positiv\w*)\b",
    re.IGNORECASE,
)


# Pedido para ver as avaliações, sem assunto próprio, como "Me mostre as avaliações"
# ou "Quais avaliações temos desse tipo?". Com uma categoria marcada na tela, o Nova
# Micro chegou a classificar esses pedidos como fora do escopo. Só vale quando a
# frase não tem nenhuma outra palavra: "Quais avaliações falam do clima?" continua
# com a classificação do modelo.
LIST_NOUNS = re.compile(r"^(?:avalia\w*|coment\w*|reviews?|opini\w+)$", re.IGNORECASE)
LIST_FILLER = {
    "me",
    "mostre",
    "mostra",
    "mostrar",
    "liste",
    "lista",
    "listar",
    "exiba",
    "exibir",
    "ver",
    "veja",
    "quero",
    "gostaria",
    "de",
    "traga",
    "trazer",
    "quais",
    "que",
    "as",
    "os",
    "a",
    "o",
    "temos",
    "tem",
    "têm",
    "existem",
    "há",
    "desse",
    "deste",
    "dessa",
    "desta",
    "tipo",
    "essas",
    "estas",
    "esses",
    "estes",
    "dessas",
    "destas",
    "todas",
    "todos",
    "algumas",
    "alguns",
    "por",
    "favor",
    "pode",
    "poderia",
    "você",
    "e",
    "sobre",
    "isso",
    "aqui",
    "dos",
    "das",
    "clientes",
    "deles",
}
LIST_TOPIC = "opinião dos clientes sobre a compra e o produto"
LIST_QUESTION = "O que os clientes relatam nessas avaliações?"

DELIVERY_NAMES = {
    "no_prazo": "entregue no prazo",
    "atrasada": "entregue com atraso",
    "nao_entregue": "não entregue",
}


class QuestionAnalysis(BaseModel):
    kind: Literal["in_scope", "greeting", "out_of_scope"]
    search_topic: str
    clean_question: str
    # Verdadeiro quando a pergunta afirmava como fato algo que foi retirado,
    # como "Já que 90% dos clientes reclamam de atraso"
    removed_premise: bool = False
    # Notas que a pergunta menciona, como "notas altas" (4 e 5); viram filtro
    ratings: list[int] = []

    @field_validator("ratings")
    @classmethod
    def keep_valid_ratings(cls, value: list[int]) -> list[int]:
        return sorted({rating for rating in value if 1 <= rating <= 5})


@dataclass(frozen=True)
class AnalysisResult:
    analysis: QuestionAnalysis
    fallback_used: bool


def validate_analysis(raw: object) -> QuestionAnalysis | None:
    """Aceita a resposta do modelo como objeto, dicionário ou texto JSON. Devolve None
    se o formato for inválido ou se faltar o tema da busca numa pergunta no escopo."""
    try:
        if isinstance(raw, QuestionAnalysis):
            analysis = raw
        elif isinstance(raw, str):
            analysis = QuestionAnalysis.model_validate(json.loads(raw))
        elif isinstance(raw, dict):
            analysis = QuestionAnalysis.model_validate(raw)
        else:
            return None
    except (ValueError, ValidationError):
        return None
    if analysis.kind == "in_scope" and not (
        analysis.search_topic.strip() and analysis.clean_question.strip()
    ):
        return None
    return analysis


def clean_search_topic(topic: str) -> str:
    """Tira do tema da busca as palavras de análise. Se não sobrar nada, fica o original."""
    cleaned = topic
    for pattern in ANALYSIS_WORDS:
        cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)
    words = cleaned.split()
    while words and words[0].lower() in EDGE_WORDS:
        words.pop(0)
    while words and words[-1].lower() in EDGE_WORDS:
        words.pop()
    return " ".join(words) or topic.strip()


def tidy_analysis(question: str, analysis: QuestionAnalysis) -> QuestionAnalysis:
    """Regras aplicadas em código sobre a análise do modelo."""
    if analysis.kind != "in_scope":
        return analysis
    ratings = analysis.ratings if RATING_CUE.search(question) else []
    return analysis.model_copy(
        update={"search_topic": clean_search_topic(analysis.search_topic), "ratings": ratings}
    )


def describe_filters(filters: SearchFilters | None) -> str:
    """Filtros da tela em texto, para o modelo entender "desse tipo" e "essas avaliações"."""
    if not filters:
        return ""
    parts = []
    if filters.ratings:
        parts.append("notas " + ", ".join(str(r) for r in sorted(filters.ratings)))
    if filters.category:
        parts.append("categoria " + filters.category.replace("_", " "))
    if filters.delivery:
        parts.append("entrega " + DELIVERY_NAMES.get(filters.delivery, filters.delivery))
    if filters.themes:
        parts.append("temas " + ", ".join(t.replace("_", " ") for t in filters.themes))
    return "; ".join(parts)


def is_list_request(question: str) -> bool:
    words = re.findall(r"\w+", question.lower())
    nouns = [word for word in words if LIST_NOUNS.match(word)]
    return bool(nouns) and all(LIST_NOUNS.match(word) or word in LIST_FILLER for word in words)


def list_request_fix(question: str, analysis: QuestionAnalysis) -> QuestionAnalysis:
    """Um pedido para ver as avaliações nunca é fora do escopo: vira uma busca geral
    dentro dos filtros escolhidos."""
    if analysis.kind != "out_of_scope":
        return analysis
    if not is_list_request(question):
        return analysis
    logger.info("etapa=analise ajuste=pedido_de_listagem pergunta=%r", question)
    return QuestionAnalysis(kind="in_scope", search_topic=LIST_TOPIC, clean_question=LIST_QUESTION)


def format_history(history: list[ConversationTurn]) -> str:
    lines = []
    for turn in history:
        lines.append(f"Pergunta anterior: {turn.question}")
        lines.append(f"Resposta anterior: {turn.answer}")
    return "\n".join(lines)


def build_analysis_messages(
    question: str, history: list[ConversationTurn], filters_text: str = ""
) -> list[tuple[str, str]]:
    messages = [("system", ANALYSIS_PROMPT)]
    if history:
        messages.append(("human", f"{HISTORY_INTRO}\n{format_history(history)}"))
    if filters_text:
        messages.append(("human", f"{FILTERS_INTRO}\n{filters_text}"))
    messages.append(("human", f"Mensagem do gestor a classificar:\n{question}"))
    return messages


def analyze_question(
    question: str,
    history: list[ConversationTurn],
    llm,
    filters: SearchFilters | None = None,
) -> AnalysisResult:
    structured = llm.with_structured_output(QuestionAnalysis)
    messages = build_analysis_messages(question, history, describe_filters(filters))
    for attempt in range(1, ATTEMPTS + 1):
        try:
            analysis = validate_analysis(structured.invoke(messages))
        except Exception:
            logger.warning("etapa=analise tentativa=%d erro=chamada", attempt, exc_info=True)
            analysis = None
        if analysis is not None:
            analysis = tidy_analysis(question, list_request_fix(question, analysis))
            logger.info(
                "etapa=analise tipo=%s tema=%r pergunta=%r",
                analysis.kind,
                analysis.search_topic,
                question,
            )
            return AnalysisResult(analysis=analysis, fallback_used=False)
        logger.warning("etapa=analise tentativa=%d erro=formato_invalido", attempt)

    logger.warning("etapa=analise fallback=pergunta_original pergunta=%r", question)
    fallback = QuestionAnalysis(kind="in_scope", search_topic=question, clean_question=question)
    return AnalysisResult(analysis=fallback, fallback_used=True)
