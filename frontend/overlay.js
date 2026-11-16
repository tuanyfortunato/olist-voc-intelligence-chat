// Menu flutuante no computador e folha de baixo para cima no celular. É usado
// pelos menus dos filtros e pelo cartão da avaliação citada. Só um fica aberto
// por vez, e o conteúdo é sempre montado por quem chama, com textContent.

const MOBILE = window.matchMedia("(max-width: 640px)");
const MARGIN = 8;
const FOCUSABLE = 'button:not([disabled]), input:not([disabled]), a[href], [tabindex="0"]';

let current = null;

export function closeOverlay() {
  if (current) current.close();
}

function node(tag, className, text) {
  const item = document.createElement(tag);
  if (className) item.className = className;
  if (text !== undefined) item.textContent = text;
  return item;
}

// No computador, o menu abre acima do botão que o chamou; sem espaço em cima,
// abre embaixo. Nunca passa das bordas da janela.
function place(panel, anchor) {
  const rect = anchor.getBoundingClientRect();
  const above = rect.top - MARGIN * 2;
  const below = window.innerHeight - rect.bottom - MARGIN * 2;
  const openAbove = above >= Math.min(panel.offsetHeight, 240) || above >= below;
  panel.style.maxHeight = `${Math.max(openAbove ? above : below, 120)}px`;
  const maxLeft = window.innerWidth - panel.offsetWidth - MARGIN;
  panel.style.left = `${Math.max(MARGIN, Math.min(rect.left, maxLeft))}px`;
  if (openAbove) {
    panel.style.top = "";
    panel.style.bottom = `${window.innerHeight - rect.top + MARGIN}px`;
  } else {
    panel.style.bottom = "";
    panel.style.top = `${rect.bottom + MARGIN}px`;
  }
}

export function openOverlay({ anchor, title, content, onClose }) {
  closeOverlay();
  const sheet = MOBILE.matches;
  const panel = node("div", sheet ? "overlay overlay-sheet" : "overlay");
  panel.setAttribute("role", "dialog");
  panel.setAttribute("aria-label", title);
  panel.tabIndex = -1;
  let backdrop = null;
  if (sheet) {
    panel.setAttribute("aria-modal", "true");
    backdrop = node("div", "overlay-backdrop");
    const header = node("div", "overlay-header");
    header.appendChild(node("strong", null, title));
    const closeButton = node("button", "overlay-close", "Fechar");
    closeButton.type = "button";
    closeButton.addEventListener("click", () => handle.close());
    header.appendChild(closeButton);
    panel.appendChild(header);
    document.body.appendChild(backdrop);
  }
  const body = node("div", "overlay-body");
  body.appendChild(content);
  panel.appendChild(body);
  document.body.appendChild(panel);
  if (!sheet) place(panel, anchor);
  anchor.setAttribute("aria-expanded", "true");

  function focusables() {
    return [...panel.querySelectorAll(FOCUSABLE)].filter((item) => item.offsetParent !== null);
  }

  function onKeydown(event) {
    if (event.key === "Escape") {
      event.preventDefault();
      handle.close();
      return;
    }
    const items = focusables();
    if (!items.length) return;
    const index = items.indexOf(document.activeElement);
    // As setas andam pelas opções; no campo de busca, só a seta para baixo sai dele
    const typing = document.activeElement && document.activeElement.tagName === "INPUT";
    if (event.key === "ArrowDown" || (event.key === "ArrowUp" && !typing)) {
      event.preventDefault();
      const step = event.key === "ArrowDown" ? 1 : -1;
      items[(index + step + items.length) % items.length].focus();
    } else if (event.key === "Tab") {
      // O foco fica preso dentro do menu enquanto ele está aberto
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
  }

  // composedPath guarda o caminho do clique mesmo que o menu redesenhe o botão clicado
  function onOutsideClick(event) {
    const path = event.composedPath();
    if (path.includes(panel) || path.includes(anchor)) return;
    handle.close({ restoreFocus: false });
  }

  function onViewportChange() {
    handle.close({ restoreFocus: false });
  }

  function onScroll(event) {
    // Rolar a lista de dentro do menu não o fecha; rolar a página, sim
    if (!sheet && !panel.contains(event.target)) handle.close({ restoreFocus: false });
  }

  const handle = {
    isOpen: true,
    panel,
    // Chamado por quem redesenha o conteúdo e muda a altura do menu
    reposition() {
      if (handle.isOpen && !sheet) place(panel, anchor);
    },
    close({ restoreFocus = true } = {}) {
      if (!handle.isOpen) return;
      handle.isOpen = false;
      current = null;
      panel.remove();
      if (backdrop) backdrop.remove();
      document.removeEventListener("keydown", onKeydown, true);
      document.removeEventListener("click", onOutsideClick, true);
      window.removeEventListener("resize", onViewportChange);
      window.removeEventListener("scroll", onScroll, true);
      anchor.setAttribute("aria-expanded", "false");
      if (restoreFocus && document.contains(anchor)) anchor.focus();
      if (onClose) onClose();
    },
  };
  current = handle;

  document.addEventListener("keydown", onKeydown, true);
  window.addEventListener("resize", onViewportChange);
  window.addEventListener("scroll", onScroll, true);
  // O clique que abriu o menu ainda está em andamento; o registro espera ele terminar
  setTimeout(() => {
    if (handle.isOpen) document.addEventListener("click", onOutsideClick, true);
  }, 0);
  if (backdrop) backdrop.addEventListener("click", () => handle.close({ restoreFocus: false }));

  // Na folha do celular, o foco não vai para o campo de busca, para o teclado
  // não abrir sozinho e cobrir a lista
  const first = focusables().find(
    (item) => !item.classList.contains("overlay-close") && !(sheet && item.tagName === "INPUT"),
  );
  (first || panel).focus({ preventScroll: true });
  return handle;
}
