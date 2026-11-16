import logging

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError

from src.api.quota import DailyQuota
from src.rag.schemas import ConversationTurn

from .conftest import KEY, FakePipeline, fixed_clock, make_client

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


@pytest.fixture
def client_quota_1(fake_pipe):
    with make_client(fake_pipe, quota=DailyQuota(limit=1, now=fixed_clock)) as test_client:
        yield test_client


def test_ask_returns_answer(client):
    r = client.post("/api/ask", json={"question": "Quais reclamações sobre entrega?"}, headers=KEY)
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
    assert client.post("/api/ask", json=body, headers=KEY).status_code == 200
    question, history = fake_pipe.received[0]
    assert question == "E sobre o frete?"
    assert history == [ConversationTurn("Quais reclamações sobre entrega?", "Atrasos [1].")]


def test_question_too_long_is_422_before_pipeline(client, fake_pipe):
    r = client.post("/api/ask", json={"question": "a" * 501}, headers=KEY)
    assert r.status_code == 422 and fake_pipe.calls == 0


def test_too_much_history_is_422_before_pipeline(client, fake_pipe):
    turn = {"question": "q", "answer": "a"}
    r = client.post("/api/ask", json={"question": "x", "history": [turn] * 4}, headers=KEY)
    assert r.status_code == 422 and fake_pipe.calls == 0


def test_bedrock_throttling_is_503(client_throttled, caplog):
    with caplog.at_level(logging.ERROR):
        r = client_throttled.post("/api/ask", json={"question": "x"}, headers=KEY)
    assert r.status_code == 503
    assert "Tente de novo" in r.json()["detail"]
    assert "ThrottlingException" not in r.text
    assert any(record.exc_info for record in caplog.records)


def test_bedrock_unreachable_is_503():
    pipeline = FakePipeline(error=EndpointConnectionError(endpoint_url="https://bedrock"))
    with make_client(pipeline) as client:
        r = client.post("/api/ask", json={"question": "x"}, headers=KEY)
    assert r.status_code == 503


def test_unexpected_error_is_generic_500(client_broken, caplog):
    with caplog.at_level(logging.ERROR):
        r = client_broken.post("/api/ask", json={"question": "x"}, headers=KEY)
    assert r.status_code == 500
    assert "detalhe interno" not in r.text
    assert any(record.exc_info for record in caplog.records)


def test_quota_exceeded_is_429(client_quota_1):
    client_quota_1.post("/api/ask", json={"question": "x"}, headers=KEY)
    r = client_quota_1.post("/api/ask", json={"question": "x"}, headers=KEY)
    assert r.status_code == 429
    assert r.json() == {"detail": "Limite diário de perguntas atingido."}


def test_invalid_body_does_not_consume_quota(fake_pipe):
    quota = DailyQuota(limit=10, now=fixed_clock)
    with make_client(fake_pipe, quota=quota) as client:
        client.post("/api/ask", json={"question": ""}, headers=KEY)
    assert quota.used == 0
