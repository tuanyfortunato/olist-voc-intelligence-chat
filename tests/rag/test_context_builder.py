from src.rag.context_builder import (
    build_context,
    extract_citations,
    remove_citations_from_negative_claims,
    remove_invalid_citations,
)
from src.rag.schemas import RetrievedReview


def review(review_id, rating, text):
    return RetrievedReview(review_id, rating, "bebes", "no_prazo", "2018-03-10", text, 0.7)


def test_build_context_numbering():
    context = build_context([review("r1", 1, "Não chegou"), review("r2", 5, "Ótimo")])
    assert context.splitlines() == [
        "[1] (avaliação r1, nota 1) Não chegou",
        "[2] (avaliação r2, nota 5) Ótimo",
    ]


def test_extract_citations_formats():
    check = extract_citations("Atrasos são comuns [1][4], e há defeitos [2, 4] e [6].", n_reviews=6)
    assert check.cited == [1, 4, 2, 6]
    assert check.invalid == []


def test_extract_citations_out_of_range():
    check = extract_citations("Veja [0], [3] e [17].", n_reviews=15)
    assert check.cited == [3]
    assert check.invalid == [0, 17]


def test_extract_citations_repeated_numbers_count_once():
    assert extract_citations("A [2][2] e B [2].", n_reviews=3).cited == [2]


def test_extract_citations_ignores_non_numeric_brackets():
    assert extract_citations("A loja [Lannister] demorou [2].", n_reviews=3).cited == [2]


def test_remove_invalid_citations():
    assert (
        remove_invalid_citations("Defeitos [1, 17] e trocas [17].", [17])
        == "Defeitos [1] e trocas."
    )


def test_remove_invalid_citations_keeps_text_without_invalid():
    assert remove_invalid_citations("Defeitos [1].", []) == "Defeitos [1]."


def test_negative_claim_loses_its_citations():
    answer = "- Nenhum dos comentários recuperados fala sobre o pagamento com Pix. [1][2][4]"
    assert remove_citations_from_negative_claims(answer) == (
        "- Nenhum dos comentários recuperados fala sobre o pagamento com Pix."
    )


def test_negative_claim_only_touches_its_own_sentence():
    answer = (
        "Alguns clientes gostam do aplicativo [4][11]. "
        "Nenhum comentário menciona problemas com o aplicativo em si [2][6]."
    )
    assert remove_citations_from_negative_claims(answer) == (
        "Alguns clientes gostam do aplicativo [4][11]. "
        "Nenhum comentário menciona problemas com o aplicativo em si."
    )


def test_answer_without_negative_claim_is_unchanged():
    answer = "- Atrasos [1][2].\n- Nenhum vendedor respondeu, segundo um cliente [3]."
    assert remove_citations_from_negative_claims(answer) == answer
