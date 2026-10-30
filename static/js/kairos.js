/*
  JS próprio do Kairos: só o que não é papel do HTMX.
  - Tema escuro/claro (preferência salva neste navegador)
  - Toasts que somem sozinhos
*/
"use strict";

const reduzMovimento = matchMedia("(prefers-reduced-motion: reduce)").matches;

/* ===== Tema ===== */
function aplicarTema(tema) {
  document.documentElement.dataset.theme = tema;
  const claro = tema === "light";
  document.querySelectorAll('[data-action="tema"]').forEach(botao => {
    botao.querySelector("use")?.setAttribute("href", claro ? "#i-moon" : "#i-sun");
    const texto = botao.querySelector("span");
    if (texto) texto.textContent = claro ? "Modo escuro" : "Modo claro";
  });
}

function trocarTema(evento) {
  const novo = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  try { localStorage.setItem("kairos-tema", novo); } catch { /* navegador sem armazenamento */ }
  if (!document.startViewTransition || reduzMovimento) return aplicarTema(novo);

  // Círculo que se expande a partir do clique
  const x = evento.clientX || innerWidth / 2, y = evento.clientY || 0;
  const raio = Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y));
  document.startViewTransition(() => aplicarTema(novo)).ready.then(() => {
    document.documentElement.animate(
      { clipPath: [`circle(0px at ${x}px ${y}px)`, `circle(${raio}px at ${x}px ${y}px)`] },
      { duration: 550, easing: "cubic-bezier(.4,0,.2,1)", pseudoElement: "::view-transition-new(root)" },
    );
  });
}

document.addEventListener("click", evento => {
  if (evento.target.closest('[data-action="tema"]')) trocarTema(evento);
});

/* ===== Toasts ===== */
function fecharToast(toast) {
  toast.classList.add("is-leaving");
  setTimeout(() => toast.remove(), 200);
}

function agendarToasts(raiz = document) {
  raiz.querySelectorAll(".toast[data-auto]").forEach(toast => {
    toast.removeAttribute("data-auto");
    setTimeout(() => fecharToast(toast), 4000);
  });
}

/* ===== Início ===== */
document.addEventListener("DOMContentLoaded", () => {
  aplicarTema(document.documentElement.dataset.theme || "dark");
  agendarToasts();
});
// Toasts que chegarem em respostas do HTMX também somem sozinhos.
document.addEventListener("htmx:afterSettle", evento => agendarToasts(evento.target));
