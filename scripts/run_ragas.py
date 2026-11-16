"""Notas do RAGAS para as respostas da avaliação.

Lê o CSV que o run_evaluation grava e calcula três métricas que não precisam de
resposta de referência: faithfulness (cada afirmação da resposta está nos
comentários recuperados?), answer relevancy (a resposta trata da pergunta?) e
context precision sem referência (os comentários úteis vêm nas primeiras
posições?). O juiz é o Nova Pro, e não o Nova Micro que escreve a resposta,
para o modelo não avaliar a si mesmo.

As respostas fixas e as recusas (fora do escopo, saudação, sem evidência) não
passam pelo RAGAS, que daria nota baixa justamente ao comportamento certo.
Para elas, e para todas as outras linhas, há uma checagem por regra: a situação
retornada é a esperada para o tipo da pergunta?

Roda no runner do GitHub Actions, sem o banco, só com acesso ao Bedrock:
    python -m scripts.run_ragas avaliacao/avaliacao.csv --out-dir avaliacao
"""

import argparse
import csv
import json
import logging
import re
from pathlib import Path
from statistics import mean

from src.rag.prompts import PREMISE_NOTE

logger = logging.getLogger(__name__)

JUDGE_MODEL_ID = "amazon.nova-pro-v1:0"
EMBEDDING_MODEL_ID = "cohere.embed-multilingual-v3"
# Preço do Nova Pro em us-east-1, em dólares por token, para estimar o custo no log
JUDGE_PRICE_INPUT = 0.80 / 1_000_000
JUDGE_PRICE_OUTPUT = 3.20 / 1_000_000

METRICS = ["faithfulness", "answer_relevancy", "context_precision"]

# Situações que o RAGAS pontua: as respostas escritas pelo modelo a partir dos comentários
SCORED_STATUSES = {"answered", "weak_evidence"}
ANSWERED = {"answered", "weak_evidence"}

# Situação esperada para cada tipo de pergunta. A mudança de regra pode tanto
# responder normalmente quanto recusar, então fica só para a revisão manual.
EXPECTED_STATUS = {
    "with_evidence": ANSWERED,
    "with_filter": ANSWERED,
    "false_premise": ANSWERED,
    "weak_evidence": {"weak_evidence"},
    "no_evidence": {"no_evidence"},
    "out_of_scope": {"out_of_scope"},
}

CITATION = re.compile(r"\s*\[\d+\]")


def expected_statuses(question_type: str, turn: int) -> set[str] | None:
    if question_type == "greeting_follow_up":
        return {"greeting"} if turn == 1 else ANSWERED
    return EXPECTED_STATUS.get(question_type)


def status_check(row: dict) -> str:
    """sim ou não quando há uma situação esperada; vazio quando não se aplica."""
    expected = expected_statuses(row["type"], int(row["turn"]))
    if expected is None:
        return ""
    return "sim" if row["status"] in expected else "não"


def clean_answer(answer: str) -> str:
    """Tira os marcadores [1][5] e a observação fixa sobre premissas.

    A observação é um texto do sistema, e não uma afirmação tirada dos
    comentários, então contaria como afirmação sem apoio na faithfulness.
    """
    answer = answer.replace(PREMISE_NOTE, "")
    return CITATION.sub("", answer).strip()


def ragas_sample(row: dict) -> dict | None:
    """Amostra no formato do RAGAS, ou None quando a linha não deve ser pontuada.

    Os comentários vão na ordem em que foram ao modelo, que é a ordem da busca
    e importa para a context precision.
    """
    if row["status"] not in SCORED_STATUSES:
        return None
    retrieved = sorted(json.loads(row["retrieved_json"] or "[]"), key=lambda r: r["number"])
    if not retrieved:
        return None
    return {
        "user_input": row["question"],
        "response": clean_answer(row["answer"]),
        "retrieved_contexts": [review["original_text"] for review in retrieved],
    }


def read_rows(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8-sig") as file:
        return list(csv.DictReader(file))


def score_samples(samples: list[dict]) -> list[dict]:
    """Chama o RAGAS com o Nova Pro e o Cohere. Devolve as notas na ordem das amostras.

    Os imports ficam aqui dentro porque o RAGAS só é instalado no workflow de
    avaliação, e não na imagem da API nem no CI.
    """
    from langchain_aws import BedrockEmbeddings, ChatBedrockConverse
    from ragas import EvaluationDataset, evaluate
    from ragas.cost import TokenUsage
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.llms import LangchainLLMWrapper
    from ragas.metrics import (
        Faithfulness,
        LLMContextPrecisionWithoutReference,
        ResponseRelevancy,
    )
    from ragas.run_config import RunConfig

    def bedrock_usage(llm_result) -> TokenUsage:
        usage = TokenUsage(input_tokens=0, output_tokens=0, model=JUDGE_MODEL_ID)
        for generations in llm_result.generations:
            for generation in generations:
                metadata = getattr(getattr(generation, "message", None), "usage_metadata", None)
                if metadata:
                    usage += TokenUsage(
                        input_tokens=metadata.get("input_tokens", 0),
                        output_tokens=metadata.get("output_tokens", 0),
                        model=JUDGE_MODEL_ID,
                    )
        return usage

    judge = LangchainLLMWrapper(
        ChatBedrockConverse(
            model=JUDGE_MODEL_ID, region_name="us-east-1", temperature=0, max_tokens=4096
        )
    )
    embeddings = LangchainEmbeddingsWrapper(
        BedrockEmbeddings(model_id=EMBEDDING_MODEL_ID, region_name="us-east-1")
    )
    metrics = [
        Faithfulness(),
        ResponseRelevancy(),
        LLMContextPrecisionWithoutReference(name="context_precision"),
    ]
    # Poucas chamadas em paralelo, para não bater na cota do Bedrock
    run_config = RunConfig(max_workers=4, timeout=300, max_retries=10, max_wait=60)
    result = evaluate(
        EvaluationDataset.from_list(samples),
        metrics=metrics,
        llm=judge,
        embeddings=embeddings,
        run_config=run_config,
        token_usage_parser=bedrock_usage,
        show_progress=False,
    )
    # Sem nenhuma chamada bem-sucedida ao juiz, o RAGAS não tem uso para somar
    try:
        usage = result.total_tokens()
    except IndexError:
        usage = TokenUsage(input_tokens=0, output_tokens=0, model=JUDGE_MODEL_ID)
    cost = usage.cost(JUDGE_PRICE_INPUT, JUDGE_PRICE_OUTPUT)
    logger.info(
        "etapa=ragas amostras=%d tokens_entrada=%d tokens_saida=%d custo_estimado_usd=%.2f",
        len(samples),
        usage.input_tokens,
        usage.output_tokens,
        cost,
    )
    return result.to_pandas()[METRICS].to_dict("records")


def _round(value) -> str:
    # O RAGAS devolve NaN quando uma métrica falha para a amostra
    if value is None or value != value:
        return ""
    return f"{value:.3f}"


def ragas_rows(rows: list[dict], scorer=score_samples) -> list[dict]:
    """Uma linha por linha da avaliação, com as notas e a checagem por regra."""
    samples = [ragas_sample(row) for row in rows]
    to_score = [sample for sample in samples if sample is not None]
    scores = iter(scorer(to_score) if to_score else [])
    output = []
    for row, sample in zip(rows, samples, strict=True):
        line = {
            "question_id": row["question_id"],
            "turn": row["turn"],
            "question": row["question"],
            "filters": row["filters"],
            "type": row["type"],
            "status": row["status"],
            "situacao_esperada": status_check(row),
            "avaliada_ragas": "sim" if sample else "não",
        }
        score = next(scores) if sample else {}
        line.update({metric: _round(score.get(metric)) for metric in METRICS})
        output.append(line)
    return output


def summary_rows(rows: list[dict]) -> list[dict]:
    """Média das notas por tipo de pergunta e no total."""
    groups: dict[str, list[dict]] = {}
    for row in rows:
        groups.setdefault(row["type"], []).append(row)
    groups["total"] = rows
    summary = []
    for group, items in groups.items():
        checked = [item for item in items if item["situacao_esperada"]]
        line = {
            "tipo": group,
            "linhas": len(items),
            "avaliadas_ragas": sum(item["avaliada_ragas"] == "sim" for item in items),
            "situacao_esperada": (
                f"{sum(item['situacao_esperada'] == 'sim' for item in checked)} de {len(checked)}"
                if checked
                else ""
            ),
        }
        for metric in METRICS:
            values = [float(item[metric]) for item in items if item[metric]]
            line[metric] = f"{mean(values):.3f}" if values else ""
        summary.append(line)
    return summary


def write_csv(path: Path, rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path, help="CSV gravado pelo run_evaluation")
    parser.add_argument("--out-dir", type=Path, default=Path("."))
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

    rows = ragas_rows(read_rows(args.csv))
    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.out_dir / "ragas.csv", rows)
    write_csv(args.out_dir / "ragas_resumo.csv", summary_rows(rows))


if __name__ == "__main__":
    main()
