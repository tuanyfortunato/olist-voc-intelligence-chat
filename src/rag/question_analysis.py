"""Classificação e reescrita da pergunta (camada 1 de proteção).

Uma única chamada ao Nova Micro, com saída estruturada, classifica a pergunta
(no escopo, saudação ou fora do escopo) e devolve o tema da busca e a pergunta
limpa, sem números nem premissas do gestor. Se o modelo falhar duas vezes, a
pergunta segue como está, tratada como no escopo, e as camadas seguintes (score
mínimo e instrução no prompt da resposta) continuam valendo.
"""

import json
import logging
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ValidationError

from src.rag.prompts import ANALYSIS_PROMPT, HISTORY_INTRO
from src.rag.schemas import ConversationTurn

logger = logging.getLogger(__name__)

ATTEMPTS = 2


class QuestionAnalysis(BaseModel):
    kind: Literal["in_scope", "greeting", "out_of_scope"]
    search_topic: str
    clean_question: str


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


def format_history(history: list[ConversationTurn]) -> str:
    lines = []
    for turn in history:
        lines.append(f"Pergunta anterior: {turn.question}")
        lines.append(f"Resposta anterior: {turn.answer}")
    return "\n".join(lines)


def build_analysis_messages(
    question: str, history: list[ConversationTurn]
) -> list[tuple[str, str]]:
    messages = [("system", ANALYSIS_PROMPT)]
    if history:
        messages.append(("human", f"{HISTORY_INTRO}\n{format_history(history)}"))
    messages.append(("human", f"Mensagem do gestor a classificar:\n{question}"))
    return messages


def analyze_question(question: str, history: list[ConversationTurn], llm) -> AnalysisResult:
    structured = llm.with_structured_output(QuestionAnalysis)
    messages = build_analysis_messages(question, history)
    for attempt in range(1, ATTEMPTS + 1):
        try:
            analysis = validate_analysis(structured.invoke(messages))
        except Exception:
            logger.warning("etapa=analise tentativa=%d erro=chamada", attempt, exc_info=True)
            analysis = None
        if analysis is not None:
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
