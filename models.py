"""Modelos do banco (tabelas) e regras de acesso por usuário.

Núcleo: Usuário (login/contas) e Atividade (auditoria). A ferramenta de
Relatórios de Obras adiciona Obra → Cômodo → Foto.
"""

from datetime import datetime

from flask import abort, has_request_context, request
from flask_login import UserMixin, current_user
from werkzeug.security import check_password_hash, generate_password_hash

from config import SENHA_MIN
from extensions import db, login_manager


# ---------------------------------------------------------------------------
# Usuários (núcleo da plataforma)
# ---------------------------------------------------------------------------
class Usuario(UserMixin, db.Model):
    __tablename__ = "usuarios"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    nome = db.Column(db.String(255), default="")
    senha_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    criado_em = db.Column(db.String(40), nullable=False)

    obras = db.relationship("Obra", backref="usuario",
                            cascade="all, delete-orphan")

    def definir_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def conferir_senha(self, senha):
        return check_password_hash(self.senha_hash, senha or "")

    def pode_ver_ferramenta(self, slug):
        """Toda pessoa logada pode usar as ferramentas disponíveis."""
        return True


# ---------------------------------------------------------------------------
# Ferramenta: Relatórios de Obras
# ---------------------------------------------------------------------------
class Obra(db.Model):
    __tablename__ = "obras"
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"),
                           nullable=False, index=True)
    nome = db.Column(db.String(255), nullable=False)
    endereco = db.Column(db.String(255), default="")
    criado_em = db.Column(db.String(40), nullable=False)

    comodos = db.relationship("Comodo", backref="obra",
                              cascade="all, delete-orphan")


class Comodo(db.Model):
    __tablename__ = "comodos"
    id = db.Column(db.Integer, primary_key=True)
    obra_id = db.Column(db.Integer, db.ForeignKey("obras.id"),
                        nullable=False, index=True)
    nome = db.Column(db.String(255), nullable=False)
    ordem = db.Column(db.Integer, nullable=False, default=0)

    fotos = db.relationship("Foto", backref="comodo",
                            cascade="all, delete-orphan")


class Foto(db.Model):
    __tablename__ = "fotos"
    id = db.Column(db.Integer, primary_key=True)
    comodo_id = db.Column(db.Integer, db.ForeignKey("comodos.id"),
                          nullable=False, index=True)
    arquivo = db.Column(db.String(500), nullable=False)
    descricao = db.Column(db.Text, default="")
    ordem = db.Column(db.Integer, nullable=False, default=0)
    criado_em = db.Column(db.String(40), nullable=False)


# ---------------------------------------------------------------------------
# Auditoria: quem fez o quê e quando
# ---------------------------------------------------------------------------
class Atividade(db.Model):
    """Registro de auditoria: quem fez o quê e quando (histórico de ações)."""
    __tablename__ = "atividades"
    id = db.Column(db.Integer, primary_key=True)
    # Guardamos o id E o e-mail (desnormalizado) para o histórico sobreviver
    # mesmo se o usuário for excluído depois.
    usuario_id = db.Column(db.Integer, index=True)
    usuario_email = db.Column(db.String(255))
    acao = db.Column(db.String(60), nullable=False, index=True)
    descricao = db.Column(db.String(500), default="")
    obra_id = db.Column(db.Integer, index=True)
    ip = db.Column(db.String(60))
    criado_em = db.Column(db.String(40), nullable=False, index=True)


def registrar_atividade(acao, descricao="", obra_id=None, email=None):
    """Grava uma linha no histórico de atividades. Nunca quebra a ação
    principal: se algo falhar aqui, apenas ignora."""
    try:
        autenticado = current_user.is_authenticated
        ip = None
        if has_request_context():
            ip = request.headers.get("X-Forwarded-For", request.remote_addr) or ""
            ip = ip.split(",")[0].strip() or None
        log = Atividade(
            usuario_id=current_user.id if autenticado else None,
            usuario_email=email or (current_user.email if autenticado else None),
            acao=acao, descricao=descricao, obra_id=obra_id, ip=ip,
            criado_em=datetime.now().isoformat(),
        )
        db.session.add(log)
        db.session.commit()
    except Exception:
        db.session.rollback()


@login_manager.user_loader
def carregar_usuario(user_id):
    try:
        return db.session.get(Usuario, int(user_id))
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Regras de acesso: só o dono (ou um admin) acessa cada recurso
# ---------------------------------------------------------------------------
def pode_acessar(usuario_id):
    return current_user.is_authenticated and (
        usuario_id == current_user.id or current_user.is_admin)


def obra_do_usuario(obra_id):
    obra = db.session.get(Obra, obra_id)
    if obra is None or not pode_acessar(obra.usuario_id):
        abort(404)
    return obra


def comodo_do_usuario(comodo_id):
    comodo = db.session.get(Comodo, comodo_id)
    if comodo is None or not pode_acessar(comodo.obra.usuario_id):
        abort(404)
    return comodo


def foto_do_usuario(foto_id):
    foto = db.session.get(Foto, foto_id)
    if foto is None or not pode_acessar(foto.comodo.obra.usuario_id):
        abort(404)
    return foto


def senha_fraca(senha):
    return len(senha or "") < SENHA_MIN
