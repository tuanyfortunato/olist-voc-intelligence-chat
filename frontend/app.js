// Página do chat. Todo texto que vem da API, inclusive os comentários dos
// clientes, entra na tela com textContent, nunca como HTML: um comentário com
// "<script>" aparece escrito, sem ser executado.
import {
  errorMessage,
  formatSimilarity,
  parseAnswerBlocks,
  splitCitations,
  statusNotice,
} from "./logic.js";

const KEY_STORAGE = "olist-voc-access-key";
const MAX_CHARS = 500;

const keyInput = document.getElementById("access-key");
const form = document.getElementById("ask-form");
const questionInput = document.getElementById("question");
const sendButton = document.getElementById("send");
const counter = document.getElementById("counter");
const conversation = document.getElementById("conversation");
const apiStatus = document.getElementById("api-status");

let messageCount = 0;

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

function scrollToEnd() {
  window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" });
}

// Texto com as citações [n] transformadas em botões que levam à avaliação
function appendWithCitations(parent, text, messageId) {
  for (const part of splitCitations(text)) {
    if (part.type === "text") {
      parent.appendChild(document.createTextNode(part.value));
      continue;
    }
    for (const number of part.numbers) {
      const button = element("button", "cite", `[${number}]`);
      button.type = "button";
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
  card.classList.add("highlight");
  setTimeout(() => card.classList.remove("highlight"), 1600);
}

function reviewCard(review, messageId, cited) {
  const card = element("article", cited ? "review cited" : "review");
  card.id = `${messageId}-review-${review.number}`;
  card.appendChild(element("span", "review-number", `[${review.number}]`));
  const meta = `Nota ${review.rating} · similaridade ${formatSimilarity(review.similarity)} · avaliação ${review.review_id}`;
  card.appendChild(element("span", "review-meta", meta));
  card.appendChild(element("span", "review-text", review.original_text));
  return card;
}

function renderReviews(result, messageId) {
  if (!result.cited.length && !result.uncited.length) return null;
  const section = element("section", "reviews");
  if (result.cited.length) {
    section.appendChild(element("h3", null, `Avaliações usadas (${result.cited.length})`));
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
  const notice = statusNotice(result.status);
  if (notice) {
    const box = element("div", `notice notice-${notice.kind}`);
    box.appendChild(element("strong", null, notice.title));
    box.appendChild(document.createTextNode(notice.text));
    container.appendChild(box);
  }
  for (const block of parseAnswerBlocks(result.answer)) {
    if (block.type === "paragraph") {
      const paragraph = element("p");
      appendWithCitations(paragraph, block.text, messageId);
      container.appendChild(paragraph);
    } else {
      const list = element("ul");
      for (const item of block.items) {
        const li = element("li");
        appendWithCitations(li, item, messageId);
        list.appendChild(li);
      }
      container.appendChild(list);
    }
  }
  const reviews = renderReviews(result, messageId);
  if (reviews) container.appendChild(reviews);
}

function renderError(container, error) {
  container.replaceChildren();
  const box = element("div", "notice notice-error", error.message);
  container.appendChild(box);
  if (error.kind === "key") {
    keyInput.classList.add("invalid");
    keyInput.focus();
  }
}

async function ask(question) {
  const key = keyInput.value.trim();
  if (!key) {
    keyInput.classList.add("invalid");
    keyInput.focus();
    return;
  }
  saveKey(key);
  keyInput.classList.remove("invalid");

  messageCount += 1;
  const messageId = `m${messageCount}`;
  conversation.appendChild(element("div", "message-user", question));
  const reply = element("div", "message-bot");
  reply.appendChild(element("p", "loading", "Buscando nas avaliações..."));
  conversation.appendChild(reply);
  scrollToEnd();

  sendButton.disabled = true;
  let status = 0;
  let body = null;
  try {
    const response = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Access-Key": key },
      body: JSON.stringify({ question, history: [] }),
    });
    status = response.status;
    body = await response.json().catch(() => null);
  } catch {
    status = 0;
  } finally {
    sendButton.disabled = false;
  }

  if (status === 200 && body) renderAnswer(reply, body, messageId);
  else renderError(reply, errorMessage(status, body));
  reply.scrollIntoView({ behavior: "smooth", block: "start" });
}

function updateCounter() {
  counter.textContent = `${questionInput.value.length}/${MAX_CHARS}`;
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const question = questionInput.value.trim();
  if (!question || sendButton.disabled) return;
  questionInput.value = "";
  updateCounter();
  ask(question);
});

// Enter envia; Shift+Enter quebra a linha
questionInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});

questionInput.addEventListener("input", updateCounter);

document.getElementById("key-form").addEventListener("submit", (event) => event.preventDefault());
keyInput.addEventListener("input", () => keyInput.classList.remove("invalid"));

for (const button of document.querySelectorAll("#examples button")) {
  button.addEventListener("click", () => {
    if (sendButton.disabled) return;
    ask(button.textContent.trim());
  });
}

async function checkApi() {
  try {
    const response = await fetch("/api/health");
    const data = await response.json().catch(() => null);
    if (response.ok && data) {
      apiStatus.textContent = `No ar, com ${data.documents.toLocaleString("pt-BR")} avaliações na base.`;
    } else {
      apiStatus.textContent = errorMessage(response.status, data).message;
    }
  } catch {
    apiStatus.textContent = errorMessage(0, null).message;
  }
}

keyInput.value = loadKey();
updateCounter();
checkApi();
