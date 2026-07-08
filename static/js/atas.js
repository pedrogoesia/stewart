// Stewart — interações do Assistente de Atas (participantes, assuntos,
// preenchimento por IA e geração do .docx no navegador via AtaDocx + JSZip).

const $ = id => document.getElementById(id);
const partsBox = $("participantes"), topicsBox = $("assuntos");

function csrfToken() {
  const meta = document.querySelector('meta[name="csrf-token"]');
  return meta ? meta.getAttribute("content") : "";
}

// ---------------------------------------------------- Linhas dinâmicas
function partRow(p = {}) {
  const div = document.createElement("div");
  div.className = "ata-row";
  div.innerHTML = `
    <div class="ata-row-head"><span class="ata-row-n">Participante</span>
      <button class="ata-x" type="button" title="Remover">×</button></div>
    <div class="ata-grid-2">
      <div class="ata-field"><label>Nome</label><input type="text" class="p-nome" placeholder="Nome completo"></div>
      <div class="ata-field"><label>Empresa / Função</label><input type="text" class="p-emp" placeholder="Ex.: Cliente, Arquiteta, Construtora"></div>
    </div>`;
  div.querySelector(".p-nome").value = p.nome || "";
  div.querySelector(".p-emp").value = p.empresa || "";
  div.querySelector(".ata-x").onclick = () => div.remove();
  partsBox.appendChild(div);
}

function topicRow(a = {}) {
  const div = document.createElement("div");
  div.className = "ata-row";
  div.innerHTML = `
    <div class="ata-row-head"><span class="ata-row-n">Assunto</span>
      <button class="ata-x" type="button" title="Remover">×</button></div>
    <div class="ata-field"><label>Título</label><input type="text" class="t-tit" placeholder="Ex.: Revestimento dos banheiros"></div>
    <div class="ata-field"><label>Descrição / decisão</label><textarea class="t-desc" placeholder="O que foi tratado e decidido"></textarea></div>
    <div class="ata-grid-3">
      <div class="ata-field"><label>Responsável</label><input type="text" class="t-resp" placeholder="Quem"></div>
      <div class="ata-field"><label>Prazo</label><input type="text" class="t-prazo" placeholder="Ex.: 03/07/2026"></div>
      <div class="ata-field"><label>Status</label><select class="t-status">
        <option>Pendente</option><option>Em andamento</option><option>Concluído</option></select></div>
    </div>`;
  div.querySelector(".t-tit").value = a.titulo || "";
  div.querySelector(".t-desc").value = a.descricao || "";
  div.querySelector(".t-resp").value = a.responsavel || "";
  div.querySelector(".t-prazo").value = a.prazo || "";
  if (a.status) div.querySelector(".t-status").value = a.status;
  div.querySelector(".ata-x").onclick = () => div.remove();
  topicsBox.appendChild(div);
}

$("addPart").onclick = () => partRow();
$("addTopic").onclick = () => topicRow();
partRow(); partRow(); topicRow();

// ---------------------------------------------------- Coleta dos campos
function collect() {
  const participantes = [...partsBox.querySelectorAll(".ata-row")].map(r => ({
    nome: r.querySelector(".p-nome").value.trim(),
    empresa: r.querySelector(".p-emp").value.trim(),
  })).filter(p => p.nome || p.empresa);
  const assuntos = [...topicsBox.querySelectorAll(".ata-row")].map(r => ({
    titulo: r.querySelector(".t-tit").value.trim(),
    descricao: r.querySelector(".t-desc").value.trim(),
    responsavel: r.querySelector(".t-resp").value.trim(),
    prazo: r.querySelector(".t-prazo").value.trim(),
    status: r.querySelector(".t-status").value,
  })).filter(a => a.titulo || a.descricao);
  return {
    cliente: $("cliente").value.trim(), obra: $("obra").value.trim(),
    numero: $("numero").value.trim() || "00", endereco: $("endereco").value.trim(),
    data: $("data").value.trim(), local: $("local").value.trim(),
    prazo_aprovacao: $("prazo_aprovacao").value.trim() || "2 (dois) dias úteis",
    participantes, assuntos,
  };
}

// ---------------------------------------------------- Logo do documento
// Buscado uma única vez do servidor (em vez de embutido em base64 na página).
let _logoB64 = null;
async function logoB64() {
  if (_logoB64) return _logoB64;
  const resp = await fetch(window.ATA_LOGO_URL);
  if (!resp.ok) throw new Error("Não foi possível carregar o logo do documento.");
  const bytes = new Uint8Array(await resp.arrayBuffer());
  let bin = "";
  for (let i = 0; i < bytes.length; i += 0x8000) {
    bin += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
  }
  _logoB64 = btoa(bin);
  return _logoB64;
}

// ---------------------------------------------------- Gerar .docx
$("btnGerar").onclick = async () => {
  const st = $("genStatus");
  st.className = "ata-status"; st.textContent = "Gerando...";
  try {
    const d = collect();
    if (!d.cliente) { st.className = "ata-status err"; st.textContent = "Informe ao menos o cliente."; return; }
    const parts = window.AtaDocx.buildDocxParts(d, await logoB64());
    const zip = new JSZip();
    for (const [p, v] of Object.entries(parts)) {
      if (v.text != null) zip.file(p, v.text);
      else zip.file(p, v.b64, { base64: true });
    }
    const blob = await zip.generateAsync({
      type: "blob",
      mimeType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      compression: "DEFLATE",
    });
    const nome = "Obra_" + ((d.obra || d.cliente).replace(/[^\w\-]+/g, "_")) +
      "_Ata_de_reuniao_" + String(d.numero).padStart(2, "0") + ".docx";
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = nome;
    document.body.appendChild(a); a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1500);
    st.className = "ata-status ok"; st.textContent = "Ata gerada: " + nome;
  } catch (e) {
    st.className = "ata-status err"; st.textContent = "Não foi possível gerar: " + e.message;
  }
};

// ---------------------------------------------------- Preencher com IA
$("btnIA").onclick = async () => {
  const st = $("iaStatus"), txt = $("fonte").value.trim();
  if (!txt) { st.className = "ata-status err"; st.textContent = "Cole a transcrição ou as anotações primeiro."; return; }
  st.className = "ata-status"; st.textContent = "Analisando o texto...";
  $("btnIA").disabled = true;
  try {
    const resp = await fetch("/atas/ia", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
      body: JSON.stringify({ texto: txt }),
    });
    const j = await resp.json();
    if (!resp.ok) throw new Error(j.erro || "Não foi possível analisar o texto.");
    const setv = (id, v) => { if (v) $(id).value = v; };
    setv("cliente", j.cliente); setv("obra", j.obra); setv("numero", j.numero);
    setv("endereco", j.endereco); setv("data", j.data); setv("local", j.local);
    if (Array.isArray(j.participantes) && j.participantes.length) {
      partsBox.innerHTML = ""; j.participantes.forEach(p => partRow(p));
    }
    if (Array.isArray(j.assuntos) && j.assuntos.length) {
      topicsBox.innerHTML = ""; j.assuntos.forEach(a => topicRow(a));
    }
    st.className = "ata-status ok"; st.textContent = "Campos preenchidos — revise antes de gerar.";
  } catch (e) {
    st.className = "ata-status err";
    st.textContent = e.message || "Não consegui preencher automaticamente. Tente de novo ou preencha os campos manualmente.";
  } finally {
    $("btnIA").disabled = false;
  }
};
