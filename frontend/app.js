// Página do chat. Todo texto que vem da API, inclusive os comentários dos
// clientes, entra na tela com textContent, nunca como HTML: um comentário com
// "<script>" aparece escrito, sem ser executado.
import {
  answerAsText,
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
  keyCheckResult,
  MAX_CHARS,
  nextTheme,
  parseAnswerBlocks,
  pickSuggestions,
  remainingSuggestions,
  restrictionNotice,
  similarityLabel,
  splitCitations,
  SUGGESTIONS,
  statusNotice,
  TIMEOUT_STATUS,
} from "./logic.js";
import { createFilterBar } from "./filters.js";
import { closeOverlay, openOverlay } from "./overlay.js";

const KEY_STORAGE = "olist-voc-access-key";
// O mesmo nome usado em theme.js, que aplica o tema antes de a página aparecer
const THEME_STORAGE = "olist-theme";
// A pergunta leva de 2 a 5 segundos; 30 segundos já indicam um problema
const REQUEST_TIMEOUT_MS = 30000;
// Com a API desligada, a página volta a conferir de tempos em tempos
const HEALTH_RETRY_MS = 120000;
// Tempo para desfazer uma conversa apagada
const UNDO_MS = 6000;

const keyInput = document.getElementById("access-key");
const keyError = document.getElementById("key-error");
const toggleKey = document.getElementById("toggle-key");
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
const keyGate = document.getElementById("key-gate");
const keySubmit = document.getElementById("key-submit");
const keyCancel = document.getElementById("key-cancel");
const changeKeyButton = document.getElementById("change-key");
const offlineBanner = document.getElementById("offline-banner");
const undoToast = document.getElementById("undo-toast");
const undoButton = document.getElementById("undo-button");
const aboutButton = document.getElementById("about-button");
const toEndButton = document.getElementById("to-end");
const conversationEnd = document.getElementById("conversation-end");

// O campo da pergunta fica fixo no rodapé e muda de altura com o texto e com
// a faixa de filtros. A página reserva no fim o espaço que ele ocupa, para
// ele não cobrir a última resposta nem as sugestões.
const composer = document.querySelector(".composer");
new ResizeObserver(() => {
  document.body.style.setProperty("--composer-height", `${composer.offsetHeight}px`);
}).observe(composer);
const exampleButtons = document.querySelectorAll("#examples button");

let messageCount = 0;
// Trocas desta conversa; ficam só no navegador e somem com "Nova conversa"
let conversationTurns = [];
let busy = false;
// Chave já conferida; sem ela, a página mostra só o cartão de entrada
let accessKey = "";
// Fica falso quando o /api/health não responde, fora do horário de funcionamento
let online = true;
// Número de comentários na base, vindo do /api/health
let documentCount = null;
const SUGGESTIONS_PER_ROUND = 3;
// Perguntas já sugeridas ou feitas nesta conversa, que não voltam a aparecer.
// Os exemplos da tela inicial contam como já sugeridos.
let used = [];

function resetUsed() {
  used = [...exampleButtons].map((button) =>
    button.querySelector(".example-question").textContent.trim(),
  );
}

// A chave fica só enquanto a aba estiver aberta. Em navegação privada o
// armazenamento pode falhar, e a página continua funcionando sem ele.
function loadKey() {
  try {
    return sessionStorage.getItem(KEY_STORAGE) || "";
  } catch {
    return "";
  }
}

function saveKey(value) {
  try {
    if (value) sessionStorage.setItem(KEY_STORAGE, value);
    else sessionStorage.removeItem(KEY_STORAGE);
  } catch {
    // sem armazenamento, a chave vale até a página ser recarregada
  }
}

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function announce(text) {
  announcer.textContent = "";
  // O texto muda num segundo momento para o leitor de tela anunciar de novo
  requestAnimationFrame(() => {
    announcer.textContent = text;
  });
}

// Sem chave ou com a API desligada, nada na página envia pergunta
function applyLocks() {
  const locked = !accessKey || !online;
  const blocked = busy || locked;
  sendButton.disabled = blocked;
  sendButton.textContent = busy ? "Aguarde..." : "Perguntar";
  questionInput.disabled = locked;
  for (const button of exampleButtons) button.disabled = blocked;
  const waiting = ".suggestion, .more-suggestions, .ask-unfiltered, .retry-button";
  for (const button of conversation.querySelectorAll(waiting)) {
    button.disabled = blocked;
  }
  filterBar.setDisabled(locked);
  offlineBanner.hidden = online;
  changeKeyButton.hidden = !accessKey || !keyGate.hidden;
  welcome.hidden = !keyGate.hidden || conversation.childElementCount > 0;
}

function setBusy(value) {
  busy = value;
  applyLocks();
}

function showKeyError(message) {
  keyInput.classList.add("invalid");
  keyInput.setAttribute("aria-invalid", "true");
  keyError.textContent = message;
  keyError.hidden = false;
}

function clearKeyError() {
  keyInput.classList.remove("invalid");
  keyInput.removeAttribute("aria-invalid");
  keyError.hidden = true;
}

// Cartão de entrada. "Trocar a chave" reabre o cartão sem apagar a conversa,
// e por isso pode ser cancelado; sem chave nenhuma, não.
function showGate(message, { cancel = false } = {}) {
  closeOverlay();
  keyGate.hidden = false;
  keyCancel.hidden = !cancel;
  if (message) showKeyError(message);
  else clearKeyError();
  applyLocks();
  window.scrollTo({ top: 0 });
  keyInput.focus();
}

function hideGate() {
  keyGate.hidden = true;
  keyInput.value = "";
  clearKeyError();
  applyLocks();
}

// A rota das categorias exige a chave e não consome a cota diária
async function checkKey(key) {
  try {
    const response = await fetch("/api/categories", { headers: { "X-Access-Key": key } });
    return keyCheckResult(response.status);
  } catch {
    return keyCheckResult(0);
  }
}

function rejectKey() {
  accessKey = "";
  saveKey("");
  showGate("Chave de acesso inválida. Confira e tente de novo.");
}

const KEY_MESSAGES = {
  invalid: "Chave de acesso inválida. Confira e tente de novo.",
  offline: errorMessage(0, null).message,
  error: "Não foi possível conferir a chave. Tente de novo.",
};

async function submitKey() {
  const key = keyInput.value.trim();
  if (!key) {
    showKeyError("Digite a chave de acesso.");
    keyInput.focus();
    return;
  }
  keySubmit.disabled = true;
  keySubmit.textContent = "Conferindo...";
  const result = await checkKey(key);
  keySubmit.disabled = false;
  keySubmit.textContent = "Entrar";
  if (result !== "ok") {
    showKeyError(KEY_MESSAGES[result]);
    keyInput.focus();
    return;
  }
  accessKey = key;
  saveKey(key);
  hideGate();
  // Uma chave nova pode trazer outra lista de categorias
  filterBar.reloadCategories();
  announce("Chave aceita.");
  questionInput.focus();
}

// Texto com as citações [n] transformadas em botões que levam à avaliação
function appendWithCitations(parent, text, messageId) {
  for (const part of splitCitations(text)) {
    if (part.type === "text") {
      parent.appendChild(document.createTextNode(part.value));
      continue;
    }
    for (const number of part.numbers) {
      const button = element("button", "cite", String(number));
      button.type = "button";
      button.setAttribute("aria-label", `Ver a avaliação ${number}`);
      button.title = `Ver a avaliação ${number}`;
      button.setAttribute("aria-haspopup", "dialog");
      button.addEventListener("click", () => previewReview(button, messageId, number));
      parent.appendChild(button);
    }
  }
}

// Mostra a avaliação citada ao lado da citação, sem tirar a resposta da tela
let openPreview = null;

function previewReview(button, messageId, number) {
  if (openPreview && openPreview.button === button && openPreview.handle.isOpen) {
    openPreview.handle.close();
    return;
  }
  const reply = conversation.querySelector(`[data-message-id="${messageId}"]`);
  const entry = reply && reply.reviews ? reply.reviews.get(number) : null;
  if (!entry) return;
  const content = element("div", "cite-preview");
  content.appendChild(reviewCard(entry.review, messageId, entry.cited, { preview: true }));
  const link = element("button", "cite-preview-link", "Ver na lista");
  link.type = "button";
  link.addEventListener("click", () => {
    handle.close({ restoreFocus: false });
    showReview(messageId, number);
  });
  content.appendChild(link);
  const handle = openOverlay({ anchor: button, title: `Avaliação ${number}`, content });
  openPreview = { button, handle };
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
    const star = element("span", i <= rating ? "star filled" : "star", "★");
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

// Bloco recolhido de avaliações. Abre pelo clique no título ou numa citação [n].
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
      reviewGroup("cited-group", "Avaliações citadas", result.cited, messageId, true),
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

// Acrescenta perguntas sorteadas ao bloco e esconde o botão quando a lista acaba
function addSuggestions(list, moreButton) {
  const questions = pickSuggestions(SUGGESTIONS, used, SUGGESTIONS_PER_ROUND);
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
    if (addSuggestions(list, more)) list.children[first].focus();
  });
  addSuggestions(list, more);
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
  const notice = statusNotice(result.status);
  if (notice) {
    const box = element("div", `notice notice-${notice.kind}`);
    box.appendChild(element("strong", null, notice.title));
    box.appendChild(element("span", null, notice.text));
    // Com filtros, a falta de evidência pode ser só o recorte escolhido
    const restriction = restrictionNotice(result.status, container.filters);
    if (restriction) {
      box.appendChild(element("span", "notice-restriction", `${restriction}.`));
      const unfiltered = element("button", "retry-button ask-unfiltered", "Perguntar sem filtros");
      unfiltered.type = "button";
      unfiltered.addEventListener("click", () =>
        startQuestion(container.question, { filters: null }),
      );
      box.appendChild(unfiltered);
    }
    container.appendChild(box);
  }
  // As notas marcadas na faixa valem mais do que as citadas na pergunta; nesse
  // caso a API não deduz nada, e o balão da pergunta já mostra as usadas
  const chosenRatings = container.filters && container.filters.ratings;
  const inferred = chosenRatings ? null : describeInferredRatings(result.inferred_ratings);
  if (inferred) container.appendChild(element("p", "inferred-filter", inferred));
  const answer = element("div", "answer");
  for (const block of parseAnswerBlocks(result.answer)) {
    if (block.type === "paragraph") {
      const paragraph = element("p");
      appendWithCitations(paragraph, block.text, messageId);
      answer.appendChild(paragraph);
    } else {
      const list = element("ul");
      for (const item of block.items) {
        const li = element("li");
        appendWithCitations(li, item, messageId);
        list.appendChild(li);
      }
      answer.appendChild(list);
    }
  }
  container.appendChild(answer);
  const evidence = evidenceLine(result.cited.length, result.uncited.length);
  if (evidence) container.appendChild(element("p", "evidence-line", evidence));
  container.appendChild(copyButton(result));
  // As avaliações ficam no balão, para o cartão aberto por uma citação
  container.reviews = new Map();
  for (const review of result.cited) container.reviews.set(review.number, { review, cited: true });
  for (const review of result.uncited) container.reviews.set(review.number, { review, cited: false });
  const reviews = renderReviews(result, messageId);
  if (reviews) container.appendChild(reviews);
}

function renderError(container, error, question) {
  container.replaceChildren();
  container.removeAttribute("aria-busy");
  const box = element("div", "notice notice-error");
  box.appendChild(element("span", null, error.message));
  if (canRetry(error.kind)) {
    const retry = element("button", "retry-button", "Tentar de novo");
    retry.type = "button";
    retry.addEventListener("click", () => send(question, container));
    box.appendChild(retry);
  }
  container.appendChild(box);
  if (error.kind === "key") rejectKey();
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
  loading.appendChild(element("span", null, "Buscando nas avaliações e escrevendo a resposta..."));
  container.appendChild(loading);
}

async function callApi(question, key, filters, history) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Access-Key": key },
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
  if (!accessKey) {
    showGate();
    return;
  }
  const key = accessKey;
  closeOverlay();

  setBusy(true);
  renderLoading(reply);
  // Os filtros ficam no balão: a nova tentativa usa os mesmos da pergunta original
  const { status, body } = await callApi(question, key, reply.filters || null, reply.history || []);
  setBusy(false);

  const messageId = reply.dataset.messageId;
  if (status === 200 && body) {
    renderAnswer(reply, body, messageId);
    conversationTurns.push({ question, answer: body.answer });
    renderSuggestions(reply);
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
  if (!accessKey) {
    showGate();
    return false;
  }
  discardUndo();
  welcome.hidden = true;
  newChatButton.hidden = false;
  used.push(question);

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

document.getElementById("key-form").addEventListener("submit", (event) => {
  event.preventDefault();
  submitKey();
});
keyCancel.addEventListener("click", () => {
  hideGate();
  changeKeyButton.focus();
});
changeKeyButton.addEventListener("click", () => showGate("", { cancel: true }));
keyInput.addEventListener("input", clearKeyError);

toggleKey.addEventListener("click", () => {
  const show = keyInput.type === "password";
  keyInput.type = show ? "text" : "password";
  toggleKey.textContent = show ? "Ocultar" : "Mostrar";
  toggleKey.setAttribute("aria-label", show ? "Ocultar a chave" : "Mostrar a chave");
  toggleKey.setAttribute("aria-pressed", String(show));
});

for (const button of exampleButtons) {
  button.addEventListener("click", () => {
    const question = button.querySelector(".example-question").textContent.trim();
    startQuestion(question);
  });
}

// "Nova conversa" guarda o que apagou por alguns segundos, para dar tempo de desfazer
let undoState = null;
let undoTimer = null;

function discardUndo() {
  clearTimeout(undoTimer);
  undoState = null;
  undoToast.hidden = true;
}

newChatButton.addEventListener("click", () => {
  if (busy) return;
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
  questionInput.focus();
});

undoButton.addEventListener("click", () => {
  if (!undoState) return;
  conversation.replaceChildren(...undoState.nodes);
  conversationTurns = undoState.turns;
  used = undoState.used;
  filterBar.restore(undoState.filters);
  newChatButton.hidden = false;
  discardUndo();
  applyLocks();
  announce("Conversa recuperada.");
  conversation.lastElementChild.scrollIntoView({ behavior: "smooth", block: "start" });
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
      apiStatusText.textContent = `No ar, com ${data.documents.toLocaleString("pt-BR")} avaliações`;
    } else {
      apiStatusText.textContent = errorMessage(response.status, data).message;
    }
  } catch {
    apiStatusText.textContent = errorMessage(0, null).message;
  }
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

const filterBar = createFilterBar({
  container: document.getElementById("filter-bar"),
  getKey: () => accessKey,
  focusKey: () => showGate(),
  announce,
});

// Com uma chave guardada, a página abre direto e confere a chave em segundo
// plano; sem chave, abre no cartão de entrada.
accessKey = loadKey();
resetUsed();
updateThemeButton();
updateComposer();
if (accessKey) {
  hideGate();
  checkKey(accessKey).then((result) => {
    if (result === "invalid") rejectKey();
  });
} else {
  showGate();
}
checkApi();
