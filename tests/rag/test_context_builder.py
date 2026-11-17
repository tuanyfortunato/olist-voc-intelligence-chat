from src.rag.context_builder import (
    build_context,
    extract_citations,
    is_label_only_list,
    labels_to_sentence,
    remove_citations_from_negative_claims,
    remove_invalid_citations,
    soften_unsupported_quantities,
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


def numbered(*texts):
    return [
        RetrievedReview(f"r{i}", 1, "bebes", "no_prazo", "2018-03-10", text, 0.7, number=i)
        for i, text in enumerate(texts, start=1)
    ]


def test_soften_many_customers_with_two_citations():
    reviews = numbered("Veio quebrado", "Chegou com defeito")
    answer = "Vários clientes relatam produtos com defeito [1][2]."
    assert soften_unsupported_quantities(answer, reviews) == (
        "Alguns clientes relatam produtos com defeito [1][2]."
    )


def test_soften_keeps_gender():
    reviews = numbered("Demorou", "Atrasou")
    answer = "Há muitas reclamações de atraso [1, 2]."
    assert soften_unsupported_quantities(answer, reviews) == (
        "Há algumas reclamações de atraso [1, 2]."
    )


def test_soften_keeps_many_with_three_citations():
    reviews = numbered("Veio quebrado", "Defeito", "Não funciona")
    answer = "Vários clientes relatam problemas recorrentes com defeito [1][2][3]."
    assert soften_unsupported_quantities(answer, reviews) == answer


def test_soften_removes_recurrence_without_cue():
    reviews = numbered("Primeira vez que compro e veio errado")
    answer = "Um cliente relata problemas recorrentes com o pedido [1]."
    assert soften_unsupported_quantities(answer, reviews) == (
        "Um cliente relata problemas com o pedido [1]."
    )


def test_soften_keeps_recurrence_when_review_says_so():
    reviews = numbered("Mais uma vez o pedido veio errado", "Veio errado")
    answer = "Vários clientes relatam erros recorrentes no pedido [1][2]."
    assert soften_unsupported_quantities(answer, reviews) == (
        "Alguns clientes relatam erros recorrentes no pedido [1][2]."
    )


def test_soften_only_touches_sentence_with_few_citations():
    reviews = numbered("Atrasou", "Demorou", "Não chegou", "Veio errado")
    answer = (
        "Muitos clientes reclamam de atraso [1][2][3]. "
        "Vários clientes citam o pedido errado com frequência [4]."
    )
    assert soften_unsupported_quantities(answer, reviews) == (
        "Muitos clientes reclamam de atraso [1][2][3]. Alguns clientes citam o pedido errado [4]."
    )


def test_soften_ignores_sentences_without_citation_and_other_nouns():
    reviews = numbered("Atrasou")
    answer = "Vários clientes reclamam. O pedido atrasou muitos dias [1]."
    assert soften_unsupported_quantities(answer, reviews) == answer


def test_soften_recurrence_as_predicate_keeps_the_other_verb():
    reviews = numbered("Atrasou", "Não chegou")
    answer = (
        "Alguns clientes dizem que os problemas na entrega são recorrentes "
        "e afetam a confiança [1][2]."
    )
    assert soften_unsupported_quantities(answer, reviews) == (
        "Alguns clientes dizem que os problemas na entrega afetam a confiança [1][2]."
    )


LABEL_LIST = (
    "- Atraso na entrega: [1][2][4]\n"
    "- Falha na entrega: [5]\n"
    "- Insatisfação com a transportadora: [4]"
)


def test_label_only_list_is_detected():
    assert is_label_only_list(LABEL_LIST)


def test_sentences_are_not_label_only():
    assert not is_label_only_list("- Atraso na entrega: vários clientes reclamam [1][2].")
    assert not is_label_only_list("Os clientes reclamam de atraso [1].")
    assert not is_label_only_list("")


def test_labels_to_sentence_keeps_citations():
    assert labels_to_sentence(LABEL_LIST) == (
        "Nos comentários recuperados aparecem estes temas: atraso na entrega [1][2][4], "
        "falha na entrega [5] e insatisfação com a transportadora [4]."
    )


def test_soften_drops_sentence_whose_claim_is_only_recurrence():
    answer = (
        "- Vários clientes relatam atraso [1][2][3].\n"
        "- Alguns clientes mencionam que os problemas na entrega são recorrentes [2]."
    )
    reviews = numbered("Atrasou", "Não chegou", "Demorou")
    assert soften_unsupported_quantities(answer, reviews) == (
        "- Vários clientes relatam atraso [1][2][3]."
    )


def test_soften_predicate_with_many_citations_says_many_comments():
    reviews = numbered("Atrasou", "Não chegou", "Demorou")
    answer = "Problemas com a entrega são frequentes, com produtos não entregues [1][2][3]."
    assert soften_unsupported_quantities(answer, reviews) == (
        "Problemas com a entrega aparecem em vários comentários, "
        "com produtos não entregues [1][2][3]."
    )


def test_soften_drops_uncited_recurrence_claim_and_keeps_negation():
    reviews = numbered("Atrasou", "Não chegou", "Demorou")
    answer = (
        "Clientes relatam atraso [1][2][3].\n\n"
        "Esses comentários indicam que a entrega ruim é um tema recorrente entre os clientes.\n"
        "Não há menção de que os problemas sejam recorrentes."
    )
    assert soften_unsupported_quantities(answer, reviews) == (
        "Clientes relatam atraso [1][2][3].\n\nNão há menção de que os problemas sejam recorrentes."
    )


def test_negative_claim_with_citation_in_the_middle_is_dropped():
    answer = (
        "- Vários clientes pedem embalagem [1][3][4].\n"
        "- Nenhum comentário fala sobre isso de forma detalhada como no caso de [10], "
        "que menciona papel de presente."
    )
    assert remove_citations_from_negative_claims(answer) == (
        "- Vários clientes pedem embalagem [1][3][4]."
    )
