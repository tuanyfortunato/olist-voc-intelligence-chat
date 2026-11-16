// Lógica da página que não depende do navegador, testada com o Node em
// tests/frontend/. A montagem da tela fica em app.js.

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

// Categoria do produto como a Olist a nomeia, sem os sublinhados
export function categoryLabel(category) {
  if (!category || category === "desconhecido") return null;
  if (category === "mista") return "Várias categorias";
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

// Resumo dos filtros, como "notas 1 e 2 · Cama mesa banho · entregas com problema"
export function describeFilters(filters) {
  if (!filters) return "";
  const parts = [];
  if (filters.ratings && filters.ratings.length) {
    const list = filters.ratings;
    const joined = list.length === 1 ? `${list[0]}` : `${list.slice(0, -1).join(", ")} e ${list.at(-1)}`;
    parts.push(`${list.length === 1 ? "nota" : "notas"} ${joined}`);
  }
  if (filters.category) parts.push(categoryLabel(filters.category));
  if (filters.delivery) parts.push(DELIVERY_FILTER_LABELS[filters.delivery] || filters.delivery);
  return parts.join(" · ");
}
