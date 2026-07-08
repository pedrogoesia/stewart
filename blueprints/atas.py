"""Ferramenta: Assistente de Atas de Reunião.

Serve o gerador de atas (HTML autocontido, monta o .docx com JSZip no
navegador). O arquivo vive em tools/assistente_atas.html e é servido atrás do
login — por isso NÃO fica em static/ (que é público). O JSZip é servido
localmente (static/js), então funciona offline e respeita a CSP do portal
(script-src 'self').

O botão "Preencher com IA" envia a transcrição para POST /atas/ia, que extrai
os campos via OpenAI (mesma chave do editor de fotos). O token CSRF é injetado
no HTML na hora de servir (placeholder __CSRF_TOKEN__).

Mantido em sincronia com o gerador do Claude (gerar_ata_docx.py): mudança de
layout (cores, margens, campos) deve ser aplicada nos dois.
"""

import os

from flask import Blueprint, Response, jsonify, request
from flask_login import login_required
from flask_wtf.csrf import generate_csrf

from ai_edit import extrair_dados_ata, ia_disponivel
from extensions import limiter
from models import registrar_atividade

bp = Blueprint("atas", __name__)

_TOOL_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "tools", "assistente_atas.html")

# Limite de tamanho da transcrição enviada à IA (caracteres).
_MAX_TEXTO = 60_000


@bp.route("/atas")
@login_required
def index():
    registrar_atividade("atas_abriu", "Abriu o Assistente de Atas")
    with open(_TOOL_PATH, encoding="utf-8") as f:
        html = f.read()
    html = html.replace("__CSRF_TOKEN__", generate_csrf())
    return Response(html, mimetype="text/html")


@bp.route("/atas/ia", methods=["POST"])
@login_required
@limiter.limit("30 per hour")
def preencher_ia():
    if not ia_disponivel():
        return jsonify({"erro": "O preenchimento por IA não está configurado "
                        "neste servidor. Preencha os campos manualmente."}), 400
    dados = request.get_json(silent=True) or {}
    texto = (dados.get("texto") or "").strip()
    if not texto:
        return jsonify({"erro": "Cole a transcrição ou as anotações "
                        "primeiro."}), 400
    if len(texto) > _MAX_TEXTO:
        return jsonify({"erro": "O texto é muito longo. Reduza para até "
                        f"{_MAX_TEXTO // 1000} mil caracteres."}), 400
    try:
        campos = extrair_dados_ata(texto)
    except Exception as e:  # noqa: BLE001
        return jsonify({"erro": str(e)}), 502
    registrar_atividade("atas_ia", "Preencheu a ata com IA")
    return jsonify(campos)
