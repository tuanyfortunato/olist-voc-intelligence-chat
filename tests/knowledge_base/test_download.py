from src.knowledge_base import download


class FakeKaggleApi:
    """Substitui a API do Kaggle e registra os arquivos pedidos, sem usar a rede."""

    def __init__(self):
        self.downloaded = []

    def authenticate(self):
        pass

    def dataset_download_file(self, dataset, file_name, path, unzip):
        self.downloaded.append(file_name)
        (path / file_name).write_text("conteúdo baixado")


def test_download_skips_existing_files(tmp_path, monkeypatch):
    fake = FakeKaggleApi()
    monkeypatch.setattr(download, "KaggleApi", lambda: fake)
    (tmp_path / "olist_orders_dataset.csv").write_text("já existe")

    paths = download.download_dataset(tmp_path)

    assert len(paths) == 5
    assert "olist_orders_dataset.csv" not in fake.downloaded
    assert len(fake.downloaded) == 4
