// Testes da lógica do painel por setor: node --test "tests/frontend/*.test.mjs"
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";

import {
  DEMO_EMAIL,
  DIRECTOR,
  displayName,
  formatPercent,
  formatRating,
  initials,
  isPreview,
  monthLabel,
  monthlySeries,
  parseSession,
  scopeLabel,
  scopeLine,
  scopeThemes,
  sectorKpis,
  sectorList,
  themeGroups,
  themeQuestion,
  themeRows,
} from "../../frontend/painel.js";

function period(overrides = {}) {
  return {
    label: "Todo o período",
    total: 1000,
    avg_rating: 3.7,
    ratings: { 1: 200, 2: 50, 3: 100, 4: 150, 5: 500 },
    delivery: {
      no_prazo: { count: 850, avg_rating: 4.0 },
      atrasada: { count: 100, avg_rating: 2.0 },
      nao_entregue: { count: 50, avg_rating: 1.5 },
    },
    themes: {
      atraso: { count: 120, avg_rating: 2.1, low: 80 },
      avaria: { count: 30, avg_rating: 2.5, low: 15 },
      defeito: { count: 60, avg_rating: 1.9, low: 50 },
      entrega_rapida: { count: 300, avg_rating: 4.8, low: 2 },
      recompra: { count: 20, avg_rating: 4.6, low: 0 },
    },
    sectors: {
      logistica: { count: 140, avg_rating: 2.2, low: 90 },
      produto: { count: 60, avg_rating: 1.9, low: 50 },
      retencao: { count: 20, avg_rating: 4.6, low: 0 },
      fortes: { count: 300, avg_rating: 4.8, low: 2 },
    },
    monthly: [
      { month: "2017-01", total: 50, low: 40, high: 5, late: 30 },
      { month: "2017-02", total: 300, low: 60, high: 200, late: 30 },
      { month: "2017-03", total: 300, low: 90, high: 180, late: 90 },
      { month: "2017-04", total: 300, low: 80, high: 190, late: 80 },
      { month: "2017-05", total: 300, low: 30, high: 250, late: 15 },
      { month: "2017-06", total: 300, low: 75, high: 200, late: 60 },
    ],
    ...overrides,
  };
}

const DATA = {
  model_id: "amazon.nova-micro-v1:0",
  generated_at: "2026-11-16T22:00:00+00:00",
  sectors: [
    { id: "logistica", label: "Logística", summary: "Entrega", themes: ["atraso", "avaria"] },
    { id: "produto", label: "Produto e anúncio", summary: "Produto", themes: ["defeito"] },
    { id: "retencao", label: "Retenção e reputação", summary: "Volta", themes: ["recompra"] },
    { id: "fortes", label: "Pontos fortes", summary: "Elogios", themes: ["entrega_rapida"] },
  ],
  themes: [
    { id: "atraso", label: "Atraso na entrega", sector: "logistica", polarity: "reclamacao" },
    { id: "avaria", label: "Chegou danificado", sector: "logistica", polarity: "reclamacao" },
    { id: "defeito", label: "Defeito", sector: "produto", polarity: "reclamacao" },
    { id: "recompra", label: "Volta a comprar", sector: "retencao", polarity: "elogio" },
    { id: "entrega_rapida", label: "Entrega rápida", sector: "fortes", polarity: "elogio" },
  ],
  periods: { todos: period() },
  examples: {},
};

test("a diretoria geral vem antes dos setores", () => {
  assert.deepEqual(
    sectorList(DATA).map((sector) => sector.id),
    [DIRECTOR, "logistica", "produto", "retencao", "fortes"],
  );
});

test("números no formato brasileiro", () => {
  assert.equal(formatPercent(104, 1000), "10,4%");
  assert.equal(formatPercent(1, 0), "0%");
  assert.equal(formatRating(3.6), "3,60");
  assert.equal(formatRating(null), "sem nota");
  assert.equal(monthLabel("2018-03"), "mar/18");
});

test("nome e iniciais a partir do e-mail do login de demonstração", () => {
  assert.equal(displayName(DEMO_EMAIL), "Gestor demo");
  assert.equal(displayName("ana.souza@empresa.com"), "Ana Souza");
  assert.equal(displayName(""), "Gestor demo");
  assert.equal(initials("Ana Souza Lima"), "AS");
});

test("a sessão salva só vale com e-mail, e um setor desconhecido é ignorado", () => {
  assert.deepEqual(parseSession('{"email":"a@b.com","sector":"logistica"}', DATA), {
    email: "a@b.com",
    name: "A",
    sector: "logistica",
  });
  assert.equal(parseSession('{"email":"a@b.com","sector":"marketing"}', DATA).sector, null);
  assert.equal(parseSession("{}", DATA), null);
  assert.equal(parseSession("não é json", DATA), null);
  assert.equal(parseSession(null, DATA), null);
});

test("temas do setor do mais citado para o menos citado, com a fatia da base", () => {
  const rows = themeRows(DATA, "todos", "logistica");
  assert.deepEqual(rows.map((row) => row.id), ["atraso", "avaria"]);
  assert.equal(rows[0].share, 0.12);
  assert.equal(rows[0].sectorLabel, "Logística");
});

test("a diretoria vê reclamações e elogios de todos os setores", () => {
  const groups = themeGroups(DATA, "todos", DIRECTOR);
  assert.deepEqual(groups.complaints.map((row) => row.id), ["atraso", "defeito", "avaria"]);
  assert.deepEqual(groups.praises.map((row) => row.id), ["entrega_rapida", "recompra"]);
  const retention = themeGroups(DATA, "todos", "retencao");
  assert.deepEqual(retention.complaints, []);
  assert.deepEqual(retention.praises.map((row) => row.id), ["recompra"]);
});

test("indicadores da diretoria e da logística", () => {
  const director = sectorKpis(DATA, "todos", DIRECTOR);
  assert.deepEqual(
    director.map((kpi) => kpi.value),
    ["1.000", "3,70", "25,0%", "15,0%"],
  );
  // Nota média de atrasadas e não entregues juntas, ponderada pela quantidade
  assert.equal(director[3].note, "nota média 1,83");
  const logistics = sectorKpis(DATA, "todos", "logistica");
  assert.deepEqual(
    logistics.map((kpi) => kpi.value),
    ["10,0%", "5,0%", "2,00", "mar/17"],
  );
  // Janeiro tem poucas avaliações e não conta como pior mês
  assert.equal(logistics[3].note, "30,0% fora do prazo");
});

test("indicadores dos demais setores usam a contagem do setor e os temas mais citados", () => {
  const product = sectorKpis(DATA, "todos", "produto");
  assert.equal(product[0].value, "60");
  assert.equal(product[0].note, "6,0% das avaliações");
  assert.equal(product[2].label, "Defeito");
  assert.equal(sectorKpis(DATA, "todos", "fortes")[0].label, "Avaliações com elogio");
});

test("série mensal sem os meses pequenos e com destaques separados", () => {
  const late = monthlySeries(DATA, "todos", "logistica");
  assert.equal(late.kind, "late");
  assert.deepEqual(late.points.map((p) => p.month), ["2017-02", "2017-03", "2017-04", "2017-05", "2017-06"]);
  assert.equal(late.points[1].value, 30);
  // Março é o maior; abril, colado nele, dá lugar a junho
  assert.deepEqual(late.peaks, [1, 4]);
  assert.equal(monthlySeries(DATA, "todos", "fortes").kind, "high");
  assert.equal(monthlySeries(DATA, "todos", DIRECTOR).kind, "low");
});

test("recorte do chat: tema clicado, temas do setor ou a base inteira", () => {
  assert.deepEqual(scopeThemes(DATA, "logistica", null), ["atraso", "avaria"]);
  assert.deepEqual(scopeThemes(DATA, "logistica", "avaria"), ["avaria"]);
  assert.equal(scopeThemes(DATA, DIRECTOR, null), null);
  assert.equal(scopeLabel(DATA, "logistica", "avaria"), 'do tema "Chegou danificado"');
  assert.equal(scopeLabel(DATA, "logistica", null), "do setor Logística");
  assert.equal(scopeLabel(DATA, DIRECTOR, null), "da base inteira");
});

test("frase do recorte junto da resposta", () => {
  assert.equal(
    scopeLine(3300, 'do tema "Produto não recebido"', 15),
    '3.300 avaliações do tema "Produto não recebido" · 15 usadas na resposta',
  );
  assert.equal(scopeLine(1, "da base inteira", 0), "1 avaliação da base inteira");
  assert.equal(scopeLine(null, "x", 3), null);
});

test("cada tema tem pergunta própria, e os desconhecidos uma genérica", () => {
  assert.match(themeQuestion({ id: "atraso", label: "Atraso na entrega" }), /atrasos/);
  assert.equal(themeQuestion({ id: "novo", label: "Frete caro" }), "O que os clientes comentam sobre frete caro?");
});

test("o dashboard.json publicado tem os setores e os temas da classificação", async () => {
  const raw = await readFile(new URL("../../frontend/dashboard.json", import.meta.url), "utf8");
  const data = JSON.parse(raw);
  const themeIds = new Set(data.themes.map((theme) => theme.id));
  for (const sector of data.sectors) {
    for (const id of sector.themes) assert.ok(themeIds.has(id), id);
  }
  for (const key of ["todos", "2018", "2017"]) assert.ok(data.periods[key].total > 0, key);
  assert.equal(typeof isPreview(data), "boolean");
  // Cada tema do painel tem uma pergunta sugerida escrita à mão
  for (const theme of data.themes) {
    const generic = `O que os clientes comentam sobre ${theme.label.toLowerCase()}?`;
    assert.notEqual(themeQuestion(theme), generic, theme.id);
  }
});
