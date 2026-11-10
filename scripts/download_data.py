"""Baixa a base da Olist para a pasta data/raw.

Uso, a partir da raiz do projeto:
    python -m scripts.download_data
"""

from src.knowledge_base.download import download_dataset


def main() -> None:
    files = download_dataset()
    print(f"\nPronto. {len(files)} arquivos disponíveis em data/raw.")


if __name__ == "__main__":
    main()
