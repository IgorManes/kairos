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
  // Durante a troca de tema, os cards não animam sozinhos (ficariam fora do círculo).
  document.documentElement.classList.add("tema-trocando");
  const transicao = document.startViewTransition(() => aplicarTema(novo));
  transicao.finished.finally(() => document.documentElement.classList.remove("tema-trocando"));
  transicao.ready.then(() => {
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
  if (!toast.isConnected || toast.classList.contains("is-leaving")) return;
  toast.classList.add("is-leaving");
  setTimeout(() => toast.remove(), 200);
}

function agendarToasts() {
  document.querySelectorAll(".toast[data-auto]").forEach(toast => {
    const duracao = Number(toast.dataset.auto) || 4000;  // data-auto="6000" = 6 s
    toast.removeAttribute("data-auto");
    toast.style.setProperty("--duracao", duracao + "ms");
    setTimeout(() => fecharToast(toast), duracao);
  });
  // No máximo 3 toasts na tela.
  const todos = document.querySelectorAll("#toasts .toast:not(.is-leaving)");
  [...todos].slice(0, Math.max(0, todos.length - 3)).forEach(fecharToast);
}

function toastErro(mensagem) {
  const toast = document.createElement("div");
  toast.className = "toast is-erro";
  toast.dataset.auto = "5000";
  toast.textContent = mensagem;
  document.getElementById("toasts")?.append(toast);
  agendarToasts();
}

/* ===== Concluir: marca na hora (o servidor confirma em seguida) ===== */
function faiscas(botao) {
  if (reduzMovimento) return;
  const r = botao.getBoundingClientRect(), cx = r.left + r.width / 2, cy = r.top + r.height / 2;
  const cor = getComputedStyle(botao).getPropertyValue("--c").trim() || "#8b5cf6";
  for (let i = 0; i < 14; i++) {
    const s = document.createElement("i");
    s.className = "spark";
    Object.assign(s.style, { left: cx + "px", top: cy + "px", background: cor, boxShadow: `0 0 8px ${cor}` });
    document.body.append(s);
    const angulo = (i / 14) * Math.PI * 2 + Math.random() * 0.5, distancia = 16 + Math.random() * 18;
    s.animate([
      { transform: "translate(-50%, -50%) scale(1)", opacity: 1 },
      { transform: `translate(calc(-50% + ${Math.cos(angulo) * distancia}px), calc(-50% + ${Math.sin(angulo) * distancia}px)) scale(.2)`, opacity: 0 },
    ], { duration: 500 + Math.random() * 250, easing: "cubic-bezier(.2,.7,.3,1)" }).onfinish = () => s.remove();
  }
}

document.addEventListener("click", evento => {
  const check = evento.target.closest(".task .check");
  if (check) {
    const concluindo = check.closest(".task").classList.toggle("is-done");
    if (concluindo) faiscas(check);
  }
  const desfazer = evento.target.closest("[data-desfazer]");
  if (desfazer) fecharToast(desfazer.closest(".toast"));
});

/* ===== Painel lateral de criar/editar ===== */
const painelLateral = () => document.getElementById("drawer");

// Abre quando o HTMX coloca o formulário dentro dele.
document.addEventListener("htmx:afterSwap", evento => {
  if (evento.detail.target.id !== "drawer-conteudo") return;
  const dialogo = painelLateral();
  if (!dialogo.open) dialogo.showModal();
  const titulo = dialogo.querySelector('input[name="titulo"]:not(:disabled)');
  if (titulo && !dialogo.querySelector(".erro")) titulo.focus();
  else dialogo.querySelector(".has-erro .input")?.focus();
});
// O servidor avisa "fecharPainel" quando salvou com sucesso.
document.body.addEventListener("fecharPainel", () => painelLateral()?.close());
document.addEventListener("click", evento => {
  if (evento.target.closest("[data-fechar-painel]")) painelLateral()?.close();
  if (evento.target === painelLateral()) painelLateral().close();  // clique fora (no fundo escuro)
  // Escolheu uma opção no menu ⋯: fecha o menu.
  const opcao = evento.target.closest("[popover] button");
  if (opcao) opcao.closest("[popover]").hidePopover();
});

/* ===== Atalhos: N = nova tarefa rápida, Ctrl+Z = desfazer ===== */
document.addEventListener("keydown", evento => {
  const digitando = evento.target.closest?.("input, textarea, select, [contenteditable]");
  if ((evento.ctrlKey || evento.metaKey) && evento.key.toLowerCase() === "z" && !digitando) {
    const botoes = document.querySelectorAll("#toasts .toast:not(.is-leaving) [data-desfazer]");
    if (botoes.length) { evento.preventDefault(); botoes[botoes.length - 1].click(); }
    return;
  }
  if (digitando || evento.ctrlKey || evento.metaKey || evento.altKey || painelLateral()?.open) return;
  if (evento.key.toLowerCase() === "n") {
    const campo = document.getElementById("quick-input");
    if (campo) { evento.preventDefault(); campo.focus(); }
  }
});

/* ===== Erros do servidor: desfaz a marcação visual e avisa ===== */
document.addEventListener("htmx:responseError", evento => {
  if (evento.detail.elt.matches?.(".check")) evento.detail.elt.closest(".task").classList.toggle("is-done");
  toastErro(evento.detail.xhr.responseText || "Algo deu errado. Tente de novo.");
});
document.addEventListener("htmx:sendError", () => toastErro("Sem conexão com o Kairos."));

/* ===== Contadores que "contam" até o valor novo ===== */
let valoresAntes = {};
document.addEventListener("htmx:beforeSwap", () => {
  valoresAntes = {};
  document.querySelectorAll("[data-contar]").forEach(el => (valoresAntes[el.dataset.contar] = Number(el.textContent)));
});
document.addEventListener("htmx:afterSettle", () => {
  document.querySelectorAll("[data-contar]").forEach(el => {
    const de = valoresAntes[el.dataset.contar], para = Number(el.textContent);
    if (de === undefined || de === para || reduzMovimento) return;
    const inicio = performance.now();
    const passo = agora => {
      const p = Math.min((agora - inicio) / 450, 1);
      el.textContent = Math.round(de + (para - de) * (1 - (1 - p) ** 3));  // desacelera no fim
      if (p < 1) requestAnimationFrame(passo);
    };
    el.textContent = de;
    requestAnimationFrame(passo);
  });
});

/* ===== Quadro: arrastar o card para outra coluna ===== */
let arrastado = null;
document.addEventListener("dragstart", evento => {
  const card = evento.target.closest?.(".task[draggable]");
  if (!card) return;
  arrastado = card;
  evento.dataTransfer.effectAllowed = "move";
  evento.dataTransfer.setData("text/plain", card.id);
  requestAnimationFrame(() => card.classList.add("is-arrastando"));
});
document.addEventListener("dragend", () => {
  arrastado?.classList.remove("is-arrastando");
  document.querySelectorAll(".coluna.is-alvo").forEach(c => c.classList.remove("is-alvo"));
  arrastado = null;
});
document.addEventListener("dragover", evento => {
  const coluna = evento.target.closest?.(".coluna");
  if (!arrastado || !coluna) return;
  evento.preventDefault();  // permite soltar aqui
  document.querySelectorAll(".coluna.is-alvo").forEach(c => c !== coluna && c.classList.remove("is-alvo"));
  coluna.classList.toggle("is-alvo", coluna.dataset.status !== arrastado.dataset.status);
});
document.addEventListener("drop", evento => {
  const coluna = evento.target.closest?.(".coluna");
  if (!arrastado || !coluna) return;
  evento.preventDefault();
  const card = arrastado, novo = coluna.dataset.status;
  if (novo === card.dataset.status) return;
  coluna.querySelector(".coluna-vazia")?.remove();
  coluna.querySelector(".list").prepend(card);  // aparece na coluna na hora
  // Mesma ação dos botões: toast com Desfazer e as telas se atualizam pelo aviso.
  htmx.ajax("POST", card.dataset.urlStatus, { source: card, values: { status: novo }, swap: "none" });
});

/* ===== Início ===== */
document.addEventListener("DOMContentLoaded", () => {
  aplicarTema(document.documentElement.dataset.theme || "dark");
  agendarToasts();
});
// Toasts que chegarem em respostas do HTMX também somem sozinhos.
document.addEventListener("htmx:afterSettle", agendarToasts);
