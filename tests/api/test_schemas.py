import pytest
from pydantic import ValidationError

from src.api.schemas import AskRequest


def test_question_limits():
    assert AskRequest(question="  O que falam do frete?  ").question == "O que falam do frete?"
    AskRequest(question="a" * 500)
    for bad in ["", "   ", "a" * 501]:
        with pytest.raises(ValidationError):
            AskRequest(question=bad)


def test_history_limits():
    turn = {"question": "q", "answer": "x" * 3000}
    assert len(AskRequest(question="q", history=[turn]).history[0].answer) == 1500
    AskRequest(question="q", history=[turn] * 3)
    with pytest.raises(ValidationError):
        AskRequest(question="q", history=[turn] * 4)


def test_filters_are_accepted_and_validated():
    request = AskRequest(
        question="q", filters={"ratings": [1, 2], "category": "bebes", "delivery": "atrasada"}
    )
    assert request.filters.ratings == [1, 2]
    with pytest.raises(ValidationError):
        AskRequest(question="q", filters={"ratings": [6]})
    with pytest.raises(ValidationError):
        AskRequest(question="q", filters={"delivery": "extraviada"})
