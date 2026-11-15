// Versão mínima da página: só confere se a API está no ar.
// O chat entra na etapa do front-end.
const status = document.getElementById("status");

async function checkApi() {
  try {
    const response = await fetch("/api/health");
    if ([502, 503, 504].includes(response.status)) {
      status.textContent = "O chat está desligado no momento.";
      return;
    }
    const data = await response.json();
    status.textContent = `API no ar, com ${data.documents.toLocaleString("pt-BR")} avaliações na base.`;
  } catch {
    status.textContent = "Não foi possível falar com a API.";
  }
}

checkApi();
