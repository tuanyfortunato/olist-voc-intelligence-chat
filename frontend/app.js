// Página do chat. Todo texto que vem da API, inclusive os comentários dos
// clientes, entra na tela com textContent, nunca como HTML: um comentário com
// "<script>" aparece escrito, sem ser executado.
import {
  canRetry,
  categoryLabel,
  buildFilters,
  buildHistory,
  counterState,
  deliveryLabel,
  describeFilters,
  describeInferredRatings,
  errorMessage,
  formatDate,
  formatSimilarity,
  MAX_CHARS,
  parseAnswerBlocks,
  shortId,
  splitCitations,
  statusNotice,
  TIMEOUT_STATUS,
} from "./logic.js";

const KEY_STORAGE = "olist-voc-access-key";
// A pergunta leva de 2 a 5 segundos; 30 segundos já indicam um problema
const REQUEST_TIMEOUT_MS = 30000;
// Com a API desligada, a página volta a conferir de tempos em tempos
const HEALTH_RETRY_MS = 120000;

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
const exampleButtons = document.querySelectorAll("#examples button");
const filtersPanel = document.getElementById("filters");
const filtersSummary = document.getElementById("filters-summary");
const ratingInputs = document.querySelectorAll('input[name="rating"]');
const categorySelect = document.getElementById("filter-category");
const deliverySelect = document.getElementById("filter-delivery");
const clearFiltersButton = document.getElementById("clear-filters");

let messageCount = 0;
// Trocas desta conversa; ficam só no navegador e somem com "Nova conversa"
let conversationTurns = [];
let busy = false;

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
    sessionStorage.setItem(KEY_STORAGE, value);
  } catch {
    // sem armazenamento, a chave fica só no campo
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

function setBusy(value) {
  busy = value;
  sendButton.disabled = value;
  sendButton.textContent = value ? "Aguarde..." : "Perguntar";
  for (const button of exampleButtons) button.disabled = value;
}

function showKeyError(message) {
  keyInput.classList.add("invalid");
  keyInput.setAttribute("aria-invalid", "true");
  keyError.textContent = message;
  keyError.hidden = false;
  keyInput.focus();
}

function clearKeyError() {
  keyInput.classList.remove("invalid");
  keyInput.removeAttribute("aria-invalid");
  keyError.hidden = true;
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
      button.addEventListener("click", () => showReview(messageId, number));
      parent.appendChild(button);
    }
  }
}

function showReview(messageId, number) {
  const card = document.getElementById(`${messageId}-review-${number}`);
  if (!card) return;
  const details = card.closest("details");
  if (details) details.open = true;
  card.scrollIntoView({ behavior: "smooth", block: "center" });
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

function reviewCard(review, messageId, cited) {
  const card = element("article", cited ? "review cited" : "review");
  card.id = `${messageId}-review-${review.number}`;
  card.tabIndex = -1;

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
  const similarity = element("span", null, `Similaridade ${formatSimilarity(review.similarity)}`);
  similarity.title =
    "Proximidade entre o comentário e o tema da pergunta, de 0 a 1. Quanto maior, mais próximo.";
  foot.appendChild(similarity);
  const id = element("span", "review-id", `ID ${shortId(review.review_id)}`);
  id.title = `review_id ${review.review_id}`;
  foot.appendChild(id);
  card.appendChild(foot);
  return card;
}

function renderReviews(result, messageId) {
  if (!result.cited.length && !result.uncited.length) return null;
  const section = element("section", "reviews");
  if (result.cited.length) {
    section.appendChild(element("h3", null, `Avaliações citadas (${result.cited.length})`));
    for (const review of result.cited) section.appendChild(reviewCard(review, messageId, true));
  }
  if (result.uncited.length) {
    const details = element("details", "uncited");
    details.appendChild(
      element("summary", null, `Recuperadas e não citadas (${result.uncited.length})`),
    );
    for (const review of result.uncited) details.appendChild(reviewCard(review, messageId, false));
    section.appendChild(details);
  }
  return section;
}

function renderAnswer(container, result, messageId) {
  container.replaceChildren();
  container.removeAttribute("aria-busy");
  const notice = statusNotice(result.status);
  if (notice) {
    const box = element("div", `notice notice-${notice.kind}`);
    box.appendChild(element("strong", null, notice.title));
    box.appendChild(element("span", null, notice.text));
    container.appendChild(box);
  }
  const inferred = describeInferredRatings(result.inferred_ratings);
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
  if (error.kind === "key") showKeyError("Chave de acesso inválida. Confira e tente de novo.");
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
  const key = keyInput.value.trim();
  if (!key) {
    showKeyError("Digite a chave de acesso para perguntar.");
    return;
  }
  saveKey(key);
  clearKeyError();

  setBusy(true);
  renderLoading(reply);
  // Os filtros ficam no balão: a nova tentativa usa os mesmos da pergunta original
  const { status, body } = await callApi(question, key, reply.filters || null, reply.history || []);
  setBusy(false);

  const messageId = reply.dataset.messageId;
  if (status === 200 && body) {
    renderAnswer(reply, body, messageId);
    conversationTurns.push({ question, answer: body.answer });
    announce("Resposta pronta.");
  } else {
    const error = errorMessage(status, body);
    renderError(reply, error, question);
    announce(error.message);
  }
  // Rola até a pergunta, para a resposta ser lida desde o começo
  reply.parentElement.scrollIntoView({ behavior: "smooth", block: "start" });
}

function startQuestion(question) {
  if (busy) return false;
  if (!keyInput.value.trim()) {
    showKeyError("Digite a chave de acesso para perguntar.");
    return false;
  }
  welcome.hidden = true;
  newChatButton.hidden = false;

  messageCount += 1;
  const filters = currentFilters();
  const turn = element("div", "turn");
  const userMessage = element("div", "message-user", question);
  if (filters) userMessage.appendChild(element("span", "message-filters", `Filtros: ${describeFilters(filters)}`));
  turn.appendChild(userMessage);
  const reply = element("div", "message-bot");
  reply.dataset.messageId = `m${messageCount}`;
  reply.filters = filters;
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
    filtersPanel.open = false;
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
  questionInput.focus();
});
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

newChatButton.addEventListener("click", () => {
  if (busy) return;
  conversation.replaceChildren();
  conversationTurns = [];
  welcome.hidden = false;
  newChatButton.hidden = true;
  window.scrollTo({ top: 0, behavior: "smooth" });
  questionInput.focus();
});

let healthTimer = null;

async function checkApi() {
  clearTimeout(healthTimer);
  let online = false;
  try {
    const response = await fetch("/api/health");
    const data = await response.json().catch(() => null);
    if (response.ok && data) {
      online = true;
      apiStatusText.textContent = `No ar, com ${data.documents.toLocaleString("pt-BR")} avaliações`;
    } else {
      apiStatusText.textContent = errorMessage(response.status, data).message;
    }
  } catch {
    apiStatusText.textContent = errorMessage(0, null).message;
  }
  apiStatus.dataset.state = online ? "online" : "offline";
  if (!online) healthTimer = setTimeout(checkApi, HEALTH_RETRY_MS);
}

function currentFilters() {
  return buildFilters({
    ratings: [...ratingInputs].filter((input) => input.checked).map((input) => input.value),
    category: categorySelect.value,
    delivery: deliverySelect.value,
  });
}

function updateFiltersSummary() {
  const filters = currentFilters();
  filtersSummary.textContent = filters ? describeFilters(filters) : "nenhum";
  filtersPanel.dataset.active = String(Boolean(filters));
}

// As categorias vêm da API, que exige a chave; sem chave, o filtro fica só com "Todas".
// A carga em andamento é reaproveitada: a chave e a abertura do painel podem
// pedir a lista ao mesmo tempo, e sem isso as categorias apareceriam duas vezes.
let categoriesLoaded = false;
let categoriesRequest = null;

function loadCategories() {
  if (categoriesLoaded || categoriesRequest || !keyInput.value.trim()) return categoriesRequest;
  categoriesRequest = fetchCategories().finally(() => {
    categoriesRequest = null;
  });
  return categoriesRequest;
}

async function fetchCategories() {
  const key = keyInput.value.trim();
  try {
    const response = await fetch("/api/categories", { headers: { "X-Access-Key": key } });
    if (!response.ok) return;
    const data = await response.json();
    const options = data.categories
      .map((category) => ({ value: category, label: categoryLabel(category) }))
      .sort((a, b) => a.label.localeCompare(b.label, "pt-BR"));
    for (const option of options) {
      const node = element("option", null, option.label);
      node.value = option.value;
      categorySelect.appendChild(node);
    }
    categoriesLoaded = true;
  } catch {
    // sem as categorias, o filtro de categoria fica só com "Todas"
  }
}

for (const input of [...ratingInputs, categorySelect, deliverySelect]) {
  input.addEventListener("change", updateFiltersSummary);
}

clearFiltersButton.addEventListener("click", () => {
  for (const input of ratingInputs) input.checked = false;
  categorySelect.value = "";
  deliverySelect.value = "";
  updateFiltersSummary();
});

filtersPanel.addEventListener("toggle", () => {
  if (filtersPanel.open) loadCategories();
});
keyInput.addEventListener("change", loadCategories);

keyInput.value = loadKey();
updateComposer();
updateFiltersSummary();
checkApi();
loadCategories();
