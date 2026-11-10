"""Download da base de avaliações da Olist pela API do Kaggle.

A base completa tem nove tabelas. Baixamos apenas as cinco que o projeto usa:
avaliações (texto e nota), pedidos (datas de entrega), itens do pedido (ligação
com o produto), produtos (categoria) e a tradução das categorias.

A autenticação usa o token salvo em ~/.kaggle/access_token.
"""

from pathlib import Path

from kaggle.api.kaggle_api_extended import KaggleApi

DATASET = "olistbr/brazilian-ecommerce"

REQUIRED_FILES = [
    "olist_order_reviews_dataset.csv",
    "olist_orders_dataset.csv",
    "olist_order_items_dataset.csv",
    "olist_products_dataset.csv",
    "product_category_name_translation.csv",
]

RAW_DATA_DIR = Path("data/raw")


def download_dataset(destination: Path = RAW_DATA_DIR) -> list[Path]:
    """Baixa os arquivos necessários e devolve o caminho de cada um.

    Arquivos que já existem na pasta não são baixados de novo.
    """
    destination.mkdir(parents=True, exist_ok=True)

    api = KaggleApi()
    api.authenticate()

    downloaded = []
    for file_name in REQUIRED_FILES:
        file_path = destination / file_name
        if file_path.exists():
            print(f"Já existe, pulando: {file_path}")
        else:
            print(f"Baixando: {file_name}")
            api.dataset_download_file(DATASET, file_name, path=destination, unzip=True)
        downloaded.append(file_path)

    return downloaded
