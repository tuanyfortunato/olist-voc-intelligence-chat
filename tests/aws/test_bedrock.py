import io
import json

import pytest

from src.aws.bedrock import embed_query, embed_texts


class FakeClient:
    """Imita o invoke_model do bedrock-runtime e guarda o que recebeu."""

    def __init__(self, dimensions):
        self.dimensions = dimensions
        self.calls = 0
        self.last_body = None
        self.last_model_id = None

    def invoke_model(self, modelId, body, **kwargs):
        self.calls += 1
        self.last_model_id = modelId
        self.last_body = body
        texts = json.loads(body)["texts"]
        response = {"embeddings": [[0.1] * self.dimensions for _ in texts]}
        return {"body": io.BytesIO(json.dumps(response).encode())}


def test_embed_texts_sends_documents_in_one_call(settings):
    client = FakeClient(dimensions=1024)
    vectors = embed_texts(client, ["Chegou quebrado", "Ótimo"], "search_document", settings)
    assert json.loads(client.last_body) == {
        "texts": ["Chegou quebrado", "Ótimo"],
        "input_type": "search_document",
        "truncate": "END",
    }
    assert client.last_model_id == "cohere.embed-multilingual-v3"
    assert client.calls == 1
    assert len(vectors) == 2 and len(vectors[0]) == 1024


def test_embed_query_uses_search_query(settings):
    client = FakeClient(dimensions=1024)
    assert len(embed_query(client, "O que falam do frete?", settings)) == 1024
    assert json.loads(client.last_body)["input_type"] == "search_query"


@pytest.mark.parametrize("texts", [[], ["x"] * 97])
def test_embed_texts_rejects_bad_batch_size(settings, texts):
    client = FakeClient(dimensions=1024)
    with pytest.raises(ValueError):
        embed_texts(client, texts, "search_document", settings)
    assert client.calls == 0
