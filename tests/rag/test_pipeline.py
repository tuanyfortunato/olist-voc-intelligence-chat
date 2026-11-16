import pytest

from src.config import Settings
from src.rag.pipeline import RagPipeline, decide_status
from src.rag.prompts import GREETING_MESSAGE, NO_EVIDENCE_MESSAGE, OUT_OF_SCOPE_MESSAGE
from src.rag.question_analysis import QuestionAnalysis
from src.rag.schemas import RetrievedReview


class FakeAnalysisLLM:
    def __init__(
        self,
        kind="in_scope",
        topic="tema reescrito",
        question="pergunta limpa",
        removed_premise=False,
        ratings=(),
    ):
        self.analysis = QuestionAnalysis(
            kind=kind,
            search_topic=topic,
            clean_question=question,
            removed_premise=removed_premise,
            ratings=list(ratings),
        )

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
        settings=Settings(use_rewrite=use_rewrite, strong_similarity=0.64),
        analysis_llm=FakeAnalysisLLM(**analysis),
        answer_llm=FakeAnswerLLM(answer),
        embed=lambda text: embedded.append(text) or [1.0, 0.0, 0.0],
        search=lambda embedding, filters=None: (
            pipeline.searched_filters.append(filters) or list(retrieved)
        ),
    )
    pipeline.embedded_texts = embedded
    pipeline.searched_filters = []
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


@pytest.mark.parametrize(
    "retrieved,cited,status",
    [
        (0, 0, "no_evidence"),
        (5, 0, "no_evidence"),
        (5, 1, "weak_evidence"),
        (5, 2, "weak_evidence"),
        (5, 3, "answered"),
    ],
)
def test_decide_status(retrieved, cited, status):
    assert decide_status(retrieved, cited) == status


def test_low_top_similarity_makes_evidence_weak_even_with_many_citations():
    assert decide_status(15, 10, top_similarity=0.61, strong_similarity=0.64) == "weak_evidence"
    assert decide_status(15, 10, top_similarity=0.66, strong_similarity=0.64) == "answered"


def test_pipeline_uses_top_similarity_for_weak_evidence():
    weak = [
        RetrievedReview(f"r{i}", 1, "bebes", "no_prazo", "2018-03-10", "Embalagem", 0.61)
        for i in range(5)
    ]
    pipe = fake_pipeline(weak, "Muitos [1][2][3][4][5].")
    assert pipe.ask("Embalagem de presente?").status == "weak_evidence"


def test_no_retrieved_reviews_skips_answer_llm():
    pipe = fake_pipeline(retrieved=[])
    result = pipe.ask("O que falam do Pix?")
    assert result.status == "no_evidence"
    assert result.answer == NO_EVIDENCE_MESSAGE
    assert pipe.answer_llm.calls == 0


def test_out_of_scope_skips_search_and_answer():
    pipe = fake_pipeline(kind="out_of_scope", topic="", question="")
    result = pipe.ask("Qual o faturamento da Olist em 2018?")
    assert result.status == "out_of_scope" and result.answer == OUT_OF_SCOPE_MESSAGE
    assert pipe.embedded_texts == [] and pipe.answer_llm.calls == 0
    assert result.cited == [] and result.uncited == []


def test_greeting_returns_fixed_message():
    pipe = fake_pipeline(kind="greeting", topic="", question="")
    result = pipe.ask("Oi")
    assert result.status == "greeting" and result.answer == GREETING_MESSAGE
    assert pipe.embedded_texts == []


def test_weak_evidence_when_two_cited():
    pipe = fake_pipeline([review("r1"), review("r2"), review("r3")], "Só isso [1][2].")
    assert pipe.ask("x").status == "weak_evidence"


def test_no_citation_keeps_model_text_and_marks_no_evidence():
    text = "Não há avaliações sobre Pix entre as recuperadas; elas falam de pagamento em geral."
    pipe = fake_pipeline([review("r1"), review("r2")], text)
    result = pipe.ask("O que falam do Pix?")
    assert result.status == "no_evidence" and result.answer == text
    assert result.cited == [] and len(result.uncited) == 2


def test_answered_with_three_citations():
    pipe = fake_pipeline([review("r1"), review("r2"), review("r3")], "A [1][2][3].")
    assert pipe.ask("x").status == "answered"


def test_removed_premise_adds_fixed_note_without_the_premise():
    from src.rag.prompts import PREMISE_NOTE

    pipe = fake_pipeline(
        [review("r1"), review("r2"), review("r3")],
        "Críticas [1][2][3].",
        question="O que mais criticam além do atraso?",
        removed_premise=True,
    )
    result = pipe.ask("Já que 90% reclamam de atraso, o que mais criticam?")
    assert result.answer.endswith(PREMISE_NOTE)
    assert "90%" not in result.answer


def test_no_note_without_removed_premise():
    from src.rag.prompts import PREMISE_NOTE

    pipe = fake_pipeline([review("r1"), review("r2"), review("r3")], "A [1][2][3].")
    assert PREMISE_NOTE not in pipe.ask("x").answer


def test_no_note_when_model_flags_premise_but_question_is_unchanged():
    from src.rag.prompts import PREMISE_NOTE

    question = "Quais reclamações sobre entrega aparecem com mais frequência?"
    pipe = fake_pipeline(
        [review("r1"), review("r2"), review("r3")],
        "A [1][2][3].",
        question=question,
        removed_premise=True,
    )
    assert PREMISE_NOTE not in pipe.ask(question).answer


def test_filters_reach_search():
    from src.rag.schemas import SearchFilters

    pipe = fake_pipeline([review("r1"), review("r2"), review("r3")], "A [1][2][3].")
    filters = SearchFilters(category="bebes")
    pipe.ask("x", filters=filters)
    assert pipe.searched_filters == [filters]


def test_ratings_from_question_become_filter_when_user_chose_none():
    from src.rag.schemas import SearchFilters

    pipe = fake_pipeline([review("r1"), review("r2"), review("r3")], "A [1][2][3].", ratings=[4, 5])
    result = pipe.ask("E nas notas altas?", filters=SearchFilters(category="bebes"))
    assert pipe.searched_filters == [SearchFilters(ratings=[4, 5], category="bebes")]
    assert result.inferred_ratings == [4, 5]


def test_ratings_chosen_by_user_win_over_ratings_from_question():
    from src.rag.schemas import SearchFilters

    pipe = fake_pipeline([review("r1"), review("r2"), review("r3")], "A [1][2][3].", ratings=[4, 5])
    result = pipe.ask("E nas notas altas?", filters=SearchFilters(ratings=[1]))
    assert pipe.searched_filters == [SearchFilters(ratings=[1])]
    assert result.inferred_ratings == []


def test_history_never_reaches_answer_generation():
    from src.rag.schemas import ConversationTurn

    pipe = fake_pipeline([review("r1"), review("r2"), review("r3")], "A [1][2][3].")
    pipe.ask("E nas notas altas?", history=[ConversationTurn("PERGUNTA_ANTIGA", "RESPOSTA_ANTIGA")])
    sent = str(pipe.answer_llm.messages)
    assert "PERGUNTA_ANTIGA" not in sent and "RESPOSTA_ANTIGA" not in sent


def test_scope_count_comes_with_the_answer_and_failures_are_ignored():
    from src.rag.schemas import SearchFilters

    pipeline = fake_pipeline(retrieved=[review("a"), review("b"), review("c")])
    assert pipeline.ask("Pergunta?").scope_count is None

    counted = []
    pipeline.count = lambda filters: counted.append(filters) or 3300
    filters = SearchFilters(themes=["nao_recebido"])
    assert pipeline.ask("Pergunta?", filters=filters).scope_count == 3300
    assert counted == [filters]

    empty = fake_pipeline(retrieved=[])
    empty.count = lambda filters: 12
    assert empty.ask("Pergunta?").scope_count == 12

    def broken(filters):
        raise RuntimeError("banco")

    pipeline.count = broken
    assert pipeline.ask("Pergunta?").scope_count is None
