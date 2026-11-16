// Testes da lógica da página, sem navegador: node --test "tests/frontend/*.test.mjs"
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  canRetry,
  categoryLabel,
  counterState,
  deliveryLabel,
  errorMessage,
  formatDate,
  formatSimilarity,
  parseAnswerBlocks,
  shortId,
  splitCitations,
  statusNotice,
} from "../../frontend/logic.js";

test("splitCitations separa texto e citações", () => {
  assert.deepEqual(splitCitations("Atrasos [1][4] e defeitos [2, 5]."), [
    { type: "text", value: "Atrasos " },
    { type: "cite", numbers: [1] },
    { type: "cite", numbers: [4] },
    { type: "text", value: " e defeitos " },
    { type: "cite", numbers: [2, 5] },
    { type: "text", value: "." },
  ]);
});

test("splitCitations mantém colchetes com texto como texto", () => {
  assert.deepEqual(splitCitations("A loja [Lannister] demorou"), [
    { type: "text", value: "A loja [Lannister] demorou" },
  ]);
});

test("parseAnswerBlocks junta as linhas com hífen numa lista", () => {
  const answer = "Entre as avaliações:\n- Atrasos [1]\n- Defeitos [2]\n\nObservação: final.";
  assert.deepEqual(parseAnswerBlocks(answer), [
    { type: "paragraph", text: "Entre as avaliações:" },
    { type: "list", items: ["Atrasos [1]", "Defeitos [2]"] },
    { type: "paragraph", text: "Observação: final." },
  ]);
});

test("statusNotice só avisa nas situações sem resposta completa", () => {
  assert.equal(statusNotice("answered"), null);
  assert.equal(statusNotice("greeting"), null);
  assert.equal(statusNotice("no_evidence").kind, "no_evidence");
  assert.equal(statusNotice("weak_evidence").kind, "weak_evidence");
  assert.equal(statusNotice("out_of_scope").kind, "out_of_scope");
});

test("errorMessage escolhe a mensagem pelo tipo de erro", () => {
  assert.equal(errorMessage(401, null).kind, "key");
  assert.equal(errorMessage(429, { detail: "Limite diário de perguntas atingido." }).kind, "quota");
  assert.equal(errorMessage(422, { detail: [] }).kind, "invalid");
  assert.equal(errorMessage(503, { detail: "Tente de novo" }).kind, "retry");
  assert.equal(errorMessage(503, null).kind, "offline");
  assert.equal(errorMessage(502, null).kind, "offline");
  assert.equal(errorMessage(504, null).kind, "offline");
  assert.equal(errorMessage(0, null).kind, "offline");
  assert.equal(errorMessage(500, { detail: "x" }).kind, "unexpected");
});

test("formatSimilarity usa vírgula e duas casas", () => {
  assert.equal(formatSimilarity(0.7136), "0,71");
});

test("parseAnswerBlocks mostra um item solto como parágrafo", () => {
  assert.deepEqual(parseAnswerBlocks("- Entre as avaliações, atrasos [1]."), [
    { type: "paragraph", text: "Entre as avaliações, atrasos [1]." },
  ]);
});

test("errorMessage trata o tempo limite como erro passageiro", () => {
  assert.equal(errorMessage(-1, null).kind, "timeout");
});

test("canRetry só oferece nova tentativa quando ela pode dar certo", () => {
  for (const kind of ["retry", "timeout", "offline", "unexpected", "key"]) {
    assert.equal(canRetry(kind), true, kind);
  }
  assert.equal(canRetry("quota"), false);
  assert.equal(canRetry("invalid"), false);
});

test("deliveryLabel descreve a entrega e omite a desconhecida", () => {
  assert.deepEqual(deliveryLabel("no_prazo"), { text: "Entregue no prazo", tone: "ok" });
  assert.deepEqual(deliveryLabel("atrasada"), { text: "Entregue com atraso", tone: "warn" });
  assert.deepEqual(deliveryLabel("nao_entregue"), { text: "Não entregue", tone: "bad" });
  assert.equal(deliveryLabel("desconhecido"), null);
  assert.equal(deliveryLabel(undefined), null);
});

test("categoryLabel deixa a categoria legível", () => {
  assert.equal(categoryLabel("moveis_decoracao"), "Moveis decoracao");
  assert.equal(categoryLabel("mista"), "Várias categorias");
  assert.equal(categoryLabel("desconhecido"), null);
  assert.equal(categoryLabel(""), null);
});

test("formatDate usa o formato brasileiro", () => {
  assert.equal(formatDate("2018-03-10"), "10/03/2018");
  assert.equal(formatDate("2018-03-10 00:00:00"), "10/03/2018");
  assert.equal(formatDate("desconhecido"), null);
});

test("shortId abrevia o identificador da avaliação", () => {
  assert.equal(shortId("f242ce44a1b2c3d4e5f6a7b8c9d0e1f2"), "f242ce44");
});

test("counterState avisa perto do limite de caracteres", () => {
  assert.equal(counterState(10), "ok");
  assert.equal(counterState(450), "near");
  assert.equal(counterState(500), "full");
});

import { buildFilters, describeFilters } from "../../frontend/logic.js";

test("buildFilters devolve null sem nenhum filtro escolhido", () => {
  assert.equal(buildFilters({ ratings: [], category: "", delivery: "" }), null);
});

test("buildFilters monta só os campos escolhidos", () => {
  assert.deepEqual(buildFilters({ ratings: [2, 1], category: "", delivery: "com_problema" }), {
    ratings: [1, 2],
    delivery: "com_problema",
  });
  assert.deepEqual(buildFilters({ ratings: [], category: "cama_mesa_banho", delivery: "" }), {
    category: "cama_mesa_banho",
  });
});

test("describeFilters resume os filtros em português", () => {
  assert.equal(describeFilters(null), "");
  assert.equal(
    describeFilters({ ratings: [1, 2], category: "cama_mesa_banho", delivery: "com_problema" }),
    "notas 1 e 2 · Cama mesa banho · entregas com problema",
  );
  assert.equal(describeFilters({ ratings: [5] }), "nota 5");
  assert.equal(describeFilters({ delivery: "atrasada" }), "entregas atrasadas");
});

import { buildHistory, describeInferredRatings } from "../../frontend/logic.js";

test("buildHistory manda as 3 últimas trocas, com respostas cortadas", () => {
  const turns = [1, 2, 3, 4].map((n) => ({ question: `P${n}`, answer: `R${n}` }));
  assert.deepEqual(buildHistory(turns), [
    { question: "P2", answer: "R2" },
    { question: "P3", answer: "R3" },
    { question: "P4", answer: "R4" },
  ]);
  const long = buildHistory([{ question: "P", answer: "x".repeat(2000) }]);
  assert.equal(long[0].answer.length, 1500);
  assert.deepEqual(buildHistory([]), []);
});

test("describeInferredRatings explica a nota tirada da pergunta", () => {
  assert.equal(describeInferredRatings([]), null);
  assert.equal(
    describeInferredRatings([4, 5]),
    "A busca considerou só as avaliações de notas 4 e 5, citadas na pergunta.",
  );
});
