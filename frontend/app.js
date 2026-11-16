// Página do chat. Todo texto que vem da API, inclusive os comentários dos
// clientes, entra na tela com textContent, nunca como HTML: um comentário com
// "<script>" aparece escrito, sem ser executado.
import {
  activeFilterCount,
  answerAsText,
  errorLook,
  LOADING_STEPS,
  canRetry,
  currentTheme,
  categoryLabel,
  buildHistory,
  counterState,
  deliveryLabel,
  describeFilters,
  describeInferredRatings,
  errorMessage,
  evidenceLine,
  formatDate,
  MAX_CHARS,
  nextTheme,
  parseAnswerBlocks,
  pickAreaSuggestions,
  remainingSuggestions,
  restrictionNotice,
  similarityLabel,
  citedNumbers,
  quotePreview,
  splitQuotes,
  stripCitations,
  OVERVIEW_AREA,
  SUGGESTION_AREAS,
  SUGGESTIONS,
  statusNotice,
  TIMEOUT_STATUS,
} from "./logic.js";
import { createFilterBar } from "./filters.js";
import { closeOverlay, openOverlay } from "./overlay.js";

// O mesmo nome usado em theme.js, que aplica o tema antes de a página aparecer
const THEME_STORAGE = "olist-theme";
// A pergunta leva de 2 a 5 segundos; 30 segundos já indicam um problema
const REQUEST_TIMEOUT_MS = 30000;
// Com a API desligada, a página volta a conferir de tempos em tempos
const HEALTH_RETRY_MS = 120000;
// Tempo para desfazer uma conversa apagada
const UNDO_MS = 6000;
// Momento em que o texto de carregando passa da busca para a escrita
const LOADING_STEP_MS = 1200;
// Trechos de avaliação mostrados embaixo de cada frase antes do "+N avaliações"
const QUOTES_PER_CLAIM = 2;

const form = document.getElementById("ask-form");
const questionInput = document.getElementById("question");
const sendButton = document.getElementById("send");
const counter = document.getElementById("counter");
const conversation = document.getElementById("conversation");
const welcome = document.getElementById("welcome");
const newChatButton = document.getElementById("new-chat");
const apiStatus = document.getElementById("api-status");
const apiStatusText = document.getElementById("api-status-text");
const announcer = document.getElementById("announcer");
const offlineBanner = document.getElementById("offline-banner");
const undoToast = document.getElementById("undo-toast");
const undoButton = document.getElementById("undo-button");
const aboutButton = document.getElementById("about-button");
const toEndButton = document.getElementById("to-end");
const conversationEnd = document.getElementById("conversation-end");
const exampleButton = document.getElementById("example-button");
const filtersToggle = document.getElementById("filters-toggle");
const filtersCount = document.getElementById("filters-count");
const askForm = document.getElementById("ask-form");

// O campo da pergunta fica fixo no rodapé e muda de altura com o texto e com
// a faixa de filtros. A página reserva no fim o espaço que ele ocupa, para
// ele não cobrir a última resposta nem as sugestões.
const composer = document.querySelector(".composer");
new ResizeObserver(() => {
  document.body.style.setProperty("--composer-height", `${composer.offsetHeight}px`);
}).observe(composer);
const exampleButtons = document.querySelectorAll("#examples button");
const areaPanel = document.getElementById("area-panel");
const areaPanelTitle = document.getElementById("area-panel-title");
const areaQuestions = document.getElementById("area-questions");
const areaClose = document.getElementById("area-close");

let messageCount = 0;
// Trocas desta conversa; ficam só no navegador e somem com "Nova conversa"
let conversationTurns = [];
let busy = false;
// Fica falso quando o /api/health não responde, fora do horário de funcionamento
let online = true;
// Número de comentários na base, vindo do /api/health
let documentCount = null;
const SUGGESTIONS_PER_ROUND = 3;
// Quantas das sugestões de cada rodada vêm da mesma área da pergunta
const SAME_AREA_SUGGESTIONS = 2;
// Perguntas já sugeridas ou feitas nesta conversa, que não voltam a aparecer
let used = [];

function resetUsed() {
  used = [];
}

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

// Ícones de traço simples, montados com createElementNS, sem HTML em texto
const SVG_NS = "http://www.w3.org/2000/svg";
const ICONS = {
  alert: [["path", { d: "M12 3.5 2.5 20h19L12 3.5z" }], ["path", { d: "M12 10v4.5M12 17.5v.01" }]],
  search: [["circle", { cx: "11", cy: "11", r: "6.5" }], ["path", { d: "m16 16 4.5 4.5" }]],
  block: [["circle", { cx: "12", cy: "12", r: "9" }], ["path", { d: "m5.6 5.6 12.8 12.8" }]],
  error: [["circle", { cx: "12", cy: "12", r: "9" }], ["path", { d: "M12 7.5V13M12 16.5v.01" }]],
  clock: [["circle", { cx: "12", cy: "12", r: "9" }], ["path", { d: "M12 7v5l3 2" }]],
  sample: [["path", { d: "M5 4h10l4 4v12H5z" }], ["path", { d: "M9 12h6M9 16h6" }]],
};

function icon(name) {
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("class", "icon notice-icon");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("aria-hidden", "true");
  for (const [tag, attributes] of ICONS[name]) {
    const shape = document.createElementNS(SVG_NS, tag);
    for (const [key, value] of Object.entries(attributes)) shape.setAttribute(key, value);
    svg.appendChild(shape);
  }
  return svg;
}

// Aviso com ícone, título e texto; o ícone e o título não dependem só da cor
function noticeBox(kind, iconName, title, text) {
  const box = element("div", `notice notice-${kind}`);
  box.appendChild(icon(iconName));
  const body = element("div", "notice-body");
  if (title) body.appendChild(element("strong", null, title));
  if (text) body.appendChild(element("span", "notice-text", text));
  box.appendChild(body);
  box.body = body;
  return box;
}

function announce(text) {
  announcer.textContent = "";
  // O texto muda num segundo momento para o leitor de tela anunciar de novo
  requestAnimationFrame(() => {
    announcer.textContent = text;
  });
}

// Com a API desligada, nada na página envia pergunta
function applyLocks() {
  const locked = !online;
  const blocked = busy || locked;
  sendButton.disabled = blocked;
  sendButton.textContent = busy ? "Aguarde..." : "Perguntar";
  questionInput.disabled = locked;
  const waiting = ".suggestion, .more-suggestions, .ask-unfiltered, .retry-button";
  for (const button of areaQuestions.querySelectorAll(".suggestion")) button.disabled = blocked;
  for (const button of conversation.querySelectorAll(waiting)) {
    button.disabled = blocked;
  }
  filterBar.setDisabled(locked);
  filtersToggle.disabled = locked;
  offlineBanner.hidden = online;
  welcome.hidden = conversation.childElementCount > 0;
}

function setBusy(value) {
  busy = value;
  applyLocks();
}

// Cada frase da resposta aparece sem os números [n] e, logo abaixo, com os
// trechos das avaliações que a sustentam. Até QUOTES_PER_CLAIM ficam à
// mostra; as outras abrem pelo botão "+N avaliações".
function appendClaim(parent, text, reviews, messageId) {
  parent.appendChild(element("span", "claim-text", stripCitations(text)));
  const numbers = citedNumbers(text).filter((number) => reviews.has(number));
  if (!numbers.length) return;
  const { shown, hidden } = splitQuotes(numbers, QUOTES_PER_CLAIM);
  const list = element("ul", "quotes");
  list.setAttribute("aria-label", "Avaliações que sustentam esta frase");
  for (const number of shown) list.appendChild(quote(reviews.get(number).review, messageId));
  parent.appendChild(list);
  if (!hidden.length) return;
  const more = element(
    "button",
    "more-quotes",
    `+${hidden.length} ${hidden.length === 1 ? "avaliação" : "avaliações"}`,
  );
  more.type = "button";
  more.addEventListener("click", () => {
    for (const number of hidden) list.appendChild(quote(reviews.get(number).review, messageId));
    more.remove();
    list.children[shown.length].querySelector("button").focus();
  });
  parent.appendChild(more);
}

// Trecho de uma avaliação: o comentário entre aspas, a nota e o número, que
// leva ao cartão completo na lista de baixo
function quote(review, messageId) {
  const item = element("li", "quote");
  item.appendChild(element("q", "quote-text", quotePreview(review.original_text)));
  const meta = element("span", "quote-meta");
  meta.appendChild(stars(review.rating));
  const link = element("button", "quote-link", `Avaliação ${review.number}`);
  link.type = "button";
  link.setAttribute("aria-label", `Ver a avaliação ${review.number} completa`);
  link.addEventListener("click", () => showReview(messageId, review.number));
  meta.appendChild(link);
  item.appendChild(meta);
  return item;
}

function showReview(messageId, number) {
  const card = document.getElementById(`${messageId}-review-${number}`);
  if (!card) return;
  const details = card.closest("details");
  if (details) details.open = true;
  card.scrollIntoView({ behavior: "smooth", block: "center" });
  card.focus({ preventScroll: true });
  card.classList.remove("highlight");
  // Força o navegador a reiniciar a animação quando a mesma citação é clicada de novo
  void card.offsetWidth;
  card.classList.add("highlight");
}

function stars(rating) {
  const wrapper = element("span", "stars");
  wrapper.setAttribute("role", "img");
  wrapper.setAttribute("aria-label", `Nota ${rating} de 5`);
  for (let i = 1; i <= 5; i += 1) {
    // Cheia e vazia mudam de forma, e não só de cor
    const star = element("span", i <= rating ? "star filled" : "star", i <= rating ? "★" : "☆");
    star.setAttribute("aria-hidden", "true");
    wrapper.appendChild(star);
  }
  return wrapper;
}

// No cartão aberto pela citação (preview), o elemento não recebe o id da lista
function reviewCard(review, messageId, cited, { preview = false } = {}) {
  const card = element("article", cited ? "review cited" : "review");
  if (!preview) {
    card.id = `${messageId}-review-${review.number}`;
    card.tabIndex = -1;
  }

  const head = element("div", "review-head");
  head.appendChild(element("span", "review-number", String(review.number)));
  head.appendChild(stars(review.rating));
  const category = categoryLabel(review.category);
  if (category) head.appendChild(element("span", "chip", category));
  const delivery = deliveryLabel(review.delivery);
  if (delivery) head.appendChild(element("span", `chip chip-${delivery.tone}`, delivery.text));
  card.appendChild(head);

  card.appendChild(element("p", "review-text", review.original_text));

  const foot = element("div", "review-foot");
  const date = formatDate(review.review_date);
  if (date) foot.appendChild(element("span", null, `Avaliação de ${date}`));
  foot.appendChild(element("span", null, similarityLabel(review.similarity)));
  // A explicação e o identificador completo ficam no próprio cartão, e não num
  // title, que não aparece no toque nem para leitor de tela
  const toggle = element("button", "review-details-toggle", "Detalhes");
  toggle.type = "button";
  toggle.setAttribute("aria-expanded", "false");
  const details = element("p", "review-details");
  details.hidden = true;
  details.appendChild(
    document.createTextNode(
      "A proximidade vai de 0 a 1: quanto maior, mais o comentário se parece com o tema da pergunta. Identificador da avaliação: ",
    ),
  );
  details.appendChild(element("span", "review-id", review.review_id));
  toggle.addEventListener("click", () => {
    details.hidden = !details.hidden;
    toggle.setAttribute("aria-expanded", String(!details.hidden));
  });
  foot.appendChild(toggle);
  foot.appendChild(details);
  card.appendChild(foot);
  return card;
}

// Bloco de avaliações. As não citadas abrem pelo título ou por uma citação [n].
// Os trechos já aparecem embaixo de cada frase; a lista completa começa recolhida.
function reviewGroup(className, title, reviews, messageId, cited) {
  const details = element("details", `review-group ${className}`);
  details.appendChild(element("summary", null, `${title} (${reviews.length})`));
  for (const review of reviews) details.appendChild(reviewCard(review, messageId, cited));
  return details;
}

function renderReviews(result, messageId) {
  if (!result.cited.length && !result.uncited.length) return null;
  const section = element("section", "reviews");
  section.setAttribute("aria-label", "Avaliações recuperadas");
  if (result.cited.length) {
    section.appendChild(
      reviewGroup(
        "cited-group",
        result.cited.length === 1
          ? "Ver a avaliação usada, com nota, categoria e entrega"
          : "Ver as avaliações usadas, com nota, categoria e entrega",
        result.cited,
        messageId,
        true,
      ),
    );
  }
  if (result.uncited.length) {
    section.appendChild(
      reviewGroup("uncited", "Recuperadas e não citadas", result.uncited, messageId, false),
    );
  }
  return section;
}

// Sugestões de novas perguntas, só embaixo da resposta mais recente
function suggestionButton(question) {
  const button = element("button", "suggestion", question);
  button.type = "button";
  button.disabled = busy;
  button.addEventListener("click", () => startQuestion(question));
  return button;
}

// Acrescenta perguntas ao bloco, puxando pela área da pergunta feita, e esconde o botão quando a lista acaba
function addSuggestions(list, moreButton, question) {
  const questions = pickAreaSuggestions(question, used, SUGGESTIONS_PER_ROUND, SAME_AREA_SUGGESTIONS);
  used.push(...questions);
  for (const question of questions) list.appendChild(suggestionButton(question));
  moreButton.hidden = remainingSuggestions(SUGGESTIONS, used) === 0;
  return questions.length;
}

function renderSuggestions(container) {
  for (const old of conversation.querySelectorAll(".suggestions")) old.remove();
  if (!remainingSuggestions(SUGGESTIONS, used)) return;
  const box = element("div", "suggestions");
  box.setAttribute("aria-label", "Outras perguntas");
  box.appendChild(element("p", "suggestions-title", "Outras perguntas"));
  const list = element("div", "suggestion-list");
  box.appendChild(list);
  const more = element("button", "more-suggestions", "Mais sugestões");
  more.type = "button";
  more.addEventListener("click", () => {
    const first = list.children.length;
    if (addSuggestions(list, more, container.question)) list.children[first].focus();
  });
  addSuggestions(list, more, container.question);
  box.appendChild(more);
  container.after(box);
}

// Copia a resposta com as avaliações citadas, para levar a um e-mail ou relatório
function copyButton(result) {
  const button = element("button", "copy-button", "Copiar");
  button.type = "button";
  button.setAttribute("aria-label", "Copiar a resposta com as avaliações citadas");
  button.addEventListener("click", async () => {
    let label = "Copiado";
    try {
      await navigator.clipboard.writeText(answerAsText(result));
    } catch {
      label = "Não foi possível copiar";
    }
    button.textContent = label;
    announce(label);
    setTimeout(() => {
      button.textContent = "Copiar";
    }, 2000);
  });
  return button;
}

function renderAnswer(container, result, messageId) {
  container.replaceChildren();
  container.removeAttribute("aria-busy");
  if (container.example) container.appendChild(exampleNote());
  const notice = statusNotice(result.status);
  // Sem resposta (fora do escopo, sem evidência), o aviso traz o próprio texto
  // da API, num bloco só, e não há o que copiar
  const answerless = notice && notice.replacesAnswer;
  if (notice) {
    const box = noticeBox(
      notice.kind,
      notice.icon,
      notice.title,
      answerless ? result.answer : notice.text,
    );
    // Com filtros, a falta de evidência pode ser só o recorte escolhido
    const restriction = restrictionNotice(result.status, container.filters);
    if (restriction) {
      box.body.appendChild(element("span", "notice-restriction", `${restriction}.`));
      const unfiltered = element("button", "retry-button ask-unfiltered", "Perguntar sem filtros");
      unfiltered.type = "button";
      unfiltered.addEventListener("click", () =>
        startQuestion(container.question, { filters: null }),
      );
      box.body.appendChild(unfiltered);
    }
    container.appendChild(box);
  }
  if (answerless) return;
  // As notas marcadas na faixa valem mais do que as citadas na pergunta; nesse
  // caso a API não deduz nada, e o balão da pergunta já mostra as usadas
  const chosenRatings = container.filters && container.filters.ratings;
  const inferred = chosenRatings ? null : describeInferredRatings(result.inferred_ratings);
  if (inferred) container.appendChild(element("p", "inferred-filter", inferred));
  const reviews = new Map();
  for (const review of result.cited) reviews.set(review.number, { review, cited: true });
  for (const review of result.uncited) reviews.set(review.number, { review, cited: false });
  const answer = element("div", "answer");
  for (const block of parseAnswerBlocks(result.answer)) {
    if (block.type === "paragraph") {
      const paragraph = element("div", "claim");
      appendClaim(paragraph, block.text, reviews, messageId);
      answer.appendChild(paragraph);
    } else {
      const list = element("ul", "claims");
      for (const item of block.items) {
        const li = element("li", "claim");
        appendClaim(li, item, reviews, messageId);
        list.appendChild(li);
      }
      answer.appendChild(list);
    }
  }
  container.appendChild(answer);
  const evidence = evidenceLine(result.cited.length, result.uncited.length);
  if (evidence) container.appendChild(element("p", "evidence-line", evidence));
  if (!container.example) container.appendChild(copyButton(result));
  const reviewList = renderReviews(result, messageId);
  if (reviewList) container.appendChild(reviewList);
}

function renderError(container, error, question) {
  container.replaceChildren();
  container.removeAttribute("aria-busy");
  // O limite de perguntas não é uma falha: ganha um aviso amarelo, sem botão
  const look = errorLook(error.kind);
  const box = noticeBox(look.kind, look.icon, look.title, error.message);
  if (canRetry(error.kind)) {
    const retry = element("button", "retry-button", "Tentar de novo");
    retry.type = "button";
    retry.addEventListener("click", () => send(question, container));
    box.body.appendChild(retry);
  }
  container.appendChild(box);
  if (error.kind === "offline") checkApi();
}

function renderLoading(container) {
  container.replaceChildren();
  container.setAttribute("aria-busy", "true");
  const loading = element("div", "loading");
  const dots = element("span", "dots");
  dots.setAttribute("aria-hidden", "true");
  for (let i = 0; i < 3; i += 1) dots.appendChild(element("span"));
  loading.appendChild(dots);
  const step = element("span", null, LOADING_STEPS[0]);
  loading.appendChild(step);
  container.appendChild(loading);
  // A busca leva cerca de um segundo; depois disso o modelo escreve a resposta
  const timer = setTimeout(() => {
    if (step.isConnected) step.textContent = LOADING_STEPS[1];
  }, LOADING_STEP_MS);
  container.loadingTimer = timer;
}

async function callApi(question, filters, history) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(filters ? { question, history, filters } : { question, history }),
      signal: controller.signal,
    });
    const body = await response.json().catch(() => null);
    return { status: response.status, body };
  } catch (error) {
    return { status: error.name === "AbortError" ? TIMEOUT_STATUS : 0, body: null };
  } finally {
    clearTimeout(timer);
  }
}

// Envia a pergunta e escreve o resultado no balão da resposta. A nova
// tentativa usa o mesmo balão, sem repetir a pergunta na conversa.
async function send(question, reply) {
  if (busy) return;
  closeOverlay();

  setBusy(true);
  renderLoading(reply);
  // Os filtros ficam no balão: a nova tentativa usa os mesmos da pergunta original
  const { status, body } = await callApi(question, reply.filters || null, reply.history || []);
  setBusy(false);
  clearTimeout(reply.loadingTimer);

  const messageId = reply.dataset.messageId;
  if (status === 200 && body) {
    renderAnswer(reply, body, messageId);
    reply.turns.push({ question, answer: body.answer });
    // Se a pessoa saiu da conversa enquanto esperava, as sugestões ficam para quando ela voltar
    if (reply.isConnected) renderSuggestions(reply);
    announce("Resposta pronta.");
  } else {
    const error = errorMessage(status, body);
    renderError(reply, error, question);
    announce(error.message);
  }
  // Rola até a pergunta, para a resposta ser lida desde o começo
  reply.parentElement.scrollIntoView({ behavior: "smooth", block: "start" });
}

// Sem filtros explícitos, a pergunta usa os que estão ativos na faixa
function startQuestion(question, options = {}) {
  if (busy || !online) return false;
  discardUndo();
  closeArea();
  welcome.hidden = true;
  newChatButton.hidden = false;
  used.push(question);
  enterChat();

  messageCount += 1;
  const filters = options.filters !== undefined ? options.filters : filterBar.current();
  const turn = element("div", "turn");
  // Título oculto, para quem navega pelos títulos com leitor de tela
  turn.appendChild(element("h2", "visually-hidden", `Pergunta: ${question}`));
  const userMessage = element("div", "message-user", question);
  if (filters) userMessage.appendChild(element("span", "message-filters", `Filtros: ${describeFilters(filters)}`));
  turn.appendChild(userMessage);
  const reply = element("div", "message-bot");
  reply.dataset.messageId = `m${messageCount}`;
  reply.filters = filters;
  reply.question = question;
  // O histórico também fica no balão, para a nova tentativa mandar o mesmo
  reply.history = buildHistory(conversationTurns);
  reply.turns = conversationTurns;
  turn.appendChild(reply);
  conversation.appendChild(turn);
  send(question, reply);
  return true;
}

function updateComposer() {
  const length = questionInput.value.length;
  counter.textContent = `${length}/${MAX_CHARS}`;
  counter.dataset.state = counterState(length);
  // O campo cresce com o texto até o limite definido no CSS
  questionInput.style.height = "auto";
  questionInput.style.height = `${questionInput.scrollHeight}px`;
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const question = questionInput.value.trim();
  if (!question) return;
  // A pergunta só sai do campo depois de enviada
  if (startQuestion(question)) {
    questionInput.value = "";
    updateComposer();
  }
});

// Enter envia; Shift+Enter quebra a linha
questionInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    form.requestSubmit();
  }
});

questionInput.addEventListener("input", updateComposer);

// Cada cartão da tela inicial é uma área: o clique mostra as perguntas dela
// para a pessoa escolher, e um segundo clique no mesmo cartão as esconde
let openArea = null;

function closeArea() {
  openArea = null;
  areaPanel.hidden = true;
  areaQuestions.replaceChildren();
  for (const button of exampleButtons) button.setAttribute("aria-expanded", "false");
}

function showArea(name) {
  const group = SUGGESTION_AREAS.find((item) => item.area === name);
  if (!group) return;
  openArea = name;
  for (const button of exampleButtons) {
    button.setAttribute("aria-expanded", String(button.dataset.area === name));
  }
  areaPanelTitle.textContent = name === OVERVIEW_AREA ? "Perguntas de visão geral" : `Perguntas de ${name}`;
  areaQuestions.replaceChildren(...group.questions.map(suggestionButton));
  areaPanel.hidden = false;
  applyLocks();
  areaPanel.scrollIntoView({ behavior: "smooth", block: "nearest" });
  areaPanelTitle.focus({ preventScroll: true });
}

for (const button of exampleButtons) {
  button.addEventListener("click", () => {
    if (openArea === button.dataset.area) {
      closeArea();
      return;
    }
    showArea(button.dataset.area);
  });
}

areaClose.addEventListener("click", () => {
  const name = openArea;
  closeArea();
  const card = [...exampleButtons].find((button) => button.dataset.area === name);
  if (card) card.focus();
});

// A conversa ganha uma entrada no histórico do navegador. Assim o botão voltar
// do navegador ou do celular leva de volta à tela inicial, em vez de sair do site.
function enterChat() {
  if (history.state && history.state.view === "chat") return;
  history.pushState({ view: "chat" }, "");
}

window.addEventListener("popstate", (event) => {
  const view = event.state && event.state.view;
  if (view === "chat") {
    // Avançar depois de voltar: recupera a conversa, se ainda dá para desfazer
    if (!conversation.childElementCount && !restoreConversation()) history.replaceState(null, "");
    return;
  }
  if (conversation.childElementCount) clearConversation();
});

// "Nova conversa" guarda o que apagou por alguns segundos, para dar tempo de desfazer
let undoState = null;
let undoTimer = null;

function discardUndo() {
  clearTimeout(undoTimer);
  undoState = null;
  undoToast.hidden = true;
}

// Apaga a conversa e volta à tela inicial, guardando o que apagou para desfazer
let focusAfterClear = false;

function clearConversation() {
  closeOverlay();
  discardUndo();
  undoState = {
    nodes: [...conversation.childNodes],
    turns: conversationTurns,
    used,
    filters: filterBar.current(),
  };
  conversation.replaceChildren();
  conversationTurns = [];
  filterBar.clear();
  resetUsed();
  newChatButton.hidden = true;
  applyLocks();
  undoToast.hidden = false;
  undoTimer = setTimeout(discardUndo, UNDO_MS);
  window.scrollTo({ top: 0, behavior: "smooth" });
  // Pelo botão, o foco vai para o campo; pelo voltar do celular, não abre o teclado
  if (focusAfterClear) questionInput.focus({ preventScroll: true });
  focusAfterClear = false;
}

// O botão "Nova conversa" volta uma entrada no histórico, como o voltar do
// navegador; os dois caminhos apagam a conversa no mesmo lugar
newChatButton.addEventListener("click", () => {
  if (busy) return;
  focusAfterClear = true;
  if (history.state && history.state.view === "chat") history.back();
  else clearConversation();
});

function restoreConversation() {
  if (!undoState) return false;
  conversation.replaceChildren(...undoState.nodes);
  conversationTurns = undoState.turns;
  used = undoState.used;
  filterBar.restore(undoState.filters);
  newChatButton.hidden = false;
  discardUndo();
  applyLocks();
  announce("Conversa recuperada.");
  conversation.lastElementChild.scrollIntoView({ behavior: "smooth", block: "start" });
  return true;
}

undoButton.addEventListener("click", () => {
  if (restoreConversation()) enterChat();
});

const themeToggle = document.getElementById("theme-toggle");
const themeLabel = document.getElementById("theme-label");
const systemDark = window.matchMedia("(prefers-color-scheme: dark)");

// O botão mostra o tema para o qual a página vai mudar
function updateThemeButton() {
  const theme = currentTheme(document.documentElement.dataset.theme, systemDark.matches);
  const target = nextTheme(theme);
  themeLabel.textContent = target === "dark" ? "Tema escuro" : "Tema claro";
  themeToggle.dataset.target = target;
  const action = `Mudar para o tema ${target === "dark" ? "escuro" : "claro"}`;
  themeToggle.setAttribute("aria-label", action);
  themeToggle.title = action;
}

themeToggle.addEventListener("click", () => {
  const theme = nextTheme(currentTheme(document.documentElement.dataset.theme, systemDark.matches));
  document.documentElement.dataset.theme = theme;
  try {
    localStorage.setItem(THEME_STORAGE, theme);
  } catch {
    // sem armazenamento, o tema vale até a página ser recarregada
  }
  updateThemeButton();
});

// Sem escolha salva, a página acompanha a troca de tema do sistema
systemDark.addEventListener("change", updateThemeButton);

let healthTimer = null;

async function checkApi() {
  clearTimeout(healthTimer);
  online = false;
  try {
    const response = await fetch("/api/health");
    const data = await response.json().catch(() => null);
    if (response.ok && data) {
      online = true;
      documentCount = data.documents;
      apiStatus.title = `No ar, com ${data.documents.toLocaleString("pt-BR")} avaliações`;
    } else {
      apiStatus.title = errorMessage(response.status, data).message;
    }
  } catch {
    apiStatus.title = errorMessage(0, null).message;
  }
  // O selo mostra só a situação; o detalhe fica no title e no aviso da página
  apiStatusText.textContent = online ? "No ar" : "Fora do ar";
  apiStatus.dataset.state = online ? "online" : "offline";
  applyLocks();
  if (!online) healthTimer = setTimeout(checkApi, HEALTH_RETRY_MS);
}

aboutButton.addEventListener("click", () => {
  const content = document.getElementById("about-template").content.cloneNode(true);
  const count = content.querySelector(".about-count");
  if (documentCount) {
    count.textContent = `O chat busca em ${documentCount.toLocaleString("pt-BR")} comentários de clientes.`;
  }
  const wrapper = element("div");
  wrapper.appendChild(content);
  openOverlay({ anchor: aboutButton, title: "Sobre os dados", content: wrapper });
});

// "Ir para o fim" aparece quando falta bastante conversa abaixo do que está na tela
const TO_END_DISTANCE = 400;
function updateToEnd() {
  const below = document.documentElement.scrollHeight - (window.scrollY + window.innerHeight);
  toEndButton.hidden = conversation.childElementCount === 0 || below < TO_END_DISTANCE;
}
window.addEventListener("scroll", updateToEnd, { passive: true });
new ResizeObserver(updateToEnd).observe(conversation);
toEndButton.addEventListener("click", () => {
  conversationEnd.scrollIntoView({ behavior: "smooth", block: "end" });
});

// No celular a faixa de filtros fica recolhida atrás do botão "Filtros",
// que mostra quantos estão ativos
function updateFiltersToggle(filters) {
  const count = activeFilterCount(filters);
  filtersCount.hidden = count === 0;
  filtersCount.textContent = String(count);
  filtersToggle.dataset.active = String(count > 0);
  filtersToggle.setAttribute(
    "aria-label",
    count ? `Filtros, ${count} ${count === 1 ? "ativo" : "ativos"}` : "Filtros",
  );
}

filtersToggle.addEventListener("click", () => {
  const open = askForm.dataset.filtersOpen !== "true";
  askForm.dataset.filtersOpen = String(open);
  filtersToggle.setAttribute("aria-expanded", String(open));
});

const filterBar = createFilterBar({
  container: document.getElementById("filter-bar"),
  announce,
  onChange: updateFiltersToggle,
});

// Fora do horário, uma resposta real gravada mostra o que o chat faz
exampleButton.addEventListener("click", async () => {
  exampleButton.disabled = true;
  try {
    const response = await fetch("exemplo.json");
    if (!response.ok) throw new Error(String(response.status));
    const result = await response.json();
    showExample(result);
  } catch {
    announce("Não foi possível carregar o exemplo.");
  } finally {
    exampleButton.disabled = false;
  }
});

function showExample(result) {
  closeOverlay();
  discardUndo();
  conversation.replaceChildren();
  conversationTurns = [];
  closeArea();
  welcome.hidden = true;
  enterChat();
  messageCount += 1;
  const turn = element("div", "turn");
  turn.appendChild(element("h2", "visually-hidden", `Exemplo: ${result.original_question}`));
  turn.appendChild(element("div", "message-user", result.original_question));
  const reply = element("div", "message-bot");
  reply.dataset.messageId = `m${messageCount}`;
  reply.example = true;
  turn.appendChild(reply);
  conversation.appendChild(turn);
  renderAnswer(reply, result, reply.dataset.messageId);
  newChatButton.hidden = false;
  applyLocks();
  announce("Resposta de exemplo aberta.");
  turn.scrollIntoView({ behavior: "smooth", block: "start" });
}

function exampleNote() {
  return noticeBox(
    "sample",
    "sample",
    "Resposta de exemplo",
    "Gravada numa rodada de avaliação do projeto. Com o chat no ar, as respostas trazem também a categoria, a data e a entrega de cada avaliação.",
  );
}

// Ao recarregar a página no meio de uma conversa, ela começa de novo na tela inicial
if (history.state && history.state.view === "chat") history.replaceState(null, "");
resetUsed();
updateThemeButton();
updateComposer();
applyLocks();
checkApi();
