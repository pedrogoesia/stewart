// Stewart — interações da página da obra (upload, descrições, cômodos).

// Token CSRF: enviado em todo POST para o servidor confirmar que a requisição
// partiu da nossa própria página (e não de um site malicioso).
function csrfToken() {
  const meta = document.querySelector('meta[name="csrf-token"]');
  return meta ? meta.getAttribute("content") : "";
}

function postForm(url, data) {
  const fd = new FormData();
  for (const k in data) fd.append(k, data[k]);
  return fetch(url, {
    method: "POST",
    body: fd,
    headers: { "X-CSRFToken": csrfToken() },
  });
}

// ---------------------------------------------------------------- Cômodos
async function criarComodo() {
  const input = document.getElementById("novo-comodo");
  const nome = input.value.trim();
  if (!nome) { input.focus(); return; }

  const resp = await postForm(`/obra/${window.OBRA_ID}/comodos`, { nome });
  if (!resp.ok) { alert("Não foi possível criar o cômodo."); return; }
  const c = await resp.json();
  input.value = "";

  const semComodos = document.getElementById("sem-comodos");
  if (semComodos) semComodos.remove();

  document.getElementById("comodos").insertAdjacentHTML("beforeend",
    comodoTemplate(c.id, c.nome));
  input.focus();  // pronto para digitar o próximo cômodo, sem rolar a página
}

// Seção de fotos avulsas ("sem cômodo"): reaproveita a existente ou cria uma.
async function criarComodoGeral() {
  const resp = await postForm(`/obra/${window.OBRA_ID}/comodo-geral`, {});
  if (!resp.ok) { alert("Não foi possível criar a seção de fotos."); return; }
  const c = await resp.json();

  if (!document.querySelector(`[data-comodo-id="${c.id}"]`)) {
    const semComodos = document.getElementById("sem-comodos");
    if (semComodos) semComodos.remove();
    document.getElementById("comodos").insertAdjacentHTML("beforeend",
      comodoTemplate(c.id, c.nome, true));
  }
}

function comodoTemplate(id, nome, geral = false) {
  const titulo = geral
    ? `<h2 class="comodo-nome">📷 Fotos da obra <small class="muted">(sem cômodo)</small></h2>`
    : `<h2 class="comodo-nome" data-id="${id}">${escapeHtml(nome)}</h2>`;
  const renomear = geral ? "" :
    `<button class="btn btn-sm btn-ghost" onclick="renomearComodo(${id})">Renomear</button>`;
  return `
  <section class="comodo" data-comodo-id="${id}">
    <div class="comodo-head">
      ${titulo}
      <div class="comodo-tools">
        <span class="badge foto-count">0 foto(s)</span>
        <span class="comodo-mover">
          <button class="btn btn-sm btn-ghost btn-icon" title="Mover para cima" onclick="moverComodo(${id}, -1)">↑</button>
          <button class="btn btn-sm btn-ghost btn-icon" title="Mover para baixo" onclick="moverComodo(${id}, 1)">↓</button>
        </span>
        ${renomear}
        <button class="btn btn-sm btn-ghost-danger" onclick="excluirComodo(${id})">Excluir</button>
      </div>
    </div>
    <label class="dropzone">
      <input type="file" accept="image/*" multiple
             onchange="enviarFotos(this, ${id})" hidden>
      <span class="dropzone-inner">📷 Adicionar fotos &nbsp;<small>(toque para tirar foto ou escolher da galeria)</small></span>
    </label>
    <p class="drag-hint" hidden>↕ Arraste as fotos pela imagem para mudar a ordem (é a ordem que sai no PowerPoint).</p>
    <div class="foto-grid" data-grid="${id}"></div>
  </section>`;
}

async function renomearComodo(id) {
  const h = document.querySelector(`.comodo-nome[data-id="${id}"]`);
  const nome = prompt("Novo nome do cômodo:", h.textContent.trim());
  if (nome === null) return;
  const v = nome.trim();
  if (!v) return;
  const resp = await postForm(`/comodo/${id}/renomear`, { nome: v });
  if (resp.ok) h.textContent = v;
}

async function excluirComodo(id) {
  if (!confirm("Excluir este cômodo e todas as suas fotos?")) return;
  const resp = await postForm(`/comodo/${id}/excluir`, {});
  if (resp.ok) document.querySelector(`[data-comodo-id="${id}"]`).remove();
}

// Move um cômodo para cima (-1) ou para baixo (1) e salva a nova ordem.
async function moverComodo(id, dir) {
  const sec = document.querySelector(`.comodo[data-comodo-id="${id}"]`);
  if (!sec) return;
  if (dir < 0) {
    const prev = sec.previousElementSibling;
    if (!prev || !prev.classList.contains("comodo")) return;  // já é o primeiro
    sec.parentNode.insertBefore(sec, prev);
  } else {
    const next = sec.nextElementSibling;
    if (!next || !next.classList.contains("comodo")) return;   // já é o último
    sec.parentNode.insertBefore(next, sec);
  }
  sec.scrollIntoView({ behavior: "smooth", block: "nearest" });
  await salvarOrdemComodos();
}

async function salvarOrdemComodos() {
  const ids = [...document.querySelectorAll("#comodos .comodo[data-comodo-id]")]
    .map((s) => s.dataset.comodoId);
  await postForm(`/obra/${window.OBRA_ID}/comodos/reordenar`, { ordem: ids.join(",") });
}

// ------------------------------------------------------------------ Fotos
async function enviarFotos(input, comodoId) {
  const files = Array.from(input.files);
  input.value = "";
  if (!files.length) return;

  const grid = document.querySelector(`[data-grid="${comodoId}"]`);
  for (const file of files) {
    const ph = document.createElement("figure");
    ph.className = "foto foto-loading";
    ph.innerHTML = `<div class="spinner"></div>`;
    grid.appendChild(ph);

    try {
      const fd = new FormData();
      fd.append("foto", file);
      fd.append("descricao", "");
      const resp = await fetch(`/comodo/${comodoId}/fotos`, {
        method: "POST", body: fd,
        headers: { "X-CSRFToken": csrfToken() },
      });
      if (!resp.ok) throw new Error((await resp.json()).erro || "falha");
      const f = await resp.json();
      ph.outerHTML = fotoTemplate(f.id, f.url, f.descricao);
    } catch (e) {
      ph.outerHTML = `<figure class="foto foto-erro" title="${e.message}">⚠️ Erro</figure>`;
    }
    atualizarContagem(comodoId);
    habilitarArrasto(grid);
  }
}

function fotoTemplate(id, url, descricao) {
  return `
  <figure class="foto" data-foto-id="${id}">
    <img src="${url}" loading="lazy" alt="">
    <textarea class="foto-desc" placeholder="Descrição da foto…"
              onchange="salvarDescricao(${id}, this)">${escapeHtml(descricao || "")}</textarea>
    <button class="foto-ia" title="Editar com IA" onclick="abrirEditarIA(${id}, this)">✨</button>
    <button class="foto-del" title="Remover foto" onclick="excluirFoto(${id}, this)">✕</button>
  </figure>`;
}

let descTimers = {};
function salvarDescricao(id, el) {
  postForm(`/foto/${id}/descricao`, { descricao: el.value });
  el.classList.add("saved");
  setTimeout(() => el.classList.remove("saved"), 800);
}

async function excluirFoto(id, btn) {
  if (!confirm("Remover esta foto?")) return;
  const resp = await postForm(`/foto/${id}/excluir`, {});
  if (resp.ok) {
    const fig = btn.closest(".foto");
    const comodo = fig.closest(".comodo").dataset.comodoId;
    fig.remove();
    atualizarContagem(comodo);
  }
}

function atualizarContagem(comodoId) {
  const sec = document.querySelector(`[data-comodo-id="${comodoId}"]`);
  const n = sec.querySelectorAll(".foto[data-foto-id]").length;
  sec.querySelector(".foto-count").textContent = `${n} foto(s)`;
  const hint = sec.querySelector(".drag-hint");
  if (hint) hint.hidden = n < 2;
}

function escapeHtml(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

// Abre uma imagem em tela cheia (lightbox). Usado na grade e no pop-up de IA.
function abrirLightbox(src) {
  if (!src) return;
  document.getElementById("lightbox-img").src = src;
  document.getElementById("lightbox").showModal();
}

// -------------------------------------------------- Arrastar / reordenar
// Implementação própria com Pointer Events (funciona no mouse e no toque),
// sem depender de bibliotecas externas. A foto é arrastada pela imagem.
let arrasto = null;

function habilitarArrasto(grid) {
  grid.querySelectorAll(".foto[data-foto-id]").forEach((item) => {
    if (item.dataset.dragReady) return;
    item.dataset.dragReady = "1";
    const handle = item.querySelector("img");
    if (!handle) return;
    handle.style.touchAction = "none";
    handle.addEventListener("pointerdown", (e) => iniciarArrasto(e, grid, item, handle));
  });
}

function iniciarArrasto(e, grid, item, handle) {
  if (arrasto || e.button === 2) return;     // ignora clique direito
  e.preventDefault();

  // Ainda não começa a arrastar: só registra o ponto inicial. O arraste de
  // verdade começa quando o ponteiro se move além do limiar (ver aoMover).
  // Se soltar sem mover, é um clique → abre a imagem em tela cheia.
  arrasto = {
    grid, item, handle,
    startX: e.clientX,
    startY: e.clientY,
    iniciado: false,
  };

  handle.setPointerCapture(e.pointerId);
  handle.addEventListener("pointermove", aoMover);
  handle.addEventListener("pointerup", aoSoltar);
  handle.addEventListener("pointercancel", aoCancelar);
}

// Promove o estado "pendente" para um arraste de verdade (a foto passa a flutuar).
function comecarArrasto() {
  const { item, startX, startY } = arrasto;
  const rect = item.getBoundingClientRect();

  // espaço tracejado que mostra onde a foto vai cair
  const placeholder = document.createElement("div");
  placeholder.className = "foto-placeholder";
  placeholder.style.height = rect.height + "px";
  item.after(placeholder);

  arrasto.placeholder = placeholder;
  arrasto.dx = startX - rect.left;
  arrasto.dy = startY - rect.top;
  arrasto.iniciado = true;

  // a foto "flutua" e segue o ponteiro
  item.classList.add("dragging");
  Object.assign(item.style, {
    width: rect.width + "px",
    height: rect.height + "px",
    position: "fixed",
    margin: "0",
    zIndex: "1000",
  });
  document.body.classList.add("arrastando");
}

function moverFlutuante(x, y) {
  arrasto.item.style.left = x - arrasto.dx + "px";
  arrasto.item.style.top = y - arrasto.dy + "px";
}

function aoMover(e) {
  if (!arrasto) return;
  if (!arrasto.iniciado) {
    // só vira arraste depois de mover ~6px; abaixo disso ainda pode ser clique
    const dist = Math.hypot(e.clientX - arrasto.startX, e.clientY - arrasto.startY);
    if (dist < 6) return;
    comecarArrasto();
  }
  moverFlutuante(e.clientX, e.clientY);
  rolarSeNecessario(e.clientY);
  const ref = posicaoDestino(arrasto.grid, e.clientX, e.clientY);
  if (ref == null) arrasto.grid.appendChild(arrasto.placeholder);
  else if (ref !== arrasto.placeholder) arrasto.grid.insertBefore(arrasto.placeholder, ref);
}

// rolagem automática quando arrasta perto do topo/rodapé da tela
function rolarSeNecessario(y) {
  const margem = 80;
  if (y < margem) window.scrollBy(0, -12);
  else if (y > window.innerHeight - margem) window.scrollBy(0, 12);
}

function desligarArrasto() {
  const { handle } = arrasto;
  handle.removeEventListener("pointermove", aoMover);
  handle.removeEventListener("pointerup", aoSoltar);
  handle.removeEventListener("pointercancel", aoCancelar);
}

function aoSoltar() {
  if (!arrasto) return;
  const { grid, item, handle, placeholder, iniciado } = arrasto;
  desligarArrasto();

  if (!iniciado) {
    // não arrastou: foi um clique → abre a imagem em tela cheia
    arrasto = null;
    abrirLightbox(handle.src);
    return;
  }

  grid.insertBefore(item, placeholder);
  placeholder.remove();
  item.classList.remove("dragging");
  item.style.cssText = "";
  document.body.classList.remove("arrastando");
  arrasto = null;
  salvarOrdem(grid);
}

// Cancelamento (ex.: rolagem no toque): desfaz sem abrir o lightbox.
function aoCancelar() {
  if (!arrasto) return;
  const { grid, item, placeholder, iniciado } = arrasto;
  desligarArrasto();
  if (iniciado) {
    grid.insertBefore(item, placeholder);
    placeholder.remove();
    item.classList.remove("dragging");
    item.style.cssText = "";
    document.body.classList.remove("arrastando");
  }
  arrasto = null;
}

// Retorna o elemento antes do qual o arrastado deve ser inserido (ou null = fim)
function posicaoDestino(grid, x, y) {
  const itens = [...grid.querySelectorAll(".foto:not(.dragging)")];
  let maisProximo = Infinity;
  let ref = null;
  for (const it of itens) {
    const b = it.getBoundingClientRect();
    const cx = b.left + b.width / 2;
    const cy = b.top + b.height / 2;
    const dist = Math.hypot(x - cx, y - cy);
    if (dist < maisProximo) {
      maisProximo = dist;
      ref = x < cx ? it : it.nextElementSibling;
    }
  }
  return ref;
}

function salvarOrdem(grid) {
  const ids = [...grid.querySelectorAll(".foto[data-foto-id]")]
    .map((f) => f.dataset.fotoId);
  if (ids.length) postForm(`/comodo/${grid.dataset.grid}/reordenar`,
                           { ordem: ids.join(",") });
}

// Inicializa o arrasto nas grades já existentes ao carregar a página.
document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".foto-grid").forEach(habilitarArrasto);
});

// --------------------------------------------------- Edição por IA (OpenAI)
let iaState = null; // { fotoId, gridImg, temPreview }

function abrirEditarIA(fotoId, btn) {
  if (!window.IA_ATIVA) {
    alert("A edição por IA ainda não está configurada.\n\n" +
          "Crie um arquivo .env na pasta do projeto com a linha:\n" +
          "OPENAI_API_KEY=sua_chave_aqui\n\n" +
          "Depois reinicie o servidor (python app.py).");
    return;
  }
  const gridImg = btn.closest(".foto").querySelector("img");
  iaState = { fotoId, gridImg, temPreview: false };

  document.getElementById("ia-original").src = gridImg.src;
  document.getElementById("ia-prompt").value = "";
  resetarResultadoIA();
  document.getElementById("ia-modal").showModal();
  document.getElementById("ia-prompt").focus();
}

function resetarResultadoIA() {
  document.getElementById("ia-result-box").innerHTML =
    '<div class="ia-result-empty">' +
    '<span class="ia-result-icon">🖼️</span>' +
    '<span class="muted">Gere para ver o resultado aqui</span></div>';
  document.getElementById("ia-aplicar").hidden = true;
  document.getElementById("ia-gerar").disabled = false;
}

async function gerarIA() {
  if (!iaState) return;
  const prompt = document.getElementById("ia-prompt").value.trim();
  if (!prompt) { document.getElementById("ia-prompt").focus(); return; }

  const box = document.getElementById("ia-result-box");
  const gerar = document.getElementById("ia-gerar");
  box.innerHTML = '<div class="spinner"></div><p class="muted">Gerando… ' +
                  'isso pode levar alguns segundos.</p>';
  gerar.disabled = true;
  document.getElementById("ia-aplicar").hidden = true;

  try {
    const resp = await postForm(`/foto/${iaState.fotoId}/editar-ia`, { prompt });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.erro || "Falha ao gerar.");
    box.innerHTML = `<img src="${data.preview_url}?t=${Date.now()}" alt="" onclick="abrirLightbox(this.src)">`;
    iaState.temPreview = true;
    document.getElementById("ia-aplicar").hidden = false;
  } catch (e) {
    box.innerHTML = `<p class="ia-erro">⚠️ ${escapeHtml(e.message)}</p>`;
  } finally {
    gerar.disabled = false;
  }
}

async function aplicarIA() {
  if (!iaState || !iaState.temPreview) return;
  const resp = await postForm(`/foto/${iaState.fotoId}/aplicar-edicao`, {});
  const data = await resp.json();
  if (!resp.ok) { alert(data.erro || "Falha ao aplicar."); return; }
  // atualiza a foto na tela (cache-bust) e fecha
  iaState.gridImg.src = data.url + "?t=" + Date.now();
  iaState.temPreview = false;
  document.getElementById("ia-modal").close();
  iaState = null;
}

async function fecharIA() {
  // descarta a prévia não aplicada, se houver
  if (iaState && iaState.temPreview) {
    try { await postForm(`/foto/${iaState.fotoId}/descartar-edicao`, {}); }
    catch (e) { /* ignora */ }
  }
  document.getElementById("ia-modal").close();
  iaState = null;
}
