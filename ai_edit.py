"""
Integrações com a OpenAI usadas pelas ferramentas do portal:

- Edição de fotos por prompt (gpt-image-1, o mesmo do ChatGPT): recebe uma
  imagem + uma instrução (ex.: "remova a vassoura desta foto") e devolve os
  bytes (JPEG) da nova imagem.
- Extração de dados de ata: recebe a transcrição/anotações da reunião e
  devolve os campos estruturados (cliente, participantes, assuntos...).

A chave de API é lida da variável de ambiente OPENAI_API_KEY (nunca é gravada
no código nem no repositório). Os modelos podem ser trocados pelas variáveis
OPENAI_IMAGE_MODEL e OPENAI_TEXT_MODEL.
"""

import base64
import io
import json
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


_ATA_INSTRUCOES = (
    "Você extrai dados de reuniões de obra e responde APENAS com um objeto "
    "JSON válido, sem texto antes ou depois, sem markdown. Esquema: "
    '{"cliente":"","obra":"","numero":"","endereco":"","data":"","local":"",'
    '"participantes":[{"nome":"","empresa":""}],'
    '"assuntos":[{"titulo":"","descricao":"","responsavel":"","prazo":"",'
    '"status":"Pendente"}]}. '
    'Use "" quando a informação não estiver no texto. Não invente fatos '
    "novos, mas ESCREVA TUDO EM PORTUGUÊS CORRETO: transcrições de áudio "
    "vêm com erros de digitação, ortografia e acentuação — corrija-os "
    '(ex.: "Arquitetta" → "Arquiteta", "eletrecista" → "eletricista", '
    '"reuniao" → "reunião"). Capitalize nomes próprios e cargos '
    'adequadamente. No campo "empresa" de cada participante, coloque a '
    "empresa OU a função/papel citado no texto (ex.: Cliente, Arquiteta, "
    "Eletricista da construtora) — não deixe vazio se o texto informar. "
    "ASSUNTOS — siga à risca o padrão da empresa: "
    "(1) Agrupe a reunião em POUCOS temas macro, tipicamente 5 a 10 — um "
    "assunto por TEMA, nunca um por micro-decisão, comentário ou detalhe. "
    "Se vários pontos tratam do mesmo tema (ex.: várias decisões sobre a "
    "escada), vire UM assunto só. "
    '(2) "titulo": um rótulo curto de 1 a 4 palavras, como '
    '"Grelhas", "Iluminação", "Projeto do Spa", "Concretagem", '
    '"Banheiro do Marcelo". Sem travessões nem subtítulos. '
    '(3) "descricao": UMA frase curta e objetiva (no máximo ~15 palavras) '
    "dizendo o que foi tratado, SEM medidas, justificativas, alternativas "
    'discutidas ou nomes de pessoas. Exemplos do padrão: "Discussão sobre '
    'o avanço da laje e posicionamento da escada.", "Medições e discussões '
    'sobre grelhas no banheiro e sua divisão.", "Ajustes na iluminação na '
    'varanda e soluções alternativas.", "Especificações sobre como '
    'proceder com a concretagem.". '
    '(4) "responsavel" e "prazo": preencha somente se estiverem ditos de '
    'forma explícita e inequívoca no texto; na dúvida, deixe "". '
    "Português do Brasil.")


def extrair_dados_ata(texto):
    """Extrai os campos da ata a partir da transcrição/anotações da reunião.

    Retorna um dict no esquema de _ATA_INSTRUCOES. Lança RuntimeError com
    mensagem amigável em caso de erro.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "A chave da OpenAI não está configurada. Crie um arquivo .env "
            "com OPENAI_API_KEY=suachave (veja o .env.example).")

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(
            "Biblioteca da OpenAI não instalada. Rode: "
            "pip install -r requirements.txt") from exc

    model = os.environ.get("OPENAI_TEXT_MODEL", "gpt-4o-mini")
    # timeout: sem ele o SDK espera até 10 min e o usuário fica sem resposta.
    client = OpenAI(api_key=api_key, timeout=60)
    try:
        resposta = client.chat.completions.create(
            model=model,
            response_format={"type": "json_object"},
            max_completion_tokens=1500,
            messages=[{"role": "system", "content": _ATA_INSTRUCOES},
                      {"role": "user", "content": texto}],
        )
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(_mensagem_amigavel(exc)) from exc

    conteudo = (resposta.choices[0].message.content or "").strip()
    try:
        return json.loads(conteudo)
    except ValueError as exc:
        raise RuntimeError("A IA não retornou dados válidos. Tente novamente "
                           "ou preencha os campos manualmente.") from exc


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
