from src.config import Settings
from src.rag.pipeline import RagPipeline
from src.rag.question_analysis import QuestionAnalysis
from src.rag.schemas import RetrievedReview


class FakeAnalysisLLM:
    def __init__(self, kind="in_scope", topic="tema reescrito", question="pergunta limpa"):
        self.analysis = QuestionAnalysis(kind=kind, search_topic=topic, clean_question=question)

    def with_structured_output(self, schema):
        return self

    def invoke(self, messages):
        return self.analysis


class FakeAnswerLLM:
    def __init__(self, answer):
        self.answer = answer
        self.calls = 0
        self.messages = []

    def invoke(self, messages):
        self.calls += 1
        self.messages.append(messages)
        return type("Message", (), {"content": self.answer})()


def review(review_id):
    return RetrievedReview(
        review_id, 1, "bebes", "no_prazo", "2018-03-10", f"Texto {review_id}", 0.7
    )


def fake_pipeline(retrieved=(), answer="Resposta [1].", use_rewrite=True, **analysis):
    embedded = []
    pipeline = RagPipeline(
        settings=Settings(use_rewrite=use_rewrite),
        analysis_llm=FakeAnalysisLLM(**analysis),
        answer_llm=FakeAnswerLLM(answer),
        embed=lambda text: embedded.append(text) or [1.0, 0.0, 0.0],
        search=lambda embedding: list(retrieved),
    )
    pipeline.embedded_texts = embedded
    return pipeline


def test_pipeline_splits_cited_and_uncited():
    pipe = fake_pipeline(
        [review("r1"), review("r2"), review("r3"), review("r4")], "A [1][3] e B [3]."
    )
    result = pipe.ask("Quais reclamações sobre entrega?")
    assert [r.review_id for r in result.cited] == ["r1", "r3"]
    assert [r.review_id for r in result.uncited] == ["r2", "r4"]
    assert [r.number for r in result.cited] == [1, 3]
    assert [r.number for r in result.uncited] == [2, 4]


def test_pipeline_removes_invalid_citations():
    pipe = fake_pipeline([review("r1"), review("r2"), review("r3")], "A [1][2][3] e [9].")
    assert "[9]" not in pipe.ask("x").answer


def test_pipeline_searches_with_rewritten_topic():
    pipe = fake_pipeline([review("r1")])
    result = pipe.ask("Pergunta original")
    assert pipe.embedded_texts == ["tema reescrito"]
    assert result.original_question == "Pergunta original"
    assert result.search_topic == "tema reescrito"


def test_pipeline_uses_original_question_when_rewrite_disabled():
    pipe = fake_pipeline([review("r1")], use_rewrite=False)
    pipe.ask("Pergunta original")
    assert pipe.embedded_texts == ["Pergunta original"]


def test_answer_uses_clean_question():
    pipe = fake_pipeline([review("r1")], question="O que mais criticam além do atraso?")
    pipe.ask("Já que 90% reclamam de atraso, o que mais criticam?")
    sent = str(pipe.answer_llm.messages[0])
    assert "O que mais criticam além do atraso?" in sent
    assert "90%" not in sent
