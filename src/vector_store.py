"""Coleção do Chroma e manifesto do índice.

O índice é gerado no workflow de indexação e lido pela API em outro lugar.
O manifesto, gravado ao lado dele, registra como o índice foi feito; a API
confere esses dados ao iniciar, porque um índice feito com outro modelo ou
outra versão do Chroma daria resultados sem sentido.
"""

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import chromadb

from src.config import Settings

DISTANCE = "cosine"
MANIFEST_FILE = "manifest.json"


class IndexMismatchError(Exception):
    """O índice não corresponde à configuração da aplicação."""


@dataclass(frozen=True)
class IndexManifest:
    embedding_model_id: str
    dimensions: int
    distance: str
    created_at: str
    document_count: int
    chroma_version: str
    categories: list[str]


def open_collection(index_dir: Path, name: str, create: bool = False):
    """Abre a coleção gravada em index_dir. Com create=True, cria se não existir."""
    client = chromadb.PersistentClient(path=str(index_dir))
    if create:
        return client.get_or_create_collection(
            name, metadata={"hnsw:space": DISTANCE}, embedding_function=None
        )
    return client.get_collection(name, embedding_function=None)


def distance_to_similarity(distance: float) -> float:
    """O Chroma devolve a distância de cosseno; a similaridade é o complemento."""
    return 1 - distance


def write_manifest(index_dir: Path, manifest: IndexManifest) -> None:
    path = Path(index_dir) / MANIFEST_FILE
    path.write_text(json.dumps(asdict(manifest), ensure_ascii=False, indent=2))


def read_manifest(index_dir: Path) -> IndexManifest:
    path = Path(index_dir) / MANIFEST_FILE
    return IndexManifest(**json.loads(path.read_text()))


def _major_minor(version: str) -> str:
    return ".".join(version.split(".")[:2])


def check_manifest(manifest: IndexManifest, settings: Settings, collection_count: int) -> None:
    """Levanta IndexMismatchError explicando o que diverge entre o índice e a configuração."""
    problems = []
    if manifest.embedding_model_id != settings.embedding_model_id:
        problems.append(
            f"modelo do índice {manifest.embedding_model_id}, "
            f"configurado {settings.embedding_model_id}"
        )
    if manifest.dimensions != settings.embedding_dimensions:
        problems.append(
            f"dimensões do índice {manifest.dimensions}, "
            f"configuradas {settings.embedding_dimensions}"
        )
    if manifest.distance != DISTANCE:
        problems.append(f"distância do índice {manifest.distance}, esperada {DISTANCE}")
    if _major_minor(manifest.chroma_version) != _major_minor(chromadb.__version__):
        problems.append(
            f"versão do Chroma do índice {manifest.chroma_version}, "
            f"instalada {chromadb.__version__}"
        )
    if manifest.document_count != collection_count:
        problems.append(
            f"documentos no manifesto {manifest.document_count}, na coleção {collection_count}"
        )
    if problems:
        raise IndexMismatchError("O índice não corresponde à configuração: " + "; ".join(problems))
