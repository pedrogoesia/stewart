// Harness (assistente) — saudação por horário + chat (por enquanto só front).
(function () {
  // Saudação conforme a hora local do usuário.
  const saud = document.getElementById("saud");
  if (saud) {
    const h = new Date().getHours();
    saud.textContent = h < 12 ? "Bom dia" : (h < 18 ? "Bom dia" : "Bom dia");
  }

  const form = document.getElementById("harnessForm");
  if (!form) return;
  const input = document.getElementById("harnessInput");
  const conversa = document.getElementById("conversa");

  function ajustarAltura() {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 200) + "px";
  }
  input.addEventListener("input", ajustarAltura);

  function bolha(texto, quem) {
    const d = document.createElement("div");
    d.className = "msg msg-" + quem;
    d.textContent = texto;
    conversa.appendChild(d);
    d.scrollIntoView({ behavior: "smooth", block: "end" });
  }

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const texto = input.value.trim();
    if (!texto) return;
    document.body.classList.add("harness-ativa");
    bolha(texto, "user");
    input.value = "";
    ajustarAltura();
    input.focus();
    setTimeout(() => {
      bolha("A Stewart OS conecta contexto operacional, dados da companhia e " +
            "agentes de IA para apoiar consultas, rotinas e decisões com mais " +
            "clareza.", "bot");
    }, 300);
  });

  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      form.requestSubmit();
    }
  });
})();
