"""Ferramenta: Assistente de Atas de Reunião.

Serve o gerador de atas (HTML autocontido, roda 100% no navegador e monta o
.docx com JSZip). O arquivo vive em tools/assistente_atas.html e é servido
atrás do login — por isso NÃO fica em static/ (que é público). O JSZip é
servido localmente (static/js), então funciona offline e respeita a CSP do
portal (script-src 'self').

Mantido em sincronia com o gerador do Claude (gerar_ata_docx.py): mudança de
layout (cores, margens, campos) deve ser aplicada nos dois.
"""

import os

from flask import Blueprint, Response
from flask_login import login_required

from models import registrar_atividade

bp = Blueprint("atas", __name__)

_TOOL_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "tools", "assistente_atas.html")


@bp.route("/atas")
@login_required
def index():
    registrar_atividade("atas_abriu", "Abriu o Assistente de Atas")
    with open(_TOOL_PATH, encoding="utf-8") as f:
        html = f.read()
    # A ferramenta é client-side (sem POST ao servidor); serve o HTML direto.
    return Response(html, mimetype="text/html")
