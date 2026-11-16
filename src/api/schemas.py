"""Formato das mensagens da API: o que a página envia e o que recebe de volta.

Os limites da pergunta e do histórico são conferidos aqui, pelo FastAPI, antes
de qualquer chamada ao Bedrock. Os valores são os mesmos de Settings.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, field_validator

from src.config import Settings
from src.themes.taxonomy import THEME_IDS

_DEFAULTS = Settings()
HISTORY_ANSWER_CHARS = _DEFAULTS.history_answer_chars

Question = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=_DEFAULTS.max_question_chars),
]
Rating = Annotated[int, Field(ge=1, le=5)]


class HistoryTurn(BaseModel):
    """Uma troca anterior da conversa. Respostas longas são cortadas, não recusadas."""

    question: str
    answer: str

    @field_validator("answer")
    @classmethod
    def cut_answer(cls, value: str) -> str:
        return value[:HISTORY_ANSWER_CHARS]


class SearchFiltersIn(BaseModel):
    """Filtros da busca. Os temas são os da classificação em lote (src/themes)."""

    ratings: list[Rating] | None = None
    category: str | None = None
    delivery: Literal["no_prazo", "atrasada", "nao_entregue", "com_problema"] | None = None
    themes: list[str] | None = Field(default=None, max_length=len(THEME_IDS))

    @field_validator("themes")
    @classmethod
    def known_themes(cls, value: list[str] | None) -> list[str] | None:
        if not value:
            return None
        unknown = sorted(set(value) - THEME_IDS)
        if unknown:
            raise ValueError(f"Temas desconhecidos: {', '.join(unknown)}")
        return sorted(set(value))


class AskRequest(BaseModel):
    question: Question
    history: list[HistoryTurn] = Field(default=[], max_length=_DEFAULTS.history_turns)
    filters: SearchFiltersIn | None = None


class ReviewOut(BaseModel):
    """Um comentário recuperado, com o número usado nas citações [n] da resposta."""

    review_id: str
    rating: int
    category: str
    delivery: str
    review_date: str
    original_text: str
    similarity: float
    number: int


class AskResponse(BaseModel):
    # Texto livre: os valores possíveis do status crescem com as etapas do projeto
    status: str
    answer: str
    cited: list[ReviewOut]
    uncited: list[ReviewOut]
    original_question: str
    search_topic: str
    inferred_ratings: list[int] = []
    scope_count: int | None = None
