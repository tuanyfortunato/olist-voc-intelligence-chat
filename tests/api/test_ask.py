import logging

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError

from src.rag.schemas import ConversationTurn

from .conftest import FakePipeline, make_client

THROTTLING = ClientError({"Error": {"Code": "ThrottlingException"}}, "Converse")


@pytest.fixture
def client_throttled():
    with make_client(FakePipeline(error=THROTTLING)) as test_client:
        yield test_client


@pytest.fixture
def client_broken():
    # Fixture, e não dentro do teste: a subida da API reconfigura o log e
    # tiraria o capturador do pytest instalado para o corpo do teste.
    with make_client(FakePipeline(error=RuntimeError("detalhe interno"))) as test_client:
        yield test_client


def test_ask_returns_answer(client):
    r = client.post("/api/ask", json={"question": "Quais reclamações sobre entrega?"})
    assert r.status_code == 200
    assert r.json()["status"] == "answered" and r.json()["cited"][0]["number"] == 1
    assert r.json()["cited"][0]["review_id"] == "r1"
    assert r.json()["uncited"][0]["review_id"] == "r2"
    assert r.json()["search_topic"] == "reclamações sobre entrega"


def test_question_and_history_reach_pipeline(client, fake_pipe):
    body = {
        "question": "  E sobre o frete?  ",
        "history": [{"question": "Quais reclamações sobre entrega?", "answer": "Atrasos [1]."}],
    }
    assert client.post("/api/ask", json=body).status_code == 200
    question, history = fake_pipe.received[0]
    assert question == "E sobre o frete?"
    assert history == [ConversationTurn("Quais reclamações sobre entrega?", "Atrasos [1].")]


def test_question_too_long_is_422_before_pipeline(client, fake_pipe):
    r = client.post("/api/ask", json={"question": "a" * 501})
    assert r.status_code == 422 and fake_pipe.calls == 0


def test_too_much_history_is_422_before_pipeline(client, fake_pipe):
    turn = {"question": "q", "answer": "a"}
    r = client.post("/api/ask", json={"question": "x", "history": [turn] * 4})
    assert r.status_code == 422 and fake_pipe.calls == 0


def test_bedrock_throttling_is_503(client_throttled, caplog):
    with caplog.at_level(logging.ERROR):
        r = client_throttled.post("/api/ask", json={"question": "x"})
    assert r.status_code == 503
    assert "Tente de novo" in r.json()["detail"]
    assert "ThrottlingException" not in r.text
    assert any(record.exc_info for record in caplog.records)


def test_bedrock_unreachable_is_503():
    pipeline = FakePipeline(error=EndpointConnectionError(endpoint_url="https://bedrock"))
    with make_client(pipeline) as client:
        r = client.post("/api/ask", json={"question": "x"})
    assert r.status_code == 503


def test_unexpected_error_is_generic_500(client_broken, caplog):
    with caplog.at_level(logging.ERROR):
        r = client_broken.post("/api/ask", json={"question": "x"})
    assert r.status_code == 500
    assert "detalhe interno" not in r.text
    assert any(record.exc_info for record in caplog.records)


def test_filters_reach_pipeline(client, fake_pipe):
    from src.rag.schemas import SearchFilters

    body = {
        "question": "Quais temas nas entregas?",
        "filters": {"delivery": "com_problema", "ratings": [1, 2]},
    }
    response = client.post("/api/ask", json=body)
    assert response.status_code == 200
    assert fake_pipe.filters == SearchFilters(
        ratings=[1, 2], category=None, delivery="com_problema"
    )


def test_no_filters_reach_pipeline_as_none(client, fake_pipe):
    client.post("/api/ask", json={"question": "x"})
    assert fake_pipe.filters is None


def test_categories_come_from_manifest(client):
    response = client.get("/api/categories")
    assert response.status_code == 200
    assert response.json() == {"categories": ["bebes"]}
