// Stewart — interações da página da obra (upload, descrições, cômodos).

function postForm(url, data) {
  const fd = new FormData();
  for (const k in data) fd.append(k, data[k]);
  return fetch(url, { method: "POST", body: fd });
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
  document.querySelector(`[data-comodo-id="${c.id}"]`)
    .scrollIntoView({ behavior: "smooth", block: "center" });
}

function comodoTemplate(id, nome) {
  return `
  <section class="comodo" data-comodo-id="${id}">
    <div class="comodo-head">
      <h2 class="comodo-nome" data-id="${id}">${escapeHtml(nome)}</h2>
      <div class="comodo-tools">
        <span class="badge foto-count">0 foto(s)</span>
        <button class="btn btn-sm btn-ghost" onclick="renomearComodo(${id})">Renomear</button>
        <button class="btn btn-sm btn-ghost-danger" onclick="excluirComodo(${id})">Excluir</button>
      </div>
    </div>
    <label class="dropzone">
      <input type="file" accept="image/*" multiple capture="environment"
             onchange="enviarFotos(this, ${id})" hidden>
      <span class="dropzone-inner">📷 Adicionar fotos &nbsp;<small>(toque para tirar foto ou escolher da galeria)</small></span>
    </label>
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
      });
      if (!resp.ok) throw new Error((await resp.json()).erro || "falha");
      const f = await resp.json();
      ph.outerHTML = fotoTemplate(f.id, f.url, f.descricao);
    } catch (e) {
      ph.outerHTML = `<figure class="foto foto-erro" title="${e.message}">⚠️ Erro</figure>`;
    }
    atualizarContagem(comodoId);
  }
}

function fotoTemplate(id, url, descricao) {
  return `
  <figure class="foto" data-foto-id="${id}">
    <img src="${url}" loading="lazy" alt="">
    <textarea class="foto-desc" placeholder="Descrição da foto…"
              onchange="salvarDescricao(${id}, this)">${escapeHtml(descricao || "")}</textarea>
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
}

function escapeHtml(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}
