import pytest
from botocore.exceptions import ClientError

from src.knowledge_base.indexing import embed_with_retry, index_documents
from src.knowledge_base.preparation import ReviewDocument
from src.vector_store import open_collection


def make_doc(i):
    return ReviewDocument(
        review_id=f"r{i}",
        order_id=f"o{i}",
        rating=5,
        review_date="2018-03-10",
        category="cama_mesa_banho",
        delivery="no_prazo",
        original_text=f"Comentário {i}",
        embedding_text=f"Comentário {i}",
    )


def fake_embed(texts):
    return [[float(len(text)), 1.0, 0.0] for text in texts]


class RecordingEmbed:
    def __init__(self):
        self.batches = []

    def __call__(self, texts):
        self.batches.append(list(texts))
        return fake_embed(texts)


class FlakyEmbed:
    """Falha as primeiras chamadas com o código de erro dado e depois responde."""

    def __init__(self, fail_times, code):
        self.fail_times = fail_times
        self.code = code
        self.count = 0

    def __call__(self, texts):
        self.count += 1
        if self.count <= self.fail_times:
            raise ClientError({"Error": {"Code": self.code, "Message": "x"}}, "InvokeModel")
        return [[0.0] * 4 for _ in texts]


@pytest.fixture
def collection(tmp_path):
    return open_collection(tmp_path, "teste", create=True)


@pytest.fixture
def docs():
    return [make_doc(i) for i in range(5)]


def test_index_documents_skips_existing(collection, docs):
    index_documents(docs[:2], collection, fake_embed, workers=2, batch_size=2)
    stats = index_documents(docs, collection, fake_embed, workers=2, batch_size=2)
    assert stats.skipped == 2
    assert stats.indexed == 3
    assert collection.count() == 5


def test_index_documents_sends_batches(collection, docs):
    embed = RecordingEmbed()
    index_documents(docs, collection, embed, workers=1, batch_size=2)
    assert sorted(len(batch) for batch in embed.batches) == [1, 2, 2]


def test_index_documents_stores_metadata_and_text(collection, docs):
    index_documents(docs, collection, fake_embed, workers=1, batch_size=10)
    stored = collection.get(ids=["r3"], include=["metadatas", "documents"])
    assert stored["documents"] == ["Comentário 3"]
    assert stored["metadatas"][0]["delivery"] == "no_prazo"
    assert stored["metadatas"][0]["rating"] == 5


def test_embed_with_retry_retries_throttling():
    embed = FlakyEmbed(fail_times=2, code="ThrottlingException")
    assert embed_with_retry(embed, ["x"], sleep=lambda s: None) == [[0.0] * 4]
    assert embed.count == 3


def test_embed_with_retry_gives_up_after_attempts():
    embed = FlakyEmbed(fail_times=10, code="ThrottlingException")
    with pytest.raises(ClientError):
        embed_with_retry(embed, ["x"], attempts=3, sleep=lambda s: None)
    assert embed.count == 3


def test_embed_with_retry_raises_other_errors_immediately():
    embed = FlakyEmbed(fail_times=1, code="ValidationException")
    with pytest.raises(ClientError):
        embed_with_retry(embed, ["x"], sleep=lambda s: None)
    assert embed.count == 1


def test_failed_batch_cancels_pending_batches(collection):
    docs = [make_doc(i) for i in range(10)]
    embed = FlakyEmbed(fail_times=100, code="ValidationException")
    with pytest.raises(ClientError):
        index_documents(docs, collection, embed, workers=1, batch_size=1)
    # A thread pode já ter começado o lote seguinte quando o cancelamento chega
    assert embed.count <= 2


def test_embed_with_retry_survives_long_throttling_with_capped_delay():
    embed = FlakyEmbed(fail_times=8, code="ThrottlingException")
    delays = []
    assert embed_with_retry(embed, ["x"], sleep=delays.append) == [[0.0] * 4]
    assert embed.count == 9
    assert max(delays) <= 61
    assert delays[-1] >= 60
