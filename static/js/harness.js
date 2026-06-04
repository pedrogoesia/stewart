// Harness (assistente) — comportamento de chat. Por enquanto é só front:
// ainda não há back-end de IA, então o assistente responde com um aviso.
(function () {
  const form = document.getElementById("harnessForm");
  if (!form) return;
  const input = document.getElementById("harnessInput");
  const conversa = document.getElementById("conversa");
  const intro = document.getElementById("harnessIntro");

  // textarea cresce conforme o texto
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
    if (intro) intro.style.display = "none";
    bolha(texto, "user");
    input.value = "";
    ajustarAltura();
    input.focus();
    setTimeout(() => {
      bolha("🚧 O assistente da Stewart ainda está em construção. Em breve " +
            "vou poder te ajudar por aqui. Por enquanto, use as ferramentas " +
            "na barra lateral.", "bot");
    }, 300);
  });

  // Enter envia; Shift+Enter quebra linha
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      form.requestSubmit();
    }
  });
})();
