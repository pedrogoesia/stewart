"""
Edição de fotos por prompt usando a OpenAI (modelo de imagem mais recente,
gpt-image-1 — o mesmo do ChatGPT). Recebe uma imagem + uma instrução em texto
(ex.: "remova a vassoura desta foto") e devolve os bytes (JPEG) da nova imagem.

A chave de API é lida da variável de ambiente OPENAI_API_KEY (nunca é gravada
no código nem no repositório). O modelo pode ser trocado pela variável
OPENAI_IMAGE_MODEL.
"""

import base64
import io
import os

from PIL import Image


def ia_disponivel():
    return bool(os.environ.get("OPENAI_API_KEY"))


def editar_imagem(caminho_entrada, prompt):
    """Edita a imagem conforme o prompt e retorna os bytes (JPEG) da nova foto.

    Lança RuntimeError com mensagem amigável em caso de erro/recusa.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "A chave da OpenAI não está configurada. Crie um arquivo .env "
            "com OPENAI_API_KEY=suachave (veja o .env.example).")

    prompt = (prompt or "").strip()
    if not prompt:
        raise RuntimeError("Descreva a alteração desejada.")

    # Importação adiada: só exige o SDK se a edição por IA for usada.
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(
            "Biblioteca da OpenAI não instalada. Rode: "
            "pip install -r requirements.txt") from exc

    model = os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-1")
    client = OpenAI(api_key=api_key)

    try:
        with open(caminho_entrada, "rb") as arquivo:
            resposta = client.images.edit(
                model=model,
                image=arquivo,
                prompt=prompt,
                input_fidelity="high",   # preserva o restante da foto
                output_format="jpeg",
                size="auto",
            )
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(_mensagem_amigavel(exc)) from exc

    dados = getattr(resposta, "data", None) or []
    b64 = getattr(dados[0], "b64_json", None) if dados else None
    if not b64:
        raise RuntimeError("A OpenAI não retornou uma imagem editada. "
                           "Tente reformular a instrução.")
    return _para_jpeg(base64.b64decode(b64))


def _mensagem_amigavel(exc):
    """Transforma erros técnicos da OpenAI em mensagens curtas e claras."""
    txt = str(exc)
    low = txt.lower()
    if "must be verified" in low or "verify organization" in low or \
       "organization verification" in low:
        return ("Sua organização na OpenAI precisa ser verificada para usar o "
                "gpt-image-1. Faça a verificação em "
                "platform.openai.com/settings/organization/general e aguarde "
                "alguns minutos.")
    if "insufficient_quota" in low or "exceeded your current quota" in low or \
       "billing" in low:
        return ("Sem créditos/cota na conta da OpenAI. Adicione créditos em "
                "platform.openai.com/account/billing e tente novamente.")
    if "rate limit" in low or "429" in txt:
        return ("Limite de requisições da OpenAI atingido. Aguarde alguns "
                "segundos e tente novamente.")
    if "invalid api key" in low or "incorrect api key" in low or \
       "401" in txt or "authentication" in low:
        return ("Chave da OpenAI inválida. Confira o OPENAI_API_KEY no "
                "arquivo .env.")
    if "content policy" in low or "safety" in low or "moderation" in low or \
       "rejected" in low:
        return ("A instrução foi recusada pela política de conteúdo da OpenAI. "
                "Tente reformular.")
    if "model" in low and ("not found" in low or "does not exist" in low):
        return ("Modelo de imagem não encontrado. Ajuste OPENAI_IMAGE_MODEL no "
                ".env (padrão: gpt-image-1).")
    if "timeout" in low or "timed out" in low:
        return ("Tempo esgotado ao falar com a OpenAI. Verifique a internet e "
                "tente novamente.")
    return f"Erro ao chamar a OpenAI: {txt[:300]}"


def _para_jpeg(dados):
    """Normaliza os bytes retornados para JPEG."""
    img = Image.open(io.BytesIO(dados))
    if img.mode != "RGB":
        img = img.convert("RGB")
    saida = io.BytesIO()
    img.save(saida, "JPEG", quality=90, optimize=True)
    return saida.getvalue()
