// Testes da lógica da página, sem navegador: node --test "tests/frontend/*.test.mjs"
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  buildFilters,
  canRetry,
  currentTheme,
  categoryLabel,
  counterState,
  deliveryLabel,
  describeFilters,
  errorMessage,
  formatDate,
  formatSimilarity,
  nextTheme,
  parseAnswerBlocks,
  pickSuggestions,
  remainingSuggestions,
  shortId,
  splitCitations,
  statusNotice,
  SUGGESTIONS,
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

test("currentTheme usa a escolha salva e, sem ela, o tema do sistema", () => {
  assert.equal(currentTheme("dark", false), "dark");
  assert.equal(currentTheme("light", true), "light");
  assert.equal(currentTheme(null, true), "dark");
  assert.equal(currentTheme("qualquer", false), "light");
});

test("nextTheme alterna entre claro e escuro", () => {
  assert.equal(nextTheme("light"), "dark");
  assert.equal(nextTheme("dark"), "light");
});

test("pickSuggestions sorteia perguntas sem repetir as já usadas", () => {
  const pool = ["Pergunta A?", "Pergunta B?", "Pergunta C?", "Pergunta D?", "Pergunta E?"];
  const used = ["Pergunta A?", "  pergunta c?  "];
  // Com o sorteio fixo em zero, a escolha é previsível
  assert.deepEqual(pickSuggestions(pool, used, 2, () => 0), ["Pergunta B?", "Pergunta D?"]);
  for (let i = 0; i < 50; i += 1) {
    const picked = pickSuggestions(pool, used, 3);
    assert.equal(picked.length, 3);
    assert.equal(new Set(picked).size, 3);
    for (const question of picked) assert.ok(!["Pergunta A?", "Pergunta C?"].includes(question));
  }
  assert.deepEqual(pickSuggestions(pool, pool, 3), []);
  assert.equal(pickSuggestions(pool, used, 10).length, 3);
});

test("remainingSuggestions conta as perguntas que ainda podem ser sugeridas", () => {
  const pool = ["Pergunta A?", "Pergunta B?", "Pergunta C?"];
  assert.equal(remainingSuggestions(pool, ["pergunta a?"]), 2);
  assert.equal(remainingSuggestions(pool, pool), 0);
});

test("SUGGESTIONS tem perguntas distintas e dentro do limite de caracteres", () => {
  assert.ok(SUGGESTIONS.length >= 20);
  assert.equal(new Set(SUGGESTIONS.map((q) => q.toLowerCase())).size, SUGGESTIONS.length);
  for (const question of SUGGESTIONS) {
    assert.ok(question.length <= 500 && question.endsWith("?"), question);
  }
});
