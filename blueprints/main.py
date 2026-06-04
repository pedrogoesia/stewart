"""Núcleo da plataforma: painel inicial, workflows e página da empresa."""

from flask import Blueprint, abort, redirect, render_template, url_for
from flask_login import current_user, login_required

from plataforma import EMPRESA, FERRAMENTAS, PROCESSOS, ferramenta_por_slug

bp = Blueprint("main", __name__)


@bp.route("/")
@login_required
def dashboard():
    """Vitrine das ferramentas da plataforma."""
    return render_template("dashboard.html", ferramentas=FERRAMENTAS)


@bp.route("/ferramenta/<slug>")
@login_required
def ferramenta(slug):
    """Abre a ferramenta (se ativa) ou mostra a página 'em breve'."""
    f = ferramenta_por_slug(slug)
    if f is None:
        abort(404)
    if f["ativo"] and f["endpoint"]:
        return redirect(url_for(f["endpoint"]))
    return render_template("ferramenta_em_breve.html", ferramenta=f)


@bp.route("/workflows")
@login_required
def workflows():
    """Quadro (board) com os fluxos/processos da construtora."""
    return render_template("workflows.html", processos=PROCESSOS,
                           ferramentas=FERRAMENTAS)


@bp.route("/empresa")
@login_required
def empresa():
    """Painel institucional da Stewart Engenharia (somente front por ora)."""
    return render_template("empresa.html", empresa=EMPRESA)

