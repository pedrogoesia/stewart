"""Autenticação e administração de usuários (núcleo da plataforma)."""

from datetime import datetime

from flask import (Blueprint, abort, redirect, render_template, request,
                   session, url_for)
from flask_login import (current_user, login_required, login_user,
                         logout_user)

from config import SENHA_MIN
from extensions import db, limiter
from models import Usuario, registrar_atividade, senha_fraca
from utils import destino_seguro, remover_arquivos_da_obra

bp = Blueprint("auth", __name__)


def _pagina_inicial():
    """Para onde mandar o usuário após o login: admin → Usuários; demais → ferramenta."""
    if current_user.is_admin:
        return url_for("auth.admin_usuarios")
    return url_for("relatorios.index")


@bp.route("/")
@login_required
def home():
    return redirect(_pagina_inicial())


@bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"])
def login():
    if current_user.is_authenticated:
        return redirect(_pagina_inicial())
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        senha = request.form.get("senha") or ""
        usuario = Usuario.query.filter_by(email=email).first()
        if usuario and usuario.conferir_senha(senha):
            session.permanent = True
            login_user(usuario)
            registrar_atividade("login", "Entrou no sistema")
            destino = destino_seguro(request.args.get("next"))
            return redirect(destino or _pagina_inicial())
        # Mensagem genérica: não revela se o email existe (evita enumeração).
        registrar_atividade("login_falhou", f"Tentativa de login: {email}",
                            email=email)
        return render_template("login.html", erro="Email ou senha inválidos.")
    return render_template("login.html")


@bp.route("/logout")
@login_required
def logout():
    registrar_atividade("logout", "Saiu do sistema")
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
        registrar_atividade("conta_atualizada", "Atualizou os dados da conta")
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


@bp.route("/admin/atividades")
@login_required
def admin_atividades():
    _exige_admin()
    from datetime import datetime as _dt
    from models import Atividade
    registros = (Atividade.query.order_by(Atividade.id.desc()).limit(300).all())
    itens = []
    for a in registros:
        try:
            quando = _dt.fromisoformat(a.criado_em).strftime("%d/%m/%Y %H:%M")
        except (ValueError, TypeError):
            quando = a.criado_em
        itens.append({
            "quando": quando, "email": a.usuario_email or "—",
            "acao": a.acao, "descricao": a.descricao or "", "ip": a.ip or "—",
        })
    return render_template("admin_atividades.html", itens=itens)


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
    registrar_atividade("usuario_criado", f"Criou o usuário {email}")
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
    registrar_atividade("senha_redefinida", f"Redefiniu a senha de {usuario.email}")
    return _admin_msg(f"Senha de {usuario.email} redefinida.")


@bp.route("/admin/usuarios/<int:user_id>/excluir", methods=["POST"])
@login_required
def admin_excluir_usuario(user_id):
    _exige_admin()
    if user_id == current_user.id:
        return _admin_msg("Você não pode excluir a própria conta.", erro=True)
    usuario = db.session.get(Usuario, user_id) or abort(404)
    email_excluido = usuario.email
    for obra in usuario.obras:
        remover_arquivos_da_obra(obra)
    db.session.delete(usuario)
    db.session.commit()
    registrar_atividade("usuario_excluido", f"Excluiu o usuário {email_excluido}")
    return _admin_msg(f"Usuário {email_excluido} excluído.")


def _admin_msg(msg, erro=False):
    usuarios = Usuario.query.order_by(Usuario.id).all()
    chave = "erro" if erro else "ok"
    return render_template("admin_usuarios.html", usuarios=usuarios,
                           **{chave: msg})
