// Testes da lógica da página, sem navegador: node --test "tests/frontend/*.test.mjs"
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  answerAsText,
  evidenceLine,
  similarityLabel,
  chipLabel,
  filterCategories,
  restrictionNotice,
  searchScopeText,
  toggleRating,
  RATING_SHORTCUTS,
  DELIVERY_OPTIONS,
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
import { CATEGORY_NAMES } from "../../frontend/categories.js";

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
  assert.equal(errorMessage(429, { detail: "Limite atingido." }).kind, "quota");
  assert.equal(errorMessage(422, { detail: [] }).kind, "invalid");
  assert.equal(errorMessage(503, { detail: "Tente de novo" }).kind, "retry");
  assert.equal(errorMessage(503, null).kind, "offline");
  assert.equal(errorMessage(502, null).kind, "offline");
  assert.equal(errorMessage(504, null).kind, "offline");
  assert.equal(errorMessage(0, null).kind, "offline");
  assert.equal(errorMessage(500, { detail: "x" }).kind, "unexpected");
});

test("errorMessage mostra a mensagem do limite que vem da API", () => {
  const detail = "Você chegou ao limite de 100 perguntas por hora.";
  assert.equal(errorMessage(429, { detail }).message, detail);
  assert.match(errorMessage(429, null).message, /limite de perguntas/);
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
  for (const kind of ["retry", "timeout", "offline", "unexpected"]) {
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
  assert.equal(categoryLabel("moveis_decoracao"), "Móveis e decoração");
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
    "notas 1 e 2 · Cama, mesa e banho · entregas com problema",
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

test("searchScopeText diz onde a busca está olhando", () => {
  assert.equal(searchScopeText(null), "Buscando em todas as avaliações");
  assert.equal(
    searchScopeText({ ratings: [1, 2], delivery: "com_problema" }),
    "Buscando só em avaliações com notas 1 e 2 e entregas com problema",
  );
  assert.equal(
    searchScopeText({ ratings: [1], category: "cama_mesa_banho", delivery: "atrasada" }),
    "Buscando só em avaliações com nota 1, Cama, mesa e banho e entregas atrasadas",
  );
});

test("chipLabel mostra o valor escolhido", () => {
  assert.equal(chipLabel("ratings", null), "Nota");
  assert.equal(chipLabel("category", {}), "Categoria");
  assert.equal(chipLabel("delivery", { ratings: [1] }), "Entrega");
  assert.equal(chipLabel("ratings", { ratings: [1, 2] }), "Nota: 1 e 2");
  assert.equal(chipLabel("category", { category: "cama_mesa_banho" }), "Categoria: Cama, mesa e banho");
  assert.equal(chipLabel("delivery", { delivery: "com_problema" }), "Entrega: com problema");
});

test("toggleRating inclui e retira sem mexer na lista original", () => {
  const original = [2];
  assert.deepEqual(toggleRating(original, 1), [1, 2]);
  assert.deepEqual(toggleRating([1, 2], 2), [1]);
  assert.deepEqual(original, [2]);
  assert.deepEqual(RATING_SHORTCUTS, { low: [1, 2], high: [4, 5] });
});

test("filterCategories ignora acentos, maiúsculas e sublinhados", () => {
  const options = [
    { value: "cama_mesa_banho", label: "Cama mesa banho" },
    { value: "moveis_decoracao", label: "Moveis decoracao" },
  ];
  assert.deepEqual(filterCategories(options, "MÓVEIS"), [options[1]]);
  assert.deepEqual(filterCategories(options, "mesa ba"), [options[0]]);
  assert.equal(filterCategories(options, "  ").length, 2);
  assert.deepEqual(filterCategories(options, "pix"), []);
});

test("restrictionNotice só aparece sem evidência e com filtros", () => {
  const filters = { ratings: [1], category: "cama_mesa_banho" };
  assert.equal(
    restrictionNotice("no_evidence", filters),
    "A busca estava restrita a nota 1 e Cama, mesa e banho",
  );
  assert.ok(restrictionNotice("weak_evidence", filters));
  assert.equal(restrictionNotice("answered", filters), null);
  assert.equal(restrictionNotice("no_evidence", null), null);
});

test("DELIVERY_OPTIONS tem as quatro situações com nome completo", () => {
  assert.deepEqual(
    DELIVERY_OPTIONS.map((option) => option.value),
    ["no_prazo", "atrasada", "nao_entregue", "com_problema"],
  );
  assert.equal(DELIVERY_OPTIONS[3].label, "Com problema (atraso ou não entregue)");
});

test("evidenceLine resume a evidência da resposta", () => {
  assert.equal(
    evidenceLine(10, 5),
    "Baseada em 10 avaliações citadas, de 15 recuperadas para esta pergunta. Não mede a frequência na base inteira.",
  );
  assert.ok(evidenceLine(1, 14).startsWith("Baseada em 1 avaliação citada, de 15 recuperadas"));
  assert.ok(evidenceLine(1, 0).startsWith("Baseada em 1 avaliação citada, de 1 recuperada para"));
  assert.ok(evidenceLine(0, 3).startsWith("Nenhuma das 3 avaliações recuperadas foi citada"));
  assert.equal(evidenceLine(0, 0), null);
});

test("similarityLabel troca o jargão por uma frase", () => {
  assert.equal(similarityLabel(0.7136), "Proximidade com a pergunta: 0,71");
});

test("categoryLabel usa o nome com acentos e cai na regra antiga fora da tabela", () => {
  assert.equal(categoryLabel("moveis_decoracao"), "Móveis e decoração");
  assert.equal(categoryLabel("cama_mesa_banho"), "Cama, mesa e banho");
  assert.equal(categoryLabel("categoria_nova"), "Categoria nova");
  assert.equal(Object.keys(CATEGORY_NAMES).length, 73);
  for (const [key, name] of Object.entries(CATEGORY_NAMES)) assert.ok(name.trim(), key);
});

test("filterCategories encontra pelo nome com acento e pelo nome original", () => {
  const options = [{ value: "moveis_decoracao", label: "Móveis e decoração" }];
  assert.equal(filterCategories(options, "moveis deco").length, 1);
  assert.equal(filterCategories(options, "decoração").length, 1);
});

test("answerAsText leva a resposta e as avaliações citadas", () => {
  const result = {
    answer: "Os clientes relatam atraso [1] e produto errado [2].\n- Sem resposta da loja [1]",
    cited: [
      { number: 1, rating: 1, review_id: "abc123", original_text: "Demorou um mês." },
      { number: 2, rating: 2, review_id: "def456", original_text: "Veio outro produto." },
    ],
    uncited: [{ number: 3, rating: 5, review_id: "ghi789", original_text: "Ótimo." }],
  };
  assert.equal(
    answerAsText(result),
    [
      "Os clientes relatam atraso [1] e produto errado [2].",
      "- Sem resposta da loja [1]",
      "",
      "Avaliações citadas:",
      "[1] nota 1, review_id abc123: Demorou um mês.",
      "[2] nota 2, review_id def456: Veio outro produto.",
    ].join("\n"),
  );
  assert.equal(answerAsText({ answer: "Olá!", cited: [], uncited: [] }), "Olá!");
});

import { activeFilterCount, errorLook, LOADING_STEPS } from "../../frontend/logic.js";

test("statusNotice troca a resposta pelo aviso só quando não há resposta", () => {
  assert.equal(statusNotice("no_evidence").replacesAnswer, true);
  assert.equal(statusNotice("out_of_scope").replacesAnswer, true);
  assert.equal(statusNotice("weak_evidence").replacesAnswer, false);
});

test("errorLook trata o limite como aviso e o resto como erro com título", () => {
  assert.equal(errorLook("quota").kind, "limit");
  assert.equal(errorLook("retry").kind, "error");
  assert.ok(errorLook("unexpected").title);
});

test("activeFilterCount conta os filtros escolhidos", () => {
  assert.equal(activeFilterCount(null), 0);
  assert.equal(activeFilterCount({ ratings: [1, 2] }), 1);
  assert.equal(activeFilterCount({ ratings: [5], category: "bebes", delivery: "atrasada" }), 3);
});

test("LOADING_STEPS mostra a busca antes da escrita", () => {
  assert.equal(LOADING_STEPS.length, 2);
  assert.match(LOADING_STEPS[0], /Buscando/);
});
