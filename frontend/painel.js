// Lógica do painel por setor, sem acesso à página: setores, indicadores, temas,
// série mensal e o login de demonstração. Os números vêm do dashboard.json,
// calculado uma vez pelo workflow Classify themes (src/themes/dashboard.py).
import { OVERVIEW_AREA } from "./logic.js";

export const DIRECTOR = "diretoria";
export const PERIODS = ["todos", "2018", "2017"];

// Login de demonstração: qualquer e-mail e senha entram, e nada é conferido
export const DEMO_EMAIL = "gestor@demo.com.br";
export const DEMO_PASSWORD = "demo1234";
export const DEMO_NAME = "Gestor demo";

const DIRECTOR_SECTOR = {
  id: DIRECTOR,
  label: "Diretoria geral",
  summary: "Todos os setores: principais reclamações e elogios da base inteira",
  themes: [],
};

// Área das perguntas sugeridas (logic.js) que corresponde a cada setor
export const SECTOR_AREAS = {
  [DIRECTOR]: OVERVIEW_AREA,
  logistica: "Logística",
  produto: "Produto e anúncio",
  vendedor: "Vendedor e atendimento",
  retencao: "Retenção e reputação",
  fortes: "Pontos fortes",
};

// Pergunta sugerida ao clicar num tema do painel
const THEME_QUESTIONS = {
  atraso: "O que os clientes relatam sobre atrasos na entrega?",
  nao_recebido: "O que os clientes relatam sobre produtos que nunca foram entregues?",
  incompleto: "O que os clientes relatam sobre pedidos que chegaram incompletos?",
  avaria: "Como os clientes descrevem os produtos que chegaram danificados?",
  rastreio: "Como os clientes descrevem a informação que recebem sobre o andamento do pedido?",
  defeito: "O que os clientes relatam sobre produtos que chegaram com defeito?",
  diferente_anuncio: "Quais diferenças entre o anúncio e o produto recebido os clientes mais apontam?",
  tamanho: "O que os clientes comentam sobre o tamanho e as medidas dos produtos?",
  qualidade_baixa: "Do que os clientes reclamam na qualidade dos produtos?",
  falsificado: "O que os clientes relatam sobre produtos falsificados ou que não são originais?",
  sem_resposta: "O que os clientes dizem quando não conseguem contato com a loja?",
  troca_devolucao: "Quais problemas os clientes relatam na troca ou devolução de produtos?",
  reembolso: "O que os clientes relatam sobre estorno ou reembolso do pagamento?",
  cancelamento: "O que os clientes relatam sobre pedidos cancelados?",
  nao_volta: "O que faz um cliente dizer que não volta a comprar?",
  reclamacao_formal: "Que tipo de problema faz o cliente falar em Procon ou reclamação pública?",
  recompra: "O que leva os clientes a dizer que vão comprar de novo ou recomendar a loja?",
  entrega_rapida: "O que os clientes destacam quando a entrega é rápida?",
  produto_bom: "O que os clientes elogiam na qualidade dos produtos?",
  conforme_anuncio: "O que os clientes dizem quando o produto chega igual ao anúncio?",
  bem_embalado: "O que os clientes elogiam na embalagem dos pedidos?",
  bom_atendimento: "Quais atitudes do vendedor os clientes mais elogiam?",
  bom_preco: "O que os clientes dizem sobre o custo-benefício dos produtos?",
};

export function themeQuestion(theme) {
  return THEME_QUESTIONS[theme.id] || `O que os clientes comentam sobre ${theme.label.toLowerCase()}?`;
}

// Perguntas do chat quando há um tema escolhido no painel. Todas falam do
// próprio tema, porque a busca fica restrita a ele: uma pergunta geral ali
// seria respondida só com as avaliações do tema.
export function themeSuggestions(theme) {
  const name = `"${theme.label}"`;
  const extra = theme.polarity === "elogio"
    ? [
        `O que os clientes que deram nota 5 destacam no tema ${name}?`,
        `Que detalhes os clientes citam quando falam de ${name}?`,
      ]
    : [
        `O que os clientes que deram nota 1 contam sobre ${name}?`,
        `Como os clientes dizem que a loja resolveu, ou não, os casos de ${name}?`,
      ];
  return [themeQuestion(theme), ...extra];
}

// Perguntas que fazem sentido no recorte do chat: as do tema, as da área do
// setor ou null na diretoria, que pode receber perguntas de qualquer área
export function scopeSuggestionPool(data, areas, sectorId, themeId) {
  const theme = themeId ? findTheme(data, themeId) : null;
  if (theme) return themeSuggestions(theme);
  if (!sectorId || sectorId === DIRECTOR) return null;
  const area = areas.find((item) => item.area === SECTOR_AREAS[sectorId]);
  return area ? [...area.questions] : null;
}

// Diretoria geral primeiro, depois os setores na ordem do arquivo
export function sectorList(data) {
  return [DIRECTOR_SECTOR, ...data.sectors];
}

export function findSector(data, id) {
  return sectorList(data).find((sector) => sector.id === id) || null;
}

export function findTheme(data, id) {
  return data.themes.find((theme) => theme.id === id) || null;
}

// Números no formato brasileiro
export function formatNumber(value) {
  return Number(value).toLocaleString("pt-BR");
}

export function formatPercent(part, total, digits = 1) {
  if (!total) return "0%";
  return `${((100 * part) / total).toFixed(digits).replace(".", ",")}%`;
}

export function formatRating(value) {
  return value === null || value === undefined ? "sem nota" : value.toFixed(2).replace(".", ",");
}

const MONTHS = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];

export function monthLabel(month) {
  const [year, number] = month.split("-");
  return `${MONTHS[Number(number) - 1]}/${year.slice(2)}`;
}

// Nome mostrado no topo a partir do e-mail: "ana.souza@x" vira "Ana Souza"
export function displayName(email) {
  const clean = (email || "").trim().toLowerCase();
  if (!clean || clean === DEMO_EMAIL) return DEMO_NAME;
  const local = clean.split("@")[0];
  const words = local.split(/[._-]+/).filter(Boolean);
  if (!words.length) return DEMO_NAME;
  return words.map((word) => word.charAt(0).toUpperCase() + word.slice(1)).join(" ");
}

export function initials(name) {
  const words = name.split(/\s+/).filter(Boolean);
  return words
    .slice(0, 2)
    .map((word) => word.charAt(0).toUpperCase())
    .join("");
}

// Sessão guardada no navegador. Qualquer coisa fora do formato vale como sem login.
export function parseSession(raw, data) {
  try {
    const session = JSON.parse(raw);
    if (!session || typeof session.email !== "string" || !session.email) return null;
    const sector = session.sector && data && findSector(data, session.sector) ? session.sector : null;
    return { email: session.email, name: displayName(session.email), sector };
  } catch {
    return null;
  }
}

// Temas de um setor no período, do mais citado para o menos citado
export function themeRows(data, period, sectorId) {
  const summary = data.periods[period];
  const labels = Object.fromEntries(data.sectors.map((sector) => [sector.id, sector.label]));
  return data.themes
    .filter((theme) => sectorId === DIRECTOR || theme.sector === sectorId)
    .map((theme) => {
      const numbers = summary.themes[theme.id] || { count: 0, avg_rating: null, low: 0 };
      return {
        ...theme,
        sectorLabel: labels[theme.sector],
        count: numbers.count,
        share: summary.total ? numbers.count / summary.total : 0,
        avgRating: numbers.avg_rating,
      };
    })
    .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label));
}

const DIRECTOR_COMPLAINTS = 6;
const DIRECTOR_PRAISES = 4;

// Reclamações e elogios do painel. A diretoria vê os mais citados de todos os setores.
export function themeGroups(data, period, sectorId) {
  const rows = themeRows(data, period, sectorId);
  const complaints = rows.filter((row) => row.polarity === "reclamacao");
  const praises = rows.filter((row) => row.polarity === "elogio");
  if (sectorId === DIRECTOR) {
    return {
      complaints: complaints.slice(0, DIRECTOR_COMPLAINTS),
      praises: praises.slice(0, DIRECTOR_PRAISES),
    };
  }
  return { complaints, praises };
}

// "1 em cada 4": a proporção dita do jeito que se fala, para quem lê rápido
export function oneIn(part, total) {
  if (!part || !total) return null;
  const exact = total / part;
  const n = Math.round(exact);
  // Só quando o arredondamento não distorce: 39,6% não vira "1 em cada 3"
  if (n < 2 || Math.abs(exact - n) / exact > 0.12) return null;
  return `1 em cada ${n}`;
}

function withOneIn(text, part, total) {
  const ratio = oneIn(part, total);
  return ratio ? `${text}: ${ratio}` : text;
}

function deliveryShare(summary, keys) {
  return keys.reduce((total, key) => total + summary.delivery[key].count, 0);
}

function combinedRating(summary, keys) {
  let count = 0;
  let sum = 0;
  for (const key of keys) {
    const item = summary.delivery[key];
    if (item.count && item.avg_rating !== null) {
      count += item.count;
      sum += item.avg_rating * item.count;
    }
  }
  return count ? Math.round((100 * sum) / count) / 100 : null;
}

// Mês com a maior parte dos pedidos fora do prazo, entre os meses com volume razoável
const MIN_MONTH_REVIEWS = 200;
const MIN_PEAK_DISTANCE = 3;

function worstLateMonth(summary) {
  const months = summary.monthly.filter((item) => item.total >= MIN_MONTH_REVIEWS);
  if (!months.length) return null;
  return months.reduce((worst, item) =>
    item.late / item.total > worst.late / worst.total ? item : worst,
  );
}

function ratingSum(summary, ratings) {
  return ratings.reduce((total, rating) => total + (summary.ratings[String(rating)] || 0), 0);
}

// Quatro indicadores do topo do painel, conforme o setor
export function sectorKpis(data, period, sectorId) {
  const summary = data.periods[period];
  const total = summary.total;
  const late = ["atrasada", "nao_entregue"];
  if (sectorId === DIRECTOR) {
    const low = ratingSum(summary, [1, 2]);
    return [
      {
        label: "Avaliações com comentário",
        value: formatNumber(total),
        note: summary.label,
        help: "Base usada no painel e no chat",
      },
      {
        label: "Nota média",
        value: formatRating(summary.avg_rating),
        note: "de 1 a 5 estrelas",
        help: "Média das estrelas dadas pelos clientes",
      },
      {
        label: "Notas 1 e 2",
        value: formatPercent(low, total),
        note: `${formatNumber(low)} avaliações`,
        tone: "bad",
        help: withOneIn("Clientes insatisfeitos", low, total),
      },
      {
        label: "Atrasadas ou não entregues",
        value: formatPercent(deliveryShare(summary, late), total),
        note: `nota média ${formatRating(combinedRating(summary, late))}`,
        tone: "bad",
        help: withOneIn("Pedidos fora do prazo", deliveryShare(summary, late), total),
      },
    ];
  }
  if (sectorId === "logistica") {
    const onTime = summary.delivery.no_prazo.avg_rating;
    const lateRating = summary.delivery.atrasada.avg_rating;
    const worst = worstLateMonth(summary);
    const kpis = [
      {
        label: "Entregas atrasadas",
        value: formatPercent(summary.delivery.atrasada.count, total),
        note: `${formatNumber(summary.delivery.atrasada.count)} avaliações`,
        help: "Chegaram depois da data prometida",
      },
      {
        label: "Não entregues",
        value: formatPercent(summary.delivery.nao_entregue.count, total),
        note: `${formatNumber(summary.delivery.nao_entregue.count)} avaliações`,
        help: "O pedido não tem data de entrega",
      },
      {
        label: "Nota média com atraso",
        value: formatRating(lateRating),
        note: `contra ${formatRating(onTime)} no prazo`,
        tone: "bad",
        help: "Quanto a nota cai quando a entrega atrasa",
      },
    ];
    if (worst) {
      kpis.push({
        label: "Pior mês",
        value: monthLabel(worst.month),
        note: `${formatPercent(worst.late, worst.total)} fora do prazo`,
        help: "Mês com mais entregas fora do prazo",
      });
    }
    return kpis;
  }
  const sector = summary.sectors[sectorId];
  const top = themeRows(data, period, sectorId).slice(0, 2);
  const praise = sectorId === "fortes";
  return [
    {
      label: praise ? "Avaliações com elogio" : "Avaliações do setor",
      value: formatNumber(sector.count),
      note: `${formatPercent(sector.count, total)} das avaliações`,
      help: praise ? "Citam pelo menos um elogio" : "Citam pelo menos um tema do setor",
    },
    {
      label: "Nota média nelas",
      value: formatRating(sector.avg_rating),
      note: `${formatRating(summary.avg_rating)} na base inteira`,
      tone: praise ? "ok" : "bad",
      help: "Média das estrelas nessas avaliações",
    },
    ...top.map((row, index) => ({
      label: row.label,
      value: formatNumber(row.count),
      note: `nota média ${formatRating(row.avgRating)}`,
      help: index === 0 ? "Tema mais citado do setor" : "Segundo tema mais citado",
    })),
  ];
}

// Evolução mensal mostrada no painel: atrasos para a logística, elogios para
// os pontos fortes e notas baixas para os demais. Meses com poucas avaliações
// ficam de fora, porque um percentual sobre poucas dezenas engana.
export function monthlySeries(data, period, sectorId) {
  const summary = data.periods[period];
  const kind = sectorId === "logistica" ? "late" : sectorId === "fortes" ? "high" : "low";
  const titles = {
    late: "Entregas fora do prazo por mês",
    high: "Avaliações com nota 4 ou 5 por mês",
    low: "Avaliações com nota 1 ou 2 por mês",
  };
  const points = summary.monthly
    .filter((item) => item.total >= MIN_MONTH_REVIEWS)
    .map((item) => ({
      month: item.month,
      label: monthLabel(item.month),
      value: Math.round((1000 * item[kind]) / item.total) / 10,
      total: item.total,
    }));
  // Os dois meses de destaque ficam separados, para os rótulos não se encostarem
  const order = [...points.keys()].sort((a, b) =>
    kind === "high" ? points[a].value - points[b].value : points[b].value - points[a].value,
  );
  const peaks = [];
  for (const index of order) {
    if (peaks.length === 2) break;
    if (peaks.every((other) => Math.abs(other - index) >= MIN_PEAK_DISTANCE)) peaks.push(index);
  }
  peaks.sort((a, b) => a - b);
  // Média ponderada dos meses mostrados, desenhada como linha de referência
  const shown = summary.monthly.filter((item) => item.total >= MIN_MONTH_REVIEWS);
  const shownTotal = shown.reduce((sum, item) => sum + item.total, 0);
  const average = shownTotal
    ? Math.round((1000 * shown.reduce((sum, item) => sum + item[kind], 0)) / shownTotal) / 10
    : null;
  // Só a logística e a diretoria têm uma série que é delas; nos outros setores
  // a curva é a da base inteira, e o título diz isso
  const baseWide = sectorId !== DIRECTOR && sectorId !== "logistica";
  return { kind, title: titles[kind], points, peaks, average, baseWide };
}

const SERIES_WORDS = {
  late: "das entregas ficaram fora do prazo",
  high: "das avaliações tiveram nota 4 ou 5",
  low: "das avaliações tiveram nota 1 ou 2",
};

// Frase que diz o que o gráfico mostra, em vez de deixar a leitura para o gestor
export function chartTakeaway(series) {
  if (series.points.length < 2) return "";
  const pick = series.kind === "high"
    ? (a, b) => (b.value < a.value ? b : a)
    : (a, b) => (b.value > a.value ? b : a);
  const extreme = series.points.reduce(pick);
  const ratio = oneIn(extreme.value, 100);
  const word = series.kind === "high" ? "Pior mês" : "Mês mais crítico";
  const parts = [
    `${word}: ${extreme.label}, quando ${String(extreme.value).replace(".", ",")}% ${SERIES_WORDS[series.kind]}${ratio ? ` (${ratio})` : ""}.`,
  ];
  if (series.average !== null) {
    parts.push(`A média do período é ${String(series.average).replace(".", ",")}%, a linha tracejada.`);
  }
  return parts.join(" ");
}

// Resumo do painel numa frase, no topo, para quem só tem alguns segundos
export function sectorHeadline(data, period, sectorId) {
  const summary = data.periods[period];
  const total = summary.total;
  const groups = themeGroups(data, period, sectorId);
  const topComplaint = groups.complaints[0];
  const topPraise = groups.praises[0];
  if (sectorId === DIRECTOR) {
    const low = ratingSum(summary, [1, 2]);
    const ratio = oneIn(low, total);
    const parts = [
      ratio
        ? `${ratio} avaliações tem nota 1 ou 2.`
        : `${formatPercent(low, total)} das avaliações têm nota 1 ou 2.`,
    ];
    if (topComplaint) {
      parts.push(`A reclamação mais citada é "${topComplaint.label}" (${formatNumber(topComplaint.count)} avaliações)`);
    }
    if (topPraise) {
      parts[parts.length - 1] += `, e o elogio mais citado é "${topPraise.label}" (${formatNumber(topPraise.count)}).`;
    } else if (topComplaint) {
      parts[parts.length - 1] += ".";
    }
    return parts.join(" ");
  }
  if (sectorId === "logistica") {
    const late = deliveryShare(summary, ["atrasada", "nao_entregue"]);
    const ratio = oneIn(late, total);
    return (
      `${ratio ? `${ratio} pedidos avaliados chegou` : `${formatPercent(late, total)} dos pedidos avaliados chegaram`} fora do prazo ou não chegou. ` +
      `Quando atrasa, a nota média cai de ${formatRating(summary.delivery.no_prazo.avg_rating)} para ${formatRating(summary.delivery.atrasada.avg_rating)}.`
    );
  }
  const sector = summary.sectors[sectorId];
  const label = findSector(data, sectorId)?.label || "";
  if (sectorId === "fortes") {
    const parts = [`${formatPercent(sector.count, total, 0)} das avaliações trazem algum elogio.`];
    if (topPraise) parts.push(`O mais citado é "${topPraise.label}", em ${formatNumber(topPraise.count)} avaliações.`);
    return parts.join(" ");
  }
  const parts = [
    `${formatPercent(sector.count, total)} das avaliações falam de ${label.toLowerCase()}, com nota média ${formatRating(sector.avg_rating)} (a base inteira tem ${formatRating(summary.avg_rating)}).`,
  ];
  if (topComplaint) parts.push(`O problema mais citado é "${topComplaint.label}".`);
  return parts.join(" ");
}

// Temas usados como filtro do chat: o tema clicado, os do setor ou nenhum
export function scopeThemes(data, sectorId, themeId) {
  if (themeId) return [themeId];
  if (!sectorId || sectorId === DIRECTOR) return null;
  const sector = findSector(data, sectorId);
  return sector && sector.themes.length ? [...sector.themes] : null;
}

export function scopeLabel(data, sectorId, themeId) {
  if (themeId) {
    const theme = findTheme(data, themeId);
    return theme ? `do tema "${theme.label}"` : "do tema escolhido";
  }
  if (!sectorId || sectorId === DIRECTOR) return "da base inteira";
  const sector = findSector(data, sectorId);
  return `do setor ${sector ? sector.label : ""}`.trim();
}

// Frase sobre o recorte da busca, embaixo da pergunta respondida
export function scopeLine(scopeCount, label, used) {
  if (scopeCount === null || scopeCount === undefined) return null;
  const base = `${formatNumber(scopeCount)} ${scopeCount === 1 ? "avaliação" : "avaliações"} ${label}`;
  if (!used) return base;
  return `${base} · ${used} usadas na resposta`;
}

// O dashboard.json de prévia foi calculado por palavras-chave, e não pelo modelo
export function isPreview(data) {
  return String(data.model_id || "").startsWith("previa");
}
