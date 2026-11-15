"""Geração dos embeddings e gravação de cada lote.

Os documentos vão ao modelo em lotes, com alguns lotes ao mesmo tempo, e cada
lote é gravado assim que volta. Se a execução parar no meio, a próxima pula os
documentos que já foram gravados e continua dali.
"""

import logging
import random
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from botocore.exceptions import ClientError

from src.knowledge_base.preparation import ReviewDocument

logger = logging.getLogger(__name__)

EmbedFunction = Callable[[list[str]], list[list[float]]]

# Espera máxima entre duas tentativas, em segundos
MAX_RETRY_DELAY = 60.0

# Erros temporários do Bedrock, que valem uma nova tentativa
RETRYABLE_ERRORS = {"ThrottlingException", "ServiceUnavailableException", "ModelNotReadyException"}


@dataclass(frozen=True)
class IndexStats:
    indexed: int
    skipped: int
    seconds: float


def embed_with_retry(
    embed: EmbedFunction,
    texts: list[str],
    attempts: int = 10,
    base_delay: float = 2.0,
    sleep: Callable[[float], None] = time.sleep,
) -> list[list[float]]:
    """Chama o modelo e, se a AWS limitar as chamadas, espera cada vez mais e tenta de novo.

    A espera dobra a cada tentativa até o teto de 60 segundos, com uma pequena
    parte aleatória para que os lotes em paralelo não voltem no mesmo instante.
    """
    for attempt in range(attempts):
        try:
            return embed(texts)
        except ClientError as error:
            code = error.response.get("Error", {}).get("Code")
            if code not in RETRYABLE_ERRORS or attempt == attempts - 1:
                raise
            delay = min(MAX_RETRY_DELAY, base_delay * 2**attempt) + random.uniform(0, 1)
            logger.warning("etapa=indexacao erro=%s nova_tentativa_em=%.0fs", code, delay)
            sleep(delay)
    raise AssertionError("inalcançável")


def index_documents(
    documents: list[ReviewDocument],
    store,
    embed: EmbedFunction,
    workers: int,
    batch_size: int = 96,
) -> IndexStats:
    start = time.monotonic()
    existing = store.existing_ids()
    pending = [doc for doc in documents if doc.review_id not in existing]
    skipped = len(documents) - len(pending)
    batches = [pending[i : i + batch_size] for i in range(0, len(pending), batch_size)]
    logger.info(
        "etapa=indexacao documentos=%d ja_indexados=%d lotes=%d",
        len(documents),
        skipped,
        len(batches),
    )

    indexed = 0
    executor = ThreadPoolExecutor(max_workers=workers)
    futures = {
        executor.submit(embed_with_retry, embed, [doc.embedding_text for doc in batch]): batch
        for batch in batches
    }
    try:
        # A gravação fica na thread principal, um lote por vez
        for future in as_completed(futures):
            batch = futures[future]
            store.add(
                ids=[doc.review_id for doc in batch],
                embeddings=future.result(),
                documents=[doc.embedding_text for doc in batch],
                metadatas=[doc.metadata() for doc in batch],
            )
            indexed += len(batch)
            logger.info(
                "etapa=indexacao indexados=%d de %d segundos=%.0f",
                indexed,
                len(pending),
                time.monotonic() - start,
            )
    except BaseException:
        # Um lote que falhou de vez para a execução. Os lotes ainda na fila são
        # cancelados para não gastar chamadas cujo resultado não seria gravado.
        executor.shutdown(wait=True, cancel_futures=True)
        raise
    executor.shutdown(wait=True)

    return IndexStats(indexed=indexed, skipped=skipped, seconds=time.monotonic() - start)
