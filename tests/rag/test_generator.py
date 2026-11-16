from src.rag.generator import generate_answer
from src.rag.prompts import ANSWER_SYSTEM_PROMPT, build_answer_messages
from src.rag.schemas import RetrievedReview


class FakeChatLLM:
    def __init__(self, content):
        self.content = content
        self.messages = []

    def invoke(self, messages):
        self.messages.append(messages)
        return type("Message", (), {"content": self.content})()


def review(review_id, rating, text):
    return RetrievedReview(review_id, rating, "bebes", "no_prazo", "2018-03-10", text, 0.7)


def test_answer_messages_contain_question_and_context_only():
    messages = build_answer_messages(
        "Quais reclamações sobre entrega?", "[1] (avaliação r1, nota 1) Não chegou"
    )
    assert [role for role, _ in messages] == ["system", "human"]
    assert "Quais reclamações sobre entrega?" in messages[1][1]
    assert "[1] (avaliação r1, nota 1) Não chegou" in messages[1][1]


def test_system_prompt_rules():
    for rule in [
        "[n]",
        "avaliações recuperadas",
        "premissa",
        "Lannister",
        "não há informação suficiente",
        "percentuais",
    ]:
        assert rule in ANSWER_SYSTEM_PROMPT, rule


def test_generate_answer_returns_content_and_sends_context():
    llm = FakeChatLLM("Atrasos aparecem [1].")
    answer = generate_answer("Pergunta?", [review("r1", 1, "Atrasou")], llm)
    assert answer == "Atrasos aparecem [1]."
    assert "[1] (avaliação r1, nota 1) Atrasou" in llm.messages[0][1][1]
