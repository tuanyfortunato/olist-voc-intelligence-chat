"""Manifesto do índice e conversão da distância em similaridade.

Os embeddings são gerados num lugar e buscados em outro. O manifesto, gravado
junto com eles, registra como foram feitos; a API confere esses dados ao
iniciar, porque vetores feitos com outro modelo ou outro tamanho dariam
resultados sem sentido.
"""

import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path

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
    categories: list[str]

    @classmethod
    def from_dict(cls, data: dict) -> "IndexManifest":
        known = {field.name for field in fields(cls)}
        return cls(**{key: value for key, value in data.items() if key in known})


def distance_to_similarity(distance: float) -> float:
    """A busca devolve a distância de cosseno; a similaridade é o complemento."""
    return 1 - distance


def write_manifest(index_dir: Path, manifest: IndexManifest) -> None:
    path = Path(index_dir) / MANIFEST_FILE
    path.write_text(json.dumps(asdict(manifest), ensure_ascii=False, indent=2))


def read_manifest(index_dir: Path) -> IndexManifest:
    path = Path(index_dir) / MANIFEST_FILE
    return IndexManifest.from_dict(json.loads(path.read_text()))


def check_manifest(manifest: IndexManifest, settings: Settings, row_count: int) -> None:
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
    if manifest.document_count != row_count:
        problems.append(f"documentos no manifesto {manifest.document_count}, no banco {row_count}")
    if problems:
        raise IndexMismatchError("O índice não corresponde à configuração: " + "; ".join(problems))
