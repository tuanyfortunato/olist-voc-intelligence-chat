"""Armazenamento dos embeddings em arquivos Parquet.

Durante a indexação, cada lote que volta do modelo vira uma parte em
work_dir/parts/. As partes são o ponto de retomada: se a execução parar no
meio, a próxima lê os review_id já gravados e continua dali. No fim, as partes
são juntadas em um único arquivo, que é carregado no PostgreSQL.
"""

from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq


class ParquetEmbeddingStore:
    def __init__(self, work_dir: Path):
        self.parts_dir = Path(work_dir) / "parts"
        self.parts_dir.mkdir(parents=True, exist_ok=True)

    def _parts(self) -> list[Path]:
        return sorted(self.parts_dir.glob("part-*.parquet"))

    def existing_ids(self) -> set[str]:
        ids = set()
        for part in self._parts():
            ids.update(pq.read_table(part, columns=["review_id"]).column("review_id").to_pylist())
        return ids

    def add(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict],
    ) -> None:
        """Grava um lote como uma parte nova. Mesma assinatura do add de uma coleção vetorial."""
        frame = pd.DataFrame(metadatas)
        frame["review_id"] = ids
        frame["embedding_text"] = documents
        # Ordem fixa das colunas: os metadados podem chegar com as chaves em
        # qualquer ordem, e partes com ordens diferentes não podem ser juntadas
        frame = frame[sorted(frame.columns)]
        table = pa.Table.from_pandas(frame, preserve_index=False).append_column(
            "embedding", pa.array(embeddings, type=pa.list_(pa.float32()))
        )
        number = len(self._parts())
        pq.write_table(table, self.parts_dir / f"part-{number:05d}.parquet")

    def write_final(self, path: Path) -> int:
        """Junta as partes num arquivo só, sem review_id repetido. Devolve o número de linhas."""
        table = pa.concat_tables(pq.read_table(part) for part in self._parts())
        frame = table.to_pandas().drop_duplicates("review_id", keep="last")
        final = pa.Table.from_pandas(frame, preserve_index=False).cast(table.schema)
        pq.write_table(final, path)
        return final.num_rows


def read_embeddings(path: Path) -> pd.DataFrame:
    return pq.read_table(path).to_pandas()
