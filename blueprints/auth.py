"""Autenticação e administração de usuários (núcleo da plataforma)."""

from datetime import datetime

from flask import (Blueprint, abort, redirect, render_template, request,
                   session, url_for)
from flask_login import (current_user, login_required, login_user,
                         logout_user)

from config import SENHA_MIN
from extensions import db, limiter
from models import Usuario, senha_fraca
from utils import destino_seguro, remover_arquivos_da_obra

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        senha = request.form.get("senha") or ""
        usuario = Usuario.query.filter_by(email=email).first()
        if usuario and usuario.conferir_senha(senha):
            session.permanent = True
            login_user(usuario)
            destino = destino_seguro(request.args.get("next"))
            return redirect(destino or url_for("main.dashboard"))
        # Mensagem genérica: não revela se o email existe (evita enumeração).
        return render_template("login.html", erro="Email ou senha inválidos.")
    return render_template("login.html")


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))


@bp.route("/conta", methods=["GET", "POST"])
@login_required
def conta():
    if request.method == "POST":
        nome = (request.form.get("nome") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        senha_atual = request.form.get("senha_atual") or ""
        nova_senha = request.form.get("nova_senha") or ""

        # Por segurança, exige a senha atual para qualquer alteração.
        if not current_user.conferir_senha(senha_atual):
            return render_template("conta.html", erro="Senha atual incorreta.")
        if email and email != current_user.email:
            existe = Usuario.query.filter(Usuario.email == email,
                                          Usuario.id != current_user.id).first()
            if existe:
                return render_template("conta.html", erro="Esse email já está em uso.")
            current_user.email = email
        current_user.nome = nome
        if nova_senha:
            if senha_fraca(nova_senha):
                return render_template("conta.html",
                                       erro=f"A nova senha deve ter pelo menos {SENHA_MIN} caracteres.")
            current_user.definir_senha(nova_senha)
        db.session.commit()
        return render_template("conta.html", ok=True)
    return render_template("conta.html")


# ---------------------------------------------------------------------------
# Administração de usuários (somente admin cria/remove contas)
# ---------------------------------------------------------------------------
def _exige_admin():
    if not current_user.is_admin:
        abort(403)


@bp.route("/admin/usuarios")
@login_required
def admin_usuarios():
    _exige_admin()
    usuarios = Usuario.query.order_by(Usuario.id).all()
    return render_template("admin_usuarios.html", usuarios=usuarios)


@bp.route("/admin/usuarios/criar", methods=["POST"])
@login_required
def admin_criar_usuario():
    _exige_admin()
    email = (request.form.get("email") or "").strip().lower()
    nome = (request.form.get("nome") or "").strip()
    senha = request.form.get("senha") or ""
    is_admin = request.form.get("is_admin") == "on"
    if not email or not senha:
        return _admin_msg("Informe email e senha.", erro=True)
    if senha_fraca(senha):
        return _admin_msg(f"A senha deve ter pelo menos {SENHA_MIN} caracteres.", erro=True)
    if Usuario.query.filter_by(email=email).first():
        return _admin_msg("Já existe um usuário com esse email.", erro=True)
    usuario = Usuario(email=email, nome=nome, is_admin=is_admin,
                      criado_em=datetime.now().isoformat())
    usuario.definir_senha(senha)
    db.session.add(usuario)
    db.session.commit()
    return _admin_msg(f"Usuário {email} criado.")


@bp.route("/admin/usuarios/<int:user_id>/senha", methods=["POST"])
@login_required
def admin_redefinir_senha(user_id):
    _exige_admin()
    usuario = db.session.get(Usuario, user_id) or abort(404)
    nova = request.form.get("senha") or ""
    if senha_fraca(nova):
        return _admin_msg(f"A nova senha deve ter pelo menos {SENHA_MIN} caracteres.", erro=True)
    usuario.definir_senha(nova)
    db.session.commit()
    return _admin_msg(f"Senha de {usuario.email} redefinida.")


@bp.route("/admin/usuarios/<int:user_id>/excluir", methods=["POST"])
@login_required
def admin_excluir_usuario(user_id):
    _exige_admin()
    if user_id == current_user.id:
        return _admin_msg("Você não pode excluir a própria conta.", erro=True)
    usuario = db.session.get(Usuario, user_id) or abort(404)
    for obra in usuario.obras:
        remover_arquivos_da_obra(obra)
    db.session.delete(usuario)
    db.session.commit()
    return _admin_msg(f"Usuário {usuario.email} excluído.")


def _admin_msg(msg, erro=False):
    usuarios = Usuario.query.order_by(Usuario.id).all()
    chave = "erro" if erro else "ok"
    return render_template("admin_usuarios.html", usuarios=usuarios, **{chave: msg})
