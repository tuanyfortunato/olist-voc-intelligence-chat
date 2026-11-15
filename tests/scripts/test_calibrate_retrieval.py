from scripts.calibrate_retrieval import calibration_rows, summarize_rows
from scripts.questions import TestQuestion
from src.rag.question_analysis import AnalysisResult, QuestionAnalysis
from src.rag.retriever import Candidate
from src.rag.schemas import RetrievedReview


def fake_analyze(question):
    return AnalysisResult(
        QuestionAnalysis(
            kind="in_scope", search_topic=f"tema de {question}", clean_question=question
        ),
        fallback_used=False,
    )


def fake_search(embedding, n):
    return [
        Candidate(
            RetrievedReview(
                f"r{i}", 1, "bebes", "no_prazo", "2018-03-10", "Veio quebrado", 0.9 - i / 100
            ),
            [0.0, 1.0, 0.0],
        )
        for i in range(n)
    ], 12.5


def test_calibration_rows_cover_both_variants():
    questions = [TestQuestion(2, "O que falam de defeito?", "with_evidence", "x")]
    embedded = []
    rows = calibration_rows(
        questions,
        analyze=fake_analyze,
        embed=lambda text: embedded.append(text) or [1.0, 0.0, 0.0],
        search=fake_search,
        n=3,
    )
    assert embedded == ["O que falam de defeito?", "tema de O que falam de defeito?"]
    assert len(rows) == 6
    assert {row["variant"] for row in rows} == {"original", "rewritten"}
    first = rows[0]
    assert first["question_id"] == 2 and first["rank"] == 1
    assert first["similarity"] == 0.9 and first["text_length"] == len("Veio quebrado")
    assert first["search_ms"] == 12.5


def test_out_of_scope_question_only_uses_original_text():
    def analyze(question):
        return AnalysisResult(
            QuestionAnalysis(kind="out_of_scope", search_topic="", clean_question=""), False
        )

    questions = [TestQuestion(6, "Faturamento?", "out_of_scope", "x")]
    rows = calibration_rows(questions, analyze, lambda t: [1.0], fake_search, n=2)
    assert {row["variant"] for row in rows} == {"original"}
    assert rows[0]["kind"] == "out_of_scope"


def test_summarize_rows_reports_similarity_levels():
    questions = [TestQuestion(2, "O que falam de defeito?", "with_evidence", "x")]
    rows = calibration_rows(questions, fake_analyze, lambda t: [1.0], fake_search, n=15)
    summary = summarize_rows(rows)
    line = next(s for s in summary if s["variant"] == "rewritten")
    assert line["top1"] == 0.9 and line["top10"] == 0.81 and line["top15"] == 0.76
