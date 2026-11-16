"""Estruturas de dados que passam de uma etapa do fluxo da pergunta para a outra."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ConversationTurn:
    """Uma troca anterior da conversa, enviada pela página."""

    question: str
    answer: str


@dataclass(frozen=True)
class RetrievedReview:
    """Um comentário recuperado pela busca, com a similaridade com o tema da pergunta."""

    review_id: str
    rating: int
    category: str
    delivery: str
    review_date: str
    original_text: str
    similarity: float
    # Número do comentário no contexto enviado ao modelo, o mesmo das citações [n]
    number: int = 0


@dataclass(frozen=True)
class AskResult:
    """Resultado de uma pergunta, devolvido pela API à página."""

    status: str
    answer: str
    cited: list[RetrievedReview]
    uncited: list[RetrievedReview]
    original_question: str
    search_topic: str
