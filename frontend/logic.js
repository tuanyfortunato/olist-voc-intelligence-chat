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
  return blocks;
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

// Mensagem para cada erro da API. O ALB devolve 502, 503 ou 504 sem corpo JSON
// quando a API está desligada; o 503 com JSON é um problema passageiro do Bedrock.
export function errorMessage(httpStatus, body) {
  const detail = body && typeof body.detail === "string" ? body.detail : null;
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

export function formatSimilarity(value) {
  return value.toFixed(2).replace(".", ",");
}
