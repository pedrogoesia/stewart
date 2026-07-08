"""Ferramenta: Assistente de Atas de Reunião.

Página integrada ao layout do portal (templates/atas.html). O .docx é montado
no navegador (static/js/atas-docx.js + JSZip) e baixado direto — nada da ata
passa pelo servidor, exceto o preenchimento por IA: o botão "Preencher com IA"
envia a transcrição para POST /atas/ia, que extrai os campos via OpenAI (mesma
chave do editor de fotos).

O layout do DOCUMENTO Word (cores, margens, campos) vive em atas-docx.js e é
mantido em sincronia com o gerador do Claude (gerar_ata_docx.py): mudança lá
deve ser aplicada nos dois.
"""

from flask import Blueprint, jsonify, render_template, request
from flask_login import login_required

from ai_edit import extrair_dados_ata, ia_disponivel
from extensions import limiter
from models import registrar_atividade

bp = Blueprint("atas", __name__)

# Limite de tamanho da transcrição enviada à IA (caracteres).
_MAX_TEXTO = 60_000


@bp.route("/atas")
@login_required
def index():
    registrar_atividade("atas_abriu", "Abriu o Assistente de Atas")
    return render_template("atas.html")


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
