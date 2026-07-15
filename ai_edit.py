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
    '"status":"Pendente OU Em andamento OU Concluído"}]}. '
    'Use "" quando a informação não estiver no texto. Não invente fatos '
    "novos, mas ESCREVA TUDO EM PORTUGUÊS CORRETO: transcrições de áudio "
    "vêm com erros de digitação, ortografia e acentuação — corrija-os "
    '(ex.: "Arquitetta" → "Arquiteta", "eletrecista" → "eletricista", '
    '"reuniao" → "reunião"). Capitalize nomes próprios e cargos '
    'adequadamente. No campo "empresa" de cada participante, coloque a '
    "empresa OU a função/papel citado no texto (ex.: Cliente, Arquiteta, "
    "Eletricista da construtora) — não deixe vazio se o texto informar. "
    "ASSUNTOS — siga à risca o padrão da empresa: "
    "(1) Um assunto para CADA ponto tratado na reunião — cada decisão, "
    "pendência, definição ou problema vira um item próprio. Não agrupe "
    "pontos distintos num tema genérico; uma reunião cheia pode render "
    "20-30 assuntos. "
    '(2) "titulo": específico e descritivo, podendo ter subtema após um '
    'hífen. Exemplos do padrão: "Escada - degrau fora do eixo", "Banheiro '
    'do Marcelo - revestimento e grelha do box", "Pendência de iluminação '
    'da varanda e sob o duto", "Altura do guarda-corpo de vidro". '
    '(3) "descricao": 1 a 3 frases completas e informativas, registrando '
    "o que foi discutido e decidido, INCLUINDO medidas, alternativas "
    "avaliadas, justificativas e encaminhamentos citados no texto. "
    'Exemplos do padrão: "Definição da peça de revestimento do box e '
    "avaliação de dividir a grelha ao meio (já comprada, ainda não "
    'produzida) para reduzir o peso da peça.", "Altura atual de 1,20 m '
    "tecnicamente segura, porém equipe avalia elevar entre 10 e 20 cm "
    'adicionais por questão de sensação de segurança e estética.". '
    '(4) "responsavel" e "prazo": preencha sempre que o texto indicar '
    'quem cuida do ponto ou até quando (ex.: "Camila (AQ Design)", '
    '"Final de junho"); se não houver indicação, deixe "". '
    '(5) "status": classifique CADA assunto individualmente — não use '
    '"Pendente" como padrão. "Concluído" = já resolvido/decidido/liberado. '
    '"Em andamento" = execução iniciada, em teste, em revisão, em '
    "contratação ou aguardando retorno já encaminhado (ex.: primeira etapa "
    "executada, área em teste, orçamento sendo enviado, aguardando desenho "
    'já pedido). "Pendente" = ainda sem definição nem encaminhamento. '
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

    # Benchmark de 15/07/2026 (mesma reunião real, 6 modelos): o gpt-5.4-mini
    # foi o mais rápido (10,7s vs 48s do gpt-4o-mini) e o mais aderente ao
    # padrão da ata (títulos "tema - subtema", responsáveis, status).
    model = os.environ.get("OPENAI_TEXT_MODEL", "gpt-5.4-mini")
    # timeout: sem ele o SDK espera até 10 min e o usuário fica sem resposta.
    client = OpenAI(api_key=api_key, timeout=60)
    try:
        resposta = client.chat.completions.create(
            model=model,
            response_format={"type": "json_object"},
            # Reuniões longas rendem 20-30 assuntos detalhados; com limite
            # baixo o JSON vem cortado pela metade e a extração falha.
            max_completion_tokens=6000,
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
