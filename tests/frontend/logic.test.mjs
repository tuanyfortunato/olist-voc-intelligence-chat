// Testes da lógica da página, sem navegador: node --test "tests/frontend/*.test.mjs"
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  errorMessage,
  formatSimilarity,
  parseAnswerBlocks,
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
