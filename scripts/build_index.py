"""Prepara a base de conhecimento e gera o índice do Chroma.

Uso, a partir da raiz do projeto:
    python -m scripts.build_index --mode prepare   # só prepara e mostra os números
    python -m scripts.build_index --mode full      # prepara, indexa e grava o manifesto
"""

import argparse
import json
import logging
from datetime import UTC, datetime
from pathlib import Path

import chromadb

from src.aws.bedrock import embed_texts, get_runtime_client
from src.config import Settings, get_settings
from src.knowledge_base.download import RAW_DATA_DIR
from src.knowledge_base.indexing import EmbedFunction, index_documents
from src.knowledge_base.preparation import (
    MIXED_CATEGORY,
    UNKNOWN,
    ReviewDocument,
    build_documents,
    load_tables,
    summarize,
)
from src.logging_config import setup_logging
from src.vector_store import (
    DISTANCE,
    IndexManifest,
    check_manifest,
    open_collection,
    write_manifest,
)

logger = logging.getLogger(__name__)

SUMMARY_PATH = Path("data/prepare_summary.json")


def build_full_index(
    documents: list[ReviewDocument], settings: Settings, embed: EmbedFunction, index_dir: Path
) -> IndexManifest:
    """Indexa os documentos que ainda não estão na coleção e grava o manifesto."""
    index_dir.mkdir(parents=True, exist_ok=True)
    collection = open_collection(index_dir, settings.collection_name, create=True)
    stats = index_documents(
        documents,
        collection,
        embed,
        workers=settings.index_workers,
        batch_size=settings.embedding_batch_size,
    )
    logger.info(
        "etapa=indexacao concluida indexados=%d ja_existiam=%d segundos=%.0f",
        stats.indexed,
        stats.skipped,
        stats.seconds,
    )

    count = collection.count()
    if count != len(documents):
        raise RuntimeError(f"A coleção tem {count} documentos, mas a base tem {len(documents)}.")

    manifest = IndexManifest(
        embedding_model_id=settings.embedding_model_id,
        dimensions=settings.embedding_dimensions,
        distance=DISTANCE,
        created_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        document_count=count,
        chroma_version=chromadb.__version__,
        categories=sorted({doc.category for doc in documents} - {MIXED_CATEGORY, UNKNOWN}),
    )
    write_manifest(index_dir, manifest)
    check_manifest(manifest, settings, count)
    return manifest


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["prepare", "full"], default="full")
    parser.add_argument("--raw-dir", type=Path, default=RAW_DATA_DIR)
    parser.add_argument("--summary-path", type=Path, default=SUMMARY_PATH)
    args = parser.parse_args(argv)

    settings = get_settings()
    setup_logging(settings.log_level)

    documents = build_documents(load_tables(args.raw_dir))
    summary = summarize(documents)
    args.summary_path.parent.mkdir(parents=True, exist_ok=True)
    args.summary_path.write_text(json.dumps(summary, indent=2))
    logger.info("etapa=preparacao %s", " ".join(f"{k}={v}" for k, v in summary.items()))
    print(json.dumps(summary, indent=2))

    if args.mode == "full":
        client = get_runtime_client(settings)
        manifest = build_full_index(
            documents,
            settings,
            embed=lambda texts: embed_texts(client, texts, "search_document", settings),
            index_dir=Path(settings.index_dir),
        )
        print(json.dumps(manifest.__dict__, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
