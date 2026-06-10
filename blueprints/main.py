"""Núcleo da plataforma: painel inicial, workflows e página da empresa."""

from flask import Blueprint, abort, redirect, render_template, url_for
from flask_login import current_user, login_required

from plataforma import EMPRESA, FERRAMENTAS, WORKFLOWS, ferramenta_por_slug

bp = Blueprint("main", __name__)


@bp.route("/")
@login_required
def dashboard():
    """Vitrine das ferramentas da plataforma (só as liberadas para o usuário)."""
    visiveis = [f for f in FERRAMENTAS
                if current_user.pode_ver_ferramenta(f["slug"])]
    return render_template("dashboard.html", ferramentas=visiveis)


@bp.route("/ferramenta/<slug>")
@login_required
def ferramenta(slug):
    """Abre a ferramenta (se ativa) ou mostra a página 'em breve'."""
    f = ferramenta_por_slug(slug)
    if f is None:
        abort(404)
    if not current_user.pode_ver_ferramenta(slug):
        abort(403)
    if f["ativo"] and f["endpoint"]:
        return redirect(url_for(f["endpoint"]))
    return render_template("ferramenta_em_breve.html", ferramenta=f)


@bp.route("/workflows")
@login_required
def workflows():
    """Fluxos operacional e financeiro da construtora, com o status de cada
    etapa (manual → em validação → automação)."""
    flows = []
    for wf in WORKFLOWS:
        etapas = []
        for e in wf["etapas"]:
            ferr = ferramenta_por_slug(e["ferramenta"]) if e.get("ferramenta") else None
            etapas.append({**e, "ferr": ferr})
        flows.append({**wf, "etapas": etapas})
    return render_template("workflows.html", flows=flows)


@bp.route("/empresa")
@login_required
def empresa():
    """Painel institucional da Stewart Engenharia (somente front por ora)."""
    return render_template("empresa.html", empresa=EMPRESA)

