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
      { label: "Avaliações com comentário", value: formatNumber(total), note: summary.label },
      { label: "Nota média", value: formatRating(summary.avg_rating), note: "de 1 a 5 estrelas" },
      {
        label: "Notas 1 e 2",
        value: formatPercent(low, total),
        note: `${formatNumber(low)} avaliações`,
        tone: "bad",
      },
      {
        label: "Entrega fora do prazo",
        value: formatPercent(deliveryShare(summary, late), total),
        note: `nota média ${formatRating(combinedRating(summary, late))}`,
        tone: "bad",
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
      },
      {
        label: "Não entregues",
        value: formatPercent(summary.delivery.nao_entregue.count, total),
        note: `${formatNumber(summary.delivery.nao_entregue.count)} avaliações`,
      },
      {
        label: "Nota média com atraso",
        value: formatRating(lateRating),
        note: `contra ${formatRating(onTime)} no prazo`,
        tone: "bad",
      },
    ];
    if (worst) {
      kpis.push({
        label: "Pior mês",
        value: monthLabel(worst.month),
        note: `${formatPercent(worst.late, worst.total)} fora do prazo`,
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
    },
    {
      label: "Nota média nelas",
      value: formatRating(sector.avg_rating),
      note: `${formatRating(summary.avg_rating)} na base inteira`,
      tone: praise ? "ok" : "bad",
    },
    ...top.map((row) => ({
      label: row.label,
      value: formatNumber(row.count),
      note: `nota média ${formatRating(row.avgRating)}`,
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
  return { kind, title: titles[kind], points, peaks };
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
  const base = `Busca feita em ${formatNumber(scopeCount)} ${scopeCount === 1 ? "avaliação" : "avaliações"} ${label}.`;
  if (!used) return base;
  return `${base} A resposta usa as ${used} mais parecidas com a pergunta.`;
}

// O dashboard.json de prévia foi calculado por palavras-chave, e não pelo modelo
export function isPreview(data) {
  return String(data.model_id || "").startsWith("previa");
}
