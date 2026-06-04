"""Núcleo da plataforma: painel inicial (vitrine) e mapa de processos."""

from flask import Blueprint, abort, redirect, render_template, url_for
from flask_login import current_user, login_required

from plataforma import FERRAMENTAS, PROCESSOS, ferramenta_por_slug

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


@bp.route("/mapa-de-processos")
@login_required
def mapa_processos():
    """Diagrama em árvore dos processos da construtora."""
    return render_template("mapa_processos.html", processos=PROCESSOS,
                           ferramentas=FERRAMENTAS)
