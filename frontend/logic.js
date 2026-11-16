// Lógica da página que não depende do navegador, testada com o Node em
// tests/frontend/. A montagem da tela fica em app.js.
import { CATEGORY_NAMES } from "./categories.js";

// [3], [1,3] e [1, 3]; colchetes com texto, como [Lannister], ficam como texto
const CITATION = /\[\s*(\d+(?:\s*,\s*\d+)*)\s*\]/g;

// Divide um trecho da resposta em partes de texto e citações [n]
export function splitCitations(text) {
  const parts = [];
  let last = 0;
  for (const match of text.matchAll(CITATION)) {
    if (match.index > last) parts.push({ type: "text", value: text.slice(last, match.index) });
    parts.push({ type: "cite", numbers: match[1].split(",").map((n) => Number(n.trim())) });
    last = match.index + match[0].length;
  }
  if (last < text.length) parts.push({ type: "text", value: text.slice(last) });
  return parts;
}

// Divide a resposta em parágrafos e listas. O modelo escreve em texto simples,
// com hífen no começo dos itens de lista.
export function parseAnswerBlocks(answer) {
  const blocks = [];
  for (const raw of answer.split("\n")) {
    const line = raw.trim();
    if (!line) continue;
    const item = line.match(/^[-*•]\s+(.*)$/);
    if (item) {
      const previous = blocks[blocks.length - 1];
      if (previous && previous.type === "list") previous.items.push(item[1]);
      else blocks.push({ type: "list", items: [item[1]] });
    } else {
      blocks.push({ type: "paragraph", text: line });
    }
  }
  // Um hífen solto no começo da resposta não é lista: vira parágrafo
  return blocks.map((block) =>
    block.type === "list" && block.items.length === 1
      ? { type: "paragraph", text: block.items[0] }
      : block,
  );
}

const NOTICES = {
  no_evidence: {
    kind: "no_evidence",
    title: "Sem evidência",
    text: "Não há avaliações suficientes sobre esse tema entre as recuperadas.",
  },
  weak_evidence: {
    kind: "weak_evidence",
    title: "Evidência fraca",
    text: "Poucas avaliações sustentam esta resposta. Leia como um indício, não como um padrão.",
  },
  out_of_scope: {
    kind: "out_of_scope",
    title: "Fora do escopo",
    text: "As avaliações dos clientes não respondem a esse tipo de pergunta.",
  },
};

// Aviso mostrado acima da resposta, ou null quando a resposta é completa
export function statusNotice(status) {
  return NOTICES[status] || null;
}

// Status usado pela página quando a API não responde dentro do tempo limite
export const TIMEOUT_STATUS = -1;

// Mensagem para cada erro da API. O ALB devolve 502, 503 ou 504 sem corpo JSON
// quando a API está desligada; o 503 com JSON é um problema passageiro do Bedrock.
export function errorMessage(httpStatus, body) {
  const detail = body && typeof body.detail === "string" ? body.detail : null;
  if (httpStatus === TIMEOUT_STATUS) {
    return {
      kind: "timeout",
      message: "A resposta demorou mais do que o esperado. Tente de novo.",
    };
  }
  if (httpStatus === 401) {
    return { kind: "key", message: "Chave de acesso inválida. Confira a chave e tente de novo." };
  }
  if (httpStatus === 429) {
    return { kind: "quota", message: detail || "Limite diário de perguntas atingido." };
  }
  if (httpStatus === 422) {
    return {
      kind: "invalid",
      message: "A pergunta precisa ter entre 1 e 500 caracteres.",
    };
  }
  if (httpStatus === 503 && detail) {
    return { kind: "retry", message: detail };
  }
  if (httpStatus === 0 || httpStatus === 502 || httpStatus === 503 || httpStatus === 504) {
    return {
      kind: "offline",
      message: "O chat está desligado no momento. Ele funciona das 9h às 22h, horário de Brasília.",
    };
  }
  return { kind: "unexpected", message: detail || "Não foi possível responder. Tente de novo." };
}

// Nova tentativa com a mesma pergunta. No limite diário ou numa pergunta
// inválida, repetir não muda nada.
export function canRetry(kind) {
  return kind !== "quota" && kind !== "invalid";
}

export function formatSimilarity(value) {
  return value.toFixed(2).replace(".", ",");
}

const DELIVERY = {
  no_prazo: { text: "Entregue no prazo", tone: "ok" },
  atrasada: { text: "Entregue com atraso", tone: "warn" },
  nao_entregue: { text: "Não entregue", tone: "bad" },
};

// Situação da entrega do pedido, ou null quando a base não tem a informação
export function deliveryLabel(delivery) {
  return DELIVERY[delivery] || null;
}

// Categoria do produto com o nome acentuado; fora da tabela, o nome da base
// sem os sublinhados
export function categoryLabel(category) {
  if (!category || category === "desconhecido") return null;
  if (category === "mista") return "Várias categorias";
  if (CATEGORY_NAMES[category]) return CATEGORY_NAMES[category];
  const text = category.replaceAll("_", " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

// "2018-03-10" vira "10/03/2018"; datas fora desse formato não aparecem
export function formatDate(value) {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value || "");
  return match ? `${match[3]}/${match[2]}/${match[1]}` : null;
}

export function shortId(reviewId) {
  return reviewId.slice(0, 8);
}

export const MAX_CHARS = 500;

export function counterState(length) {
  if (length >= MAX_CHARS) return "full";
  if (length >= MAX_CHARS * 0.9) return "near";
  return "ok";
}

// Filtros da busca. Nenhuma nota marcada busca em todas; categoria e entrega
// vazias também. Sem nenhum filtro, a página não manda o campo.
export function buildFilters({ ratings, category, delivery }) {
  const filters = {};
  if (ratings && ratings.length) filters.ratings = [...ratings].map(Number).sort((a, b) => a - b);
  if (category) filters.category = category;
  if (delivery) filters.delivery = delivery;
  return Object.keys(filters).length ? filters : null;
}

const DELIVERY_FILTER_LABELS = {
  no_prazo: "entregas no prazo",
  atrasada: "entregas atrasadas",
  nao_entregue: "pedidos não entregues",
  com_problema: "entregas com problema",
};

function joinList(items) {
  if (items.length <= 1) return items.join("");
  return `${items.slice(0, -1).join(", ")} e ${items.at(-1)}`;
}

// As partes do resumo dos filtros, uma por filtro ativo
function filterParts(filters) {
  const parts = [];
  if (!filters) return parts;
  if (filters.ratings && filters.ratings.length) {
    const list = filters.ratings;
    parts.push(`${list.length === 1 ? "nota" : "notas"} ${joinList(list)}`);
  }
  if (filters.category) parts.push(categoryLabel(filters.category));
  if (filters.delivery) parts.push(DELIVERY_FILTER_LABELS[filters.delivery] || filters.delivery);
  return parts;
}

// Resumo dos filtros, como "notas 1 e 2 · Cama mesa banho · entregas com problema"
export function describeFilters(filters) {
  return filterParts(filters).join(" · ");
}

// Linha de apoio da faixa de filtros: diz onde a busca está olhando
export function searchScopeText(filters) {
  const parts = filterParts(filters);
  if (!parts.length) return "Buscando em todas as avaliações";
  return `Buscando só em avaliações com ${joinList(parts)}`;
}

const CHIP_NAMES = { ratings: "Nota", category: "Categoria", delivery: "Entrega" };
const DELIVERY_CHIP_VALUES = {
  no_prazo: "no prazo",
  atrasada: "com atraso",
  nao_entregue: "não entregue",
  com_problema: "com problema",
};

// Texto de cada botão da faixa: só o nome, ou o nome com o valor escolhido
export function chipLabel(kind, filters) {
  const name = CHIP_NAMES[kind];
  if (!filters) return name;
  if (kind === "ratings" && filters.ratings && filters.ratings.length) {
    return `${name}: ${joinList(filters.ratings)}`;
  }
  if (kind === "category" && filters.category) return `${name}: ${categoryLabel(filters.category)}`;
  if (kind === "delivery" && filters.delivery) {
    return `${name}: ${DELIVERY_CHIP_VALUES[filters.delivery] || filters.delivery}`;
  }
  return name;
}

// Inclui ou retira uma nota, sem alterar a lista recebida
export function toggleRating(ratings, rating) {
  const next = ratings.includes(rating)
    ? ratings.filter((value) => value !== rating)
    : [...ratings, rating];
  return next.sort((a, b) => a - b);
}

export const RATING_SHORTCUTS = { low: [1, 2], high: [4, 5] };

export const DELIVERY_OPTIONS = [
  { value: "no_prazo", label: "Entregue no prazo" },
  { value: "atrasada", label: "Entregue com atraso" },
  { value: "nao_entregue", label: "Não entregue" },
  { value: "com_problema", label: "Com problema (atraso ou não entregue)" },
];

// Minúsculas, sem acentos e sem sublinhados, para comparar o que a pessoa digita
export function normalizeText(text) {
  return text
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replaceAll("_", " ")
    .toLowerCase()
    .trim();
}

// Categorias cujo nome contém o texto digitado; sem texto, todas
export function filterCategories(options, query) {
  const wanted = normalizeText(query);
  if (!wanted) return options;
  return options.filter(
    (option) =>
      normalizeText(option.label).includes(wanted) || normalizeText(option.value).includes(wanted),
  );
}

// Frase a mais no aviso de pouca evidência, quando a pergunta foi feita com filtros
export function restrictionNotice(status, filters) {
  const parts = filterParts(filters);
  if (!parts.length || (status !== "no_evidence" && status !== "weak_evidence")) return null;
  return `A busca estava restrita a ${joinList(parts)}`;
}

// Histórico enviado com a pergunta: as 3 últimas trocas, com as respostas cortadas
// no mesmo limite da API. Serve só para completar perguntas de continuação.
const HISTORY_TURNS = 3;
const HISTORY_ANSWER_CHARS = 1500;

export function buildHistory(turns) {
  return turns.slice(-HISTORY_TURNS).map((turn) => ({
    question: turn.question,
    answer: turn.answer.slice(0, HISTORY_ANSWER_CHARS),
  }));
}

// Aviso de que a busca foi restrita pelas notas que a própria pergunta mencionou
export function describeInferredRatings(ratings) {
  if (!ratings || !ratings.length) return null;
  return `A busca considerou só as avaliações de ${describeFilters({ ratings })}, citadas na pergunta.`;
}

// Tema da página. A escolha salva vale sobre o sistema; sem ela, a página
// segue a aparência do sistema operacional.
export function currentTheme(saved, systemDark) {
  if (saved === "light" || saved === "dark") return saved;
  return systemDark ? "dark" : "light";
}

export function nextTheme(theme) {
  return theme === "dark" ? "light" : "dark";
}

// Perguntas sugeridas depois de cada resposta. Todas tratam de temas que
// aparecem nos comentários das avaliações (entrega, produto, vendedor,
// pagamento, troca), e algumas testam o comportamento do chat quando há pouca
// ou nenhuma evidência, como a do Pix e a da embalagem de presente.
export const SUGGESTIONS = [
  "Quais reclamações sobre entrega aparecem com mais frequência?",
  "O que os clientes relatam sobre produtos que chegaram com defeito?",
  "Quais são os principais elogios dos clientes?",
  "O que os clientes relatam sobre o atendimento do vendedor?",
  "O que os clientes contam sobre produtos diferentes do anunciado?",
  "O que os clientes acham do aplicativo da loja?",
  "Os clientes pedem que os produtos venham em embalagem de presente?",
  "O que os clientes falam sobre pagar com Pix?",
  "O que os clientes comentam sobre a embalagem dos produtos?",
  "Como os clientes avaliam a qualidade dos produtos em relação ao preço?",
  "O que os clientes relatam sobre pedidos que chegaram incompletos?",
  "Quais problemas os clientes relatam na troca ou devolução de produtos?",
  "O que os clientes dizem quando o produto chega antes do prazo?",
  "Como os clientes descrevem a comunicação sobre o andamento do pedido?",
  "O que os clientes relatam sobre produtos que nunca foram entregues?",
  "O que os clientes falam sobre o rastreamento das encomendas?",
  "O que os clientes relatam sobre produtos falsificados ou que não são originais?",
  "O que os clientes comentam sobre o tamanho e as medidas dos produtos?",
  "Como os produtos frágeis chegam, segundo os clientes?",
  "O que os clientes relatam sobre estorno ou reembolso do pagamento?",
  "O que os clientes falam sobre a nota fiscal dos pedidos?",
  "Quais reclamações aparecem sobre a montagem de móveis?",
  "O que os clientes contam sobre a cor do produto ser diferente da foto?",
  "O que os clientes dizem sobre voltar a comprar na loja?",
  "O que os clientes relatam sobre pedidos entregues em datas diferentes?",
  // Perguntas de gestão: o que corrigir primeiro, com qual área falar, o que
  // manter e o que pode virar risco para a reputação
  "Quais problemas mais deixam os clientes insatisfeitos a ponto de darem nota 1?",
  "O que faz um cliente dizer que não volta a comprar?",
  "Quais reclamações indicam falha do vendedor, e não da transportadora?",
  "Quais problemas os clientes dizem que se repetem em mais de uma compra?",
  "Em que parte da entrega os clientes relatam mais problemas: prazo, extravio ou avaria?",
  "O que os clientes relatam quando o pedido é dividido em mais de uma entrega?",
  "Como os clientes descrevem a demora para resolver um problema depois da compra?",
  "O que os clientes dizem quando não conseguem contato com a loja ou o vendedor?",
  "Quais atitudes do vendedor os clientes mais elogiam?",
  "O que os clientes esperavam receber de informação e não receberam?",
  "Quais diferenças entre o anúncio e o produto recebido os clientes mais apontam?",
  "O que os clientes sugerem para melhorar a descrição dos produtos?",
  "O que leva os clientes a recomendarem a loja para outras pessoas?",
  "O que os clientes satisfeitos destacam além da entrega no prazo?",
  "Que tipo de problema faz o cliente falar em Procon, processo ou reclamação pública?",
  "O que os clientes relatam sobre cobranças indevidas ou pagamento não reconhecido?",
];

function normalize(question) {
  return question.trim().toLowerCase();
}

function available(pool, used) {
  const done = new Set(used.map(normalize));
  return pool.filter((question) => !done.has(normalize(question)));
}

// Sorteia até `count` perguntas que ainda não foram sugeridas nem feitas.
// O sorteio pode ser trocado nos testes para dar um resultado previsível.
export function pickSuggestions(pool, used, count, random = Math.random) {
  const options = available(pool, used);
  const picked = [];
  while (picked.length < count && options.length) {
    const index = Math.floor(random() * options.length);
    picked.push(options.splice(index, 1)[0]);
  }
  return picked;
}

export function remainingSuggestions(pool, used) {
  return available(pool, used).length;
}

// Resultado da conferência da chave, feita na rota das categorias, que exige
// a chave e não consome a cota diária
export function keyCheckResult(httpStatus) {
  if (httpStatus === 200) return "ok";
  if (httpStatus === 401) return "invalid";
  if ([0, 502, 503, 504].includes(httpStatus)) return "offline";
  return "error";
}

// Linha no pé de cada resposta: o tamanho da evidência e o limite da leitura
export function evidenceLine(citedCount, uncitedCount) {
  const total = citedCount + uncitedCount;
  if (!total) return null;
  const limit = "Não mede a frequência na base inteira.";
  if (!citedCount) {
    const all = total === 1 ? "A avaliação recuperada não foi citada" : `Nenhuma das ${total} avaliações recuperadas foi citada`;
    return `${all} nesta resposta. ${limit}`;
  }
  const cited = citedCount === 1 ? "1 avaliação citada" : `${citedCount} avaliações citadas`;
  const retrieved = total === 1 ? "1 recuperada" : `${total} recuperadas`;
  return `Baseada em ${cited}, de ${retrieved} para esta pergunta. ${limit}`;
}

export function similarityLabel(value) {
  return `Proximidade com a pergunta: ${formatSimilarity(value)}`;
}

// Texto da resposta para copiar: as citações como [n] e, abaixo, as avaliações
// citadas com o identificador, para a evidência viajar junto
export function answerAsText(result) {
  const lines = result.answer
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
  if (!result.cited.length) return lines.join("\n");
  lines.push("", "Avaliações citadas:");
  for (const review of result.cited) {
    lines.push(
      `[${review.number}] nota ${review.rating}, review_id ${review.review_id}: ${review.original_text}`,
    );
  }
  return lines.join("\n");
}
