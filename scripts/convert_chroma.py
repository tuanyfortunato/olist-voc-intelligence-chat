"""Converte os embeddings gravados no formato do Chroma para Parquet.

Roda uma única vez, no modo convert do workflow Build index, para aproveitar os
40.521 embeddings já gerados pelo Cohere sem chamar o modelo de novo. O Chroma
não faz mais parte do projeto; o workflow instala o pacote só para este passo.

Uso, a partir da raiz do projeto, com a coleção antiga em data/chroma/:
    python -m scripts.convert_chroma
"""

import logging
import shutil
from dataclasses import replace
from pathlib import Path

import chromadb

from src.config import get_settings
from src.knowledge_base.embedding_store import ParquetEmbeddingStore
from src.logging_config import setup_logging
from src.vector_store import check_manifest, read_manifest, write_manifest

logger = logging.getLogger(__name__)

CHROMA_DIR = Path("data/chroma")
INDEX_DIR = Path("data/index")
COLLECTION_NAME = "olist_reviews"
PAGE_SIZE = 5000


def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)

    old_manifest = read_manifest(CHROMA_DIR)
    collection = chromadb.PersistentClient(path=str(CHROMA_DIR)).get_collection(
        COLLECTION_NAME, embedding_function=None
    )
    total = collection.count()

    shutil.rmtree(INDEX_DIR, ignore_errors=True)
    store = ParquetEmbeddingStore(INDEX_DIR)
    for offset in range(0, total, PAGE_SIZE):
        page = collection.get(
            include=["embeddings", "documents", "metadatas"], limit=PAGE_SIZE, offset=offset
        )
        sizes = {len(vector) for vector in page["embeddings"]}
        if sizes != {settings.embedding_dimensions}:
            raise RuntimeError(f"Vetores com tamanho inesperado: {sizes}")
        store.add(
            ids=page["ids"],
            embeddings=[list(vector) for vector in page["embeddings"]],
            documents=page["documents"],
            metadatas=page["metadatas"],
        )
        logger.info("etapa=conversao lidos=%d de %d", offset + len(page["ids"]), total)

    count = store.write_final(INDEX_DIR / "embeddings.parquet")
    manifest = replace(old_manifest, document_count=count)
    check_manifest(manifest, settings, old_manifest.document_count)
    write_manifest(INDEX_DIR, manifest)
    logger.info("etapa=conversao concluida linhas=%d", count)


if __name__ == "__main__":
    main()
