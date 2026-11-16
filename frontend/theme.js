// Aplica o tema salvo antes de a página aparecer, para ela não piscar no tema
// errado. Roda no <head>, fora dos módulos, por isso não importa logic.js.
(function () {
  try {
    const saved = localStorage.getItem("olist-theme");
    if (saved === "light" || saved === "dark") document.documentElement.dataset.theme = saved;
  } catch {
    // sem armazenamento, a página segue o tema do sistema
  }
})();
