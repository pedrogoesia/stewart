"""
Edição de fotos por prompt usando o Google Gemini (modelo de imagem
"Nano Banana"). Recebe uma imagem + uma instrução em texto (ex.: "remova a
vassoura desta foto") e devolve os bytes da nova imagem editada.

A chave de API é lida da variável de ambiente GEMINI_API_KEY (nunca é gravada
no código nem no repositório). O modelo pode ser trocado pela variável
GEMINI_IMAGE_MODEL.
"""

import io
import os

from PIL import Image


def ia_disponivel():
    return bool(os.environ.get("GEMINI_API_KEY"))


def editar_imagem(caminho_entrada, prompt):
    """Edita a imagem conforme o prompt e retorna os bytes (JPEG) da nova foto.

    Lança RuntimeError com mensagem amigável em caso de erro/recusa.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "A chave do Gemini não está configurada. Crie um arquivo .env "
            "com GEMINI_API_KEY=suachave (veja o .env.example).")

    prompt = (prompt or "").strip()
    if not prompt:
        raise RuntimeError("Descreva a alteração desejada.")

    # Importação adiada: só exige o SDK se a edição por IA for usada.
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise RuntimeError(
            "Biblioteca do Gemini não instalada. Rode: "
            "pip install -r requirements.txt") from exc

    model = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")
    client = genai.Client(api_key=api_key)

    imagem = Image.open(caminho_entrada)
    imagem.load()

    try:
        resposta = client.models.generate_content(
            model=model,
            contents=[prompt, imagem],
            config=types.GenerateContentConfig(
                response_modalities=[types.Modality.IMAGE, types.Modality.TEXT],
            ),
        )
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Erro ao chamar o Gemini: {exc}") from exc

    candidatos = getattr(resposta, "candidates", None) or []
    if not candidatos:
        raise RuntimeError("O Gemini não retornou resultado (a instrução pode "
                           "ter sido bloqueada). Tente reformular.")

    conteudo = getattr(candidatos[0], "content", None)
    partes = getattr(conteudo, "parts", None) if conteudo else None
    if not partes:
        motivo = getattr(candidatos[0], "finish_reason", "")
        raise RuntimeError("O Gemini não devolveu conteúdo"
                           + (f" (motivo: {motivo})." if motivo else ".")
                           + " Tente reformular a instrução.")

    textos = []
    for parte in partes:
        dados = getattr(parte, "inline_data", None)
        if dados and getattr(dados, "data", None):
            return _para_jpeg(dados.data)
        if getattr(parte, "text", None):
            textos.append(parte.text)

    detalhe = " ".join(textos).strip()
    raise RuntimeError(
        "O Gemini não devolveu uma imagem editada."
        + (f" Resposta: {detalhe[:300]}" if detalhe else
           " Tente reformular a instrução."))


def _para_jpeg(dados):
    """Normaliza os bytes retornados (PNG/JPEG) para JPEG."""
    img = Image.open(io.BytesIO(dados))
    if img.mode not in ("RGB",):
        img = img.convert("RGB")
    saida = io.BytesIO()
    img.save(saida, "JPEG", quality=90, optimize=True)
    return saida.getvalue()
