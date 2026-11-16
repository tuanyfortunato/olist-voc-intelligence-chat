// Faixa de filtros da busca, acima do campo de pergunta: três botões (nota,
// categoria e entrega) que mostram o valor escolhido e abrem um menu cada um.
// Os nomes das categorias vêm da API e entram na tela com textContent.
import {
  buildFilters,
  categoryLabel,
  chipLabel,
  DELIVERY_OPTIONS,
  errorMessage,
  filterCategories,
  RATING_SHORTCUTS,
  searchScopeText,
  toggleRating,
} from "./logic.js";
import { closeOverlay, openOverlay } from "./overlay.js";

const KINDS = [
  { kind: "ratings", noun: "nota", title: "Filtrar por nota" },
  { kind: "category", noun: "categoria", title: "Filtrar por categoria" },
  { kind: "delivery", noun: "entrega", title: "Filtrar por entrega" },
];

function node(tag, className, text) {
  const item = document.createElement(tag);
  if (className) item.className = className;
  if (text !== undefined) item.textContent = text;
  return item;
}

function button(className, text) {
  const item = node("button", className, text);
  item.type = "button";
  return item;
}

function sameList(a, b) {
  return a.length === b.length && a.every((value, index) => value === b[index]);
}

export function createFilterBar({ container, announce }) {
  const state = { ratings: [], category: "", delivery: "" };
  // idle, loading, loaded ou error; a lista só é pedida quando o menu abre
  const categories = { status: "idle", options: [], message: "", request: null };
  const chips = {};
  let openMenu = null;
  let disabled = false;

  const chipRow = node("div", "filter-chips");
  chipRow.appendChild(node("span", "filter-bar-label", "Filtrar a busca"));
  for (const { kind, noun } of KINDS) {
    const chip = node("span", "filter-chip");
    const main = button("filter-chip-main");
    const text = node("span", "filter-chip-text");
    main.appendChild(text);
    main.setAttribute("aria-haspopup", "dialog");
    main.setAttribute("aria-expanded", "false");
    main.addEventListener("click", () => toggleMenu(kind));
    const remove = button("filter-chip-remove", "×");
    remove.setAttribute("aria-label", `Remover o filtro de ${noun}`);
    remove.addEventListener("click", () => {
      setValue(kind, kind === "ratings" ? [] : "");
      main.focus();
    });
    chip.append(main, remove);
    chipRow.appendChild(chip);
    chips[kind] = { chip, main, text, remove, noun };
  }
  const clearAll = button("filter-clear", "Limpar tudo");
  clearAll.addEventListener("click", () => {
    clear();
    announce("Filtros removidos");
  });
  chipRow.appendChild(clearAll);
  const scope = node("p", "filter-scope");
  container.replaceChildren(chipRow, scope);

  function current() {
    return buildFilters(state);
  }

  function renderBar() {
    const filters = current();
    for (const { kind } of KINDS) {
      const { chip, main, text, remove, noun } = chips[kind];
      const label = chipLabel(kind, filters);
      const active = label.includes(":");
      text.textContent = label;
      main.setAttribute(
        "aria-label",
        active ? `Filtrar por ${noun}, ${label}` : `Filtrar por ${noun}, nenhum selecionado`,
      );
      chip.dataset.active = String(active);
      remove.hidden = !active;
      main.disabled = disabled;
      remove.disabled = disabled;
    }
    clearAll.hidden = !filters;
    clearAll.disabled = disabled;
    scope.textContent = searchScopeText(filters);
    container.dataset.active = String(Boolean(filters));
  }

  function setValue(kind, value, { silent = false } = {}) {
    state[kind] = value;
    renderBar();
    if (silent) return;
    const filters = current();
    const label = chipLabel(kind, filters);
    const noun = chips[kind].noun;
    announce(
      label.includes(":")
        ? `Filtro de ${noun} aplicado: ${label.split(": ")[1]}`
        : `Filtro de ${noun} removido`,
    );
  }

  function clear() {
    closeOverlay();
    state.ratings = [];
    state.category = "";
    state.delivery = "";
    renderBar();
  }

  function restore(filters) {
    state.ratings = filters && filters.ratings ? [...filters.ratings] : [];
    state.category = (filters && filters.category) || "";
    state.delivery = (filters && filters.delivery) || "";
    renderBar();
  }

  function toggleMenu(kind) {
    if (openMenu && openMenu.kind === kind && openMenu.handle.isOpen) {
      openMenu.handle.close();
      return;
    }
    const { title } = KINDS.find((item) => item.kind === kind);
    const content = node("div", `filter-menu filter-menu-${kind}`);
    const handle = openOverlay({
      anchor: chips[kind].main,
      title,
      content,
      onClose: () => {
        openMenu = null;
      },
    });
    openMenu = { kind, handle, content };
    if (kind === "ratings") fillRatings(content);
    if (kind === "delivery") fillDelivery(content, handle);
    if (kind === "category") {
      fillCategory(content, handle);
      loadCategories();
    }
    handle.reposition();
    const first = content.querySelector("button, input");
    if (first && !(handle.panel.classList.contains("overlay-sheet") && first.tagName === "INPUT")) {
      first.focus({ preventScroll: true });
    }
  }

  // Nota: vários valores ao mesmo tempo; o menu fica aberto a cada escolha
  function fillRatings(content) {
    const shortcuts = node("div", "filter-shortcuts");
    const shortcutButtons = [];
    for (const [name, label] of [
      ["low", "Notas baixas"],
      ["high", "Notas altas"],
    ]) {
      const item = button("filter-shortcut", label);
      item.addEventListener("click", () => {
        const wanted = RATING_SHORTCUTS[name];
        setValue("ratings", sameList(state.ratings, wanted) ? [] : [...wanted]);
        sync();
      });
      shortcuts.appendChild(item);
      shortcutButtons.push([name, item]);
    }
    content.appendChild(shortcuts);
    const list = node("div", "filter-options");
    const ratingButtons = [];
    for (let rating = 1; rating <= 5; rating += 1) {
      const item = button("filter-option");
      const stars = node("span", "filter-option-stars", "★".repeat(rating));
      stars.setAttribute("aria-hidden", "true");
      item.append(stars, node("span", null, rating === 1 ? "1 estrela" : `${rating} estrelas`));
      item.addEventListener("click", () => {
        setValue("ratings", toggleRating(state.ratings, rating));
        sync();
      });
      list.appendChild(item);
      ratingButtons.push([rating, item]);
    }
    content.appendChild(list);
    content.appendChild(node("p", "filter-menu-note", "Sem nenhuma nota marcada, a busca olha todas."));

    function sync() {
      for (const [rating, item] of ratingButtons) {
        item.setAttribute("aria-pressed", String(state.ratings.includes(rating)));
      }
      for (const [name, item] of shortcutButtons) {
        item.setAttribute("aria-pressed", String(sameList(state.ratings, RATING_SHORTCUTS[name])));
      }
    }
    sync();
  }

  // Entrega: uma opção por vez; escolher a marcada desmarca
  function fillDelivery(content, handle) {
    const list = node("div", "filter-options");
    list.setAttribute("role", "radiogroup");
    list.setAttribute("aria-label", "Situação da entrega");
    for (const option of DELIVERY_OPTIONS) {
      const item = button("filter-option", option.label);
      item.setAttribute("role", "radio");
      item.setAttribute("aria-checked", String(state.delivery === option.value));
      item.addEventListener("click", () => {
        setValue("delivery", state.delivery === option.value ? "" : option.value);
        handle.close();
      });
      list.appendChild(item);
    }
    content.appendChild(list);
    content.appendChild(
      node("p", "filter-menu-note", "Os pedidos sem informação de entrega ficam de fora."),
    );
  }

  function fillCategory(content, handle) {
    const search = node("input", "filter-search");
    search.type = "search";
    search.placeholder = "Buscar categoria";
    search.setAttribute("aria-label", "Buscar categoria");
    search.autocomplete = "off";
    const list = node("div", "filter-options filter-category-list");
    list.setAttribute("role", "radiogroup");
    list.setAttribute("aria-label", "Categoria do produto");
    content.append(search, list);
    content.appendChild(
      node("p", "filter-menu-note", "Os pedidos com produtos de várias categorias ficam de fora."),
    );

    function message(text, action) {
      const box = node("p", "filter-menu-message", text);
      list.replaceChildren(box);
      if (action) list.appendChild(action);
    }

    function render() {
      search.hidden = categories.status !== "loaded";
      if (categories.status === "loading" || categories.status === "idle") {
        message("Carregando as categorias");
      } else if (categories.status === "error") {
        const retry = button("filter-shortcut", "Tentar de novo");
        retry.addEventListener("click", () => loadCategories({ force: true }));
        message(categories.message, retry);
      } else {
        const found = filterCategories(categories.options, search.value);
        if (!found.length) {
          message("Nenhuma categoria com esse nome");
        } else {
          list.replaceChildren();
          for (const option of found) {
            const item = button("filter-option", option.label);
            item.setAttribute("role", "radio");
            item.setAttribute("aria-checked", String(state.category === option.value));
            item.addEventListener("click", () => {
              setValue("category", state.category === option.value ? "" : option.value);
              handle.close();
            });
            list.appendChild(item);
          }
        }
      }
      handle.reposition();
    }

    search.addEventListener("input", render);
    openMenu.render = render;
    render();
  }

  function refreshCategoryMenu() {
    if (openMenu && openMenu.kind === "category" && openMenu.render) openMenu.render();
  }

  // A lista vem da API. A carga em andamento é reaproveitada.
  function loadCategories({ force = false } = {}) {
    if (categories.request) return categories.request;
    if (categories.status === "loaded" && !force) return Promise.resolve();
    categories.status = "loading";
    refreshCategoryMenu();
    categories.request = fetchCategories().finally(() => {
      categories.request = null;
      refreshCategoryMenu();
    });
    return categories.request;
  }

  async function fetchCategories() {
    let status = 0;
    let body = null;
    try {
      const response = await fetch("/api/categories");
      status = response.status;
      body = await response.json().catch(() => null);
    } catch {
      status = 0;
    }
    if (status !== 200 || !body || !Array.isArray(body.categories) || !body.categories.length) {
      categories.status = "error";
      categories.message =
        status === 200
          ? "Não foi possível carregar as categorias."
          : errorMessage(status, body).message;
      return;
    }
    categories.options = body.categories
      .map((value) => ({ value, label: categoryLabel(value) || value }))
      .sort((a, b) => a.label.localeCompare(b.label, "pt-BR"));
    categories.status = "loaded";
    // Uma lista nova pode não ter a categoria escolhida; nesse caso ela sai do filtro
    if (state.category && !categories.options.some((option) => option.value === state.category)) {
      setValue("category", "", { silent: true });
      announce("Filtro de categoria removido");
    }
  }

  function setDisabled(value) {
    disabled = value;
    if (value) closeOverlay();
    renderBar();
  }

  renderBar();
  return { current, clear, restore, setDisabled };
}
