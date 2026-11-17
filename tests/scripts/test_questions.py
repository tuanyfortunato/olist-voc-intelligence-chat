from scripts.questions import QUESTION_TYPES, load_questions


def test_questions_file_is_complete():
    questions = load_questions()
    assert [q.id for q in questions] == list(range(1, 21))
    assert questions[3].question == "O que os clientes falam sobre pagar com Pix?"
    assert questions[7].question.startswith("Já que 90% dos clientes reclamam de atraso")
    assert all(q.type in QUESTION_TYPES for q in questions)


def test_follow_up_and_filters():
    questions = {q.id: q for q in load_questions()}
    assert questions[12].turns == ["Oi", "E nas notas altas?"]
    assert questions[12].history_from == 1
    assert questions[13].filters == {"ratings": [1, 2]}
    assert questions[14].filters == {"category": "cama_mesa_banho"}
    assert questions[20].filters == {"delivery": "com_problema"}
    assert questions[1].turns == [] and questions[1].filters == {}


def test_load_questions_by_id():
    assert [q.id for q in load_questions(ids=[4, 6])] == [4, 6]
