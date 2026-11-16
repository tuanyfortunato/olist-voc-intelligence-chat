import pytest

from src.api.quota import DailyQuota

from .conftest import KEY, fixed_clock, make_client

QUESTION = {"question": "O que falam do frete?"}

# A rota /api/ask entra na Tarefa 8.2; até lá, estes testes falham de propósito.
pytestmark = pytest.mark.xfail(reason="rota /api/ask ainda não existe", strict=True)


@pytest.mark.parametrize("headers", [{}, {"X-Access-Key": ""}, {"X-Access-Key": "errada"}])
def test_bad_key_is_401_and_does_not_consume_quota(client_with_quota, headers):
    client, quota = client_with_quota
    response = client.post("/api/ask", json=QUESTION, headers=headers)
    assert response.status_code == 401
    assert response.json() == {"detail": "Chave de acesso inválida."}
    assert quota.used == 0


def test_missing_key_is_401_even_with_invalid_body(client_with_quota):
    client, quota = client_with_quota
    response = client.post("/api/ask", json={"question": "a" * 501})
    assert response.status_code == 401
    assert quota.used == 0


def test_server_without_key_refuses_everything(fake_pipe):
    quota = DailyQuota(limit=10, now=fixed_clock)
    with make_client(fake_pipe, quota=quota, access_key="") as client:
        for headers in [{}, {"X-Access-Key": ""}, KEY]:
            assert client.post("/api/ask", json=QUESTION, headers=headers).status_code == 401
    assert quota.used == 0 and fake_pipe.calls == 0
