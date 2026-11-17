// Painel do setor: indicadores, temas, exemplos, evolução mensal e, na
// diretoria, o resumo de cada setor. Tudo vem do dashboard.json e entra na
// tela com textContent; o gráfico é montado em SVG com createElementNS.
import { categoryLabel, deliveryLabel, formatDate } from "./logic.js";
import {
  DIRECTOR,
  PERIODS,
  findSector,
  findTheme,
  formatNumber,
  formatPercent,
  formatRating,
  isPreview,
  chartTakeaway,
  monthlySeries,
  sectorHeadline,
  sectorKpis,
  themeGroups,
} from "./painel.js";

const SVG_NS = "http://www.w3.org/2000/svg";

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function svg(tag, attributes = {}, text) {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, String(value));
  if (text !== undefined) node.textContent = text;
  return node;
}

const $ = (id) => document.getElementById(id);

function kpiTile(kpi) {
  const tile = element("div", "kpi");
  tile.appendChild(element("p", "kpi-label", kpi.label));
  tile.appendChild(element("p", "kpi-value", kpi.value));
  const note = element("p", "kpi-note", kpi.note);
  if (kpi.tone) note.dataset.tone = kpi.tone;
  tile.appendChild(note);
  // O que o número quer dizer, em palavras, para quem não conhece o indicador
  if (kpi.help) tile.appendChild(element("p", "kpi-help", kpi.help));
  return tile;
}

// Uma linha por tema: nome, números e a barra proporcional ao mais citado.
// A barra é só reforço visual; o número fica escrito ao lado.
function themeButton(row, max, { selected, showSector, onSelect }) {
  const button = element("button", "theme-row");
  button.type = "button";
  button.dataset.polarity = row.polarity;
  button.setAttribute("aria-pressed", String(selected));
  const name = element("span", "theme-name", row.label);
  if (showSector) name.appendChild(element("span", "theme-sector", ` · ${row.sectorLabel}`));
  button.appendChild(name);
  const numbers = element("span", "theme-numbers");
  numbers.appendChild(element("strong", null, formatNumber(row.count)));
  numbers.appendChild(
    document.createTextNode(` avaliações (${formatPercent(row.share * 100, 100)} do total)`),
  );
  const rating = element("span", "theme-rating", `★ ${formatRating(row.avgRating)}`);
  rating.dataset.tone = row.avgRating !== null && row.avgRating < 3 ? "bad" : "ok";
  rating.title = "Nota média dessas avaliações, de 1 a 5";
  rating.setAttribute("aria-label", `nota média ${formatRating(row.avgRating)} de 5`);
  numbers.appendChild(rating);
  button.appendChild(numbers);
  const bar = element("span", "theme-bar");
  bar.setAttribute("aria-hidden", "true");
  const fill = element("span", "theme-bar-fill");
  fill.style.width = `${max ? Math.max(1, (100 * row.count) / max) : 0}%`;
  bar.appendChild(fill);
  button.appendChild(bar);
  if (selected) button.appendChild(element("span", "theme-open", "Aberto no chat"));
  button.addEventListener("click", () => onSelect(row.id));
  return button;
}

function themeList(container, rows, options) {
  const max = Math.max(0, ...rows.map((row) => row.count));
  container.replaceChildren(
    ...rows.map((row) =>
      themeButton(row, max, { ...options, selected: options.selectedTheme === row.id }),
    ),
  );
  if (!rows.length) container.appendChild(element("p", "dash-empty", "Nenhum tema neste setor."));
}

function examplesList(container, items) {
  if (!items.length) {
    container.replaceChildren(element("p", "dash-empty", "Nenhum comentário curto deste tema."));
    return;
  }
  container.replaceChildren(
    ...items.map((item) => {
      const quote = element("figure", "dash-quote");
      quote.appendChild(element("blockquote", null, item.text));
      const meta = element("figcaption", "dash-quote-meta");
      const stars = element("span", "stars", "★".repeat(item.rating) + "☆".repeat(5 - item.rating));
      stars.setAttribute("role", "img");
      stars.setAttribute("aria-label", `Nota ${item.rating} de 5`);
      meta.appendChild(stars);
      const parts = [
        deliveryLabel(item.delivery)?.text,
        categoryLabel(item.category),
        formatDate(item.review_date),
      ].filter(Boolean);
      meta.appendChild(document.createTextNode(` · ${parts.join(" · ")}`));
      quote.appendChild(meta);
      return quote;
    }),
  );
}

// Gráfico de linha de uma série só, com os dois meses de destaque rotulados.
// Uma tabela escondida traz os mesmos números para o leitor de tela.
function lineChart(container, series) {
  container.replaceChildren();
  const points = series.points;
  if (points.length < 2) {
    container.appendChild(element("p", "dash-empty", "Poucos meses com avaliações neste período."));
    return;
  }
  // A largura do desenho acompanha a da caixa, para o texto não encolher no celular
  const width = Math.max(300, Math.min(900, container.clientWidth || 760));
  const height = width < 520 ? 200 : 220;
  // A margem da direita guarda o rótulo da média, fora da área das linhas
  const pad = { left: 40, right: 64, top: 24, bottom: 28 };
  const top = Math.max(10, Math.ceil(Math.max(...points.map((p) => p.value)) / 10) * 10);
  const x = (i) => pad.left + (i * (width - pad.left - pad.right)) / (points.length - 1);
  const y = (v) => height - pad.bottom - (v / top) * (height - pad.top - pad.bottom);

  const chart = svg("svg", {
    viewBox: `0 0 ${width} ${height}`,
    class: "line-chart",
    "aria-hidden": "true",
  });
  const step = top / 4;
  for (let v = 0; v <= top + 0.001; v += step) {
    chart.appendChild(svg("line", { x1: pad.left, x2: width - pad.right, y1: y(v), y2: y(v), class: "grid" }));
    chart.appendChild(
      svg("text", { x: pad.left - 6, y: y(v) + 4, "text-anchor": "end" }, `${Math.round(v)}%`),
    );
  }
  const labelEvery = Math.ceil(points.length / (width < 520 ? 4 : 6));
  points.forEach((point, i) => {
    const last = points.length - 1;
    // O último mês sempre aparece; o rótulo anterior sai se ficar colado nele
    if (i !== last && (i % labelEvery !== 0 || last - i < labelEvery)) return;
    const anchor = i === 0 ? "start" : i === points.length - 1 ? "end" : "middle";
    chart.appendChild(svg("text", { x: x(i), y: height - 8, "text-anchor": anchor }, point.label));
  });
  if (series.average !== null && series.average !== undefined) {
    const avgY = y(series.average);
    chart.appendChild(svg("line", { x1: pad.left, x2: width - pad.right, y1: avgY, y2: avgY, class: "average" }));
    // Rótulo em duas linhas, para caber na margem também no celular
    const labelX = width - pad.right + 6;
    chart.appendChild(svg("text", { x: labelX, y: avgY - 2, class: "average-label" }, "média"));
    chart.appendChild(
      svg("text", { x: labelX, y: avgY + 11, class: "average-label" }, `${String(series.average).replace(".", ",")}%`),
    );
  }
  const path = points.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p.value).toFixed(1)}`);
  chart.appendChild(svg("path", { d: path.join(""), class: "line" }));
  for (const i of series.peaks) {
    const p = points[i];
    chart.appendChild(svg("circle", { cx: x(i), cy: y(p.value), r: 4, class: "dot" }));
    chart.appendChild(
      svg(
        "text",
        { x: x(i), y: y(p.value) - 9, "text-anchor": "middle", class: "peak" },
        `${String(p.value).replace(".", ",")}%`,
      ),
    );
  }
  // Pontos invisíveis maiores que a linha, com o valor de cada mês ao passar o mouse
  points.forEach((p, i) => {
    const hit = svg("circle", { cx: x(i), cy: y(p.value), r: 10, class: "hit" });
    hit.appendChild(svg("title", {}, `${p.label}: ${String(p.value).replace(".", ",")}% de ${formatNumber(p.total)} avaliações`));
    chart.appendChild(hit);
  });
  container.appendChild(chart);

  // A tabela fica dentro de uma caixa escondida: a própria tabela ignoraria a altura de 1px
  const hidden = element("div", "visually-hidden");
  const table = element("table");
  const head = element("tr");
  head.append(element("th", null, "Mês"), element("th", null, "Percentual"));
  table.appendChild(head);
  for (const p of points) {
    const row = element("tr");
    row.append(element("td", null, p.label), element("td", null, `${String(p.value).replace(".", ",")}%`));
    table.appendChild(row);
  }
  hidden.appendChild(table);
  container.appendChild(hidden);
}

function chartSubtitle(series) {
  const base = series.baseWide
    ? "Curva da base inteira, e não só deste setor. Cada ponto é o percentual sobre as avaliações do mês, só nos meses com 200 avaliações ou mais."
    : "Cada ponto é o percentual sobre as avaliações do mês, só nos meses com 200 avaliações ou mais.";
  return base;
}

function sectorSummary(container, data, period, onOpenSector) {
  const summary = data.periods[period];
  container.replaceChildren(
    ...data.sectors.map((sector) => {
      const numbers = summary.sectors[sector.id];
      const card = element("button", "sector-mini");
      card.type = "button";
      card.appendChild(element("span", "sector-mini-title", sector.label));
      card.appendChild(element("span", "sector-mini-value", formatNumber(numbers.count)));
      card.appendChild(
        element(
          "span",
          "sector-mini-note",
          `${formatPercent(numbers.count, summary.total)} das avaliações · nota ${formatRating(numbers.avg_rating)}`,
        ),
      );
      card.appendChild(element("span", "sector-mini-link", "Abrir painel"));
      card.addEventListener("click", () => onOpenSector(sector.id));
      return card;
    }),
  );
}

function periodTabs(container, data, period, onPeriod) {
  container.replaceChildren(
    ...PERIODS.filter((key) => data.periods[key]).map((key) => {
      const tab = element("button", "period-tab", data.periods[key].label);
      tab.type = "button";
      tab.setAttribute("aria-pressed", String(key === period));
      tab.addEventListener("click", () => onPeriod(key));
      return tab;
    }),
  );
}

export function renderDashboard({ data, sectorId, period, selectedTheme, onTheme, onPeriod, onOpenSector }) {
  const sector = findSector(data, sectorId);
  const summary = data.periods[period];
  const director = sectorId === DIRECTOR;
  $("dash-title").textContent = sector.label;
  $("dash-sub").textContent =
    `Clientes da Olist · ${formatNumber(summary.total)} avaliações com comentário · ${summary.label === "Todo o período" ? "pedidos de 2016 a 2018" : `avaliações de ${summary.label}`}`;
  $("preview-note").hidden = !isPreview(data);
  periodTabs($("period-tabs"), data, period, onPeriod);
  $("dash-headline").textContent = sectorHeadline(data, period, sectorId);
  $("kpis").replaceChildren(...sectorKpis(data, period, sectorId).map(kpiTile));

  const groups = themeGroups(data, period, sectorId);
  const praiseSector = sectorId === "fortes";
  const mainRows = praiseSector ? groups.praises : groups.complaints;
  $("complaints-title").textContent = praiseSector
    ? "Elogios mais frequentes"
    : director
      ? "Principais reclamações"
      : "Reclamações mais frequentes";
  const listOptions = { selectedTheme, showSector: director, onSelect: onTheme };
  themeList($("complaints"), mainRows, listOptions);
  $("complaints").closest(".dash-card").dataset.polarity = praiseSector ? "elogio" : "reclamacao";

  // Ao lado: na diretoria, os elogios; nos setores, os comentários do tema
  // escolhido (ou do mais citado), e os elogios do setor quando há
  const side = $("side-body");
  side.replaceChildren();
  if (director) {
    $("side-title").textContent = "Principais elogios";
    $("side-sub").textContent = "Quantas avaliações citam cada elogio. Clique num tema para ver comentários e perguntar ao chat.";
    const list = element("div", "theme-list");
    themeList(list, groups.praises, { ...listOptions, showSector: false });
    side.appendChild(list);
    side.closest(".dash-card").dataset.polarity = "elogio";
  } else {
    const shown = findTheme(data, selectedTheme) ? selectedTheme : mainRows[0]?.id;
    const theme = findTheme(data, shown);
    $("side-title").textContent = "Exemplos de comentários";
    $("side-sub").textContent = theme ? `Avaliações reais do tema "${theme.label}"` : "";
    const quotes = element("div", "dash-quotes");
    examplesList(quotes, (theme && data.examples[theme.id]) || []);
    side.appendChild(quotes);
    if (!praiseSector && groups.praises.length) {
      side.appendChild(element("h4", "side-extra-title", "Elogios do setor"));
      const list = element("div", "theme-list");
      themeList(list, groups.praises, listOptions);
      side.appendChild(list);
    }
    side.closest(".dash-card").dataset.polarity = "reclamacao";
  }

  const series = monthlySeries(data, period, sectorId);
  $("chart-title").textContent = series.baseWide ? `${series.title}, na base inteira` : series.title;
  $("chart-sub").textContent = chartSubtitle(series);
  $("chart-takeaway").textContent = chartTakeaway(series);
  lineChart($("chart"), series);

  const summaryBox = $("sector-summary");
  summaryBox.hidden = !director;
  if (director) sectorSummary(summaryBox, data, period, onOpenSector);

  const date = formatDate(data.generated_at);
  $("dash-generated").textContent = date ? `Números calculados em ${date}.` : "";
}
