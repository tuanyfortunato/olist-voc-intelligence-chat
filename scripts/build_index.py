"""Prepara a base de conhecimento e gera o índice do Chroma.

Uso, a partir da raiz do projeto:
    python -m scripts.build_index --mode prepare   # só prepara e mostra os números
    python -m scripts.build_index --mode full      # prepara e indexa (etapa 4)
"""

import argparse
import json
import logging
from pathlib import Path

from src.config import get_settings
from src.knowledge_base.download import RAW_DATA_DIR
from src.knowledge_base.preparation import build_documents, load_tables, summarize
from src.logging_config import setup_logging

logger = logging.getLogger(__name__)

SUMMARY_PATH = Path("data/prepare_summary.json")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["prepare", "full"], default="full")
    parser.add_argument("--raw-dir", type=Path, default=RAW_DATA_DIR)
    parser.add_argument("--summary-path", type=Path, default=SUMMARY_PATH)
    args = parser.parse_args(argv)

    setup_logging(get_settings().log_level)

    documents = build_documents(load_tables(args.raw_dir))
    summary = summarize(documents)
    args.summary_path.parent.mkdir(parents=True, exist_ok=True)
    args.summary_path.write_text(json.dumps(summary, indent=2))
    logger.info("etapa=preparacao %s", " ".join(f"{k}={v}" for k, v in summary.items()))
    print(json.dumps(summary, indent=2))

    if args.mode == "full":
        raise SystemExit("O modo full entra na etapa de indexação.")


if __name__ == "__main__":
    main()
