"""
Stewart Construtora — Sistema de Relatórios Fotográficos de Obras.

Aplicação web (celular + computador) para:
  - login de usuários (cada um vê apenas as próprias obras);
  - cadastrar obras;
  - anexar fotos organizadas por cômodo, com descrição (legenda) em cada foto;
  - gerar o relatório mensal em PowerPoint (.pptx) usando o template oficial;
  - baixar todas as fotos em um .zip com uma pasta por cômodo.

Banco de dados:
  - Desenvolvimento (no seu PC): SQLite, um arquivo em data/stewart.db.
  - Produção (online): PostgreSQL — basta definir a variável DATABASE_URL.
  O mesmo código roda nos dois graças ao SQLAlchemy.
"""

import io
import os
import re
import unicodedata
import uuid
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

from flask import (Flask, abort, jsonify, redirect, render_template, request,
                   send_file, send_from_directory, session, url_for)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import (LoginManager, UserMixin, current_user, login_required,
                         login_user, logout_user)
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from flask_wtf.csrf import CSRFError
from PIL import Image, ImageOps
from sqlalchemy import inspect, text
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash

# Carrega variáveis do arquivo .env (ex.: OPENAI_API_KEY, SECRET_KEY,
# DATABASE_URL), se existir. Procura tanto na pasta do app.py quanto no
# diretório atual, para funcionar mesmo iniciando o servidor de outro lugar.
try:
    from dotenv import load_dotenv
    _aqui = os.path.dirname(os.path.abspath(__file__))
    load_dotenv(os.path.join(_aqui, ".env"))
    load_dotenv()
except Exception:
    pass

from pptx_generator import gerar_relatorio
from ai_edit import editar_imagem, ia_disponivel

# Suporte opcional a fotos HEIC/HEIF (iPhone), se a lib estiver disponível.
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except Exception:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
DB_PATH = os.path.join(DATA_DIR, "stewart.db")
TEMPLATE_PATH = os.path.join(BASE_DIR, "template", "TEMPLATE_STEWART.pptx")

MAX_IMG_SIDE = 2000          # redimensiona fotos para no máx. 2000px (lado maior)
JPEG_QUALITY = 85

MESES = ["JANEIRO", "FEVEREIRO", "MARÇO", "ABRIL", "MAIO", "JUNHO", "JULHO",
         "AGOSTO", "SETEMBRO", "OUTUBRO", "NOVEMBRO", "DEZEMBRO"]

os.makedirs(UPLOAD_DIR, exist_ok=True)


def _database_url():
    """Monta a URL do banco. Usa DATABASE_URL (produção) ou SQLite (local)."""
    url = os.environ.get("DATABASE_URL", "").strip()
    if url:
        # Provedores como Render/Railway entregam "postgres://...";
        # o SQLAlchemy precisa do driver explícito "postgresql+psycopg://".
        if url.startswith("postgres://"):
            url = "postgresql+psycopg://" + url[len("postgres://"):]
        elif url.startswith("postgresql://"):
            url = "postgresql+psycopg://" + url[len("postgresql://"):]
        return url
    return "sqlite:///" + Path(DB_PATH).as_posix()


# Estamos em produção? (quando há um banco externo configurado ou FLASK_ENV).
# Em produção, ativamos cookies "Secure" (só HTTPS), HSTS e exigimos SECRET_KEY.
IS_PRODUCTION = (bool(os.environ.get("DATABASE_URL", "").strip())
                 or os.environ.get("FLASK_ENV") == "production")

SENHA_MIN = 8  # tamanho mínimo de senha

app = Flask(__name__)

# Confia nos cabeçalhos do proxy reverso (Render/Railway/Nginx) para detectar
# HTTPS corretamente — necessário para os cookies "Secure" funcionarem.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

app.config["MAX_CONTENT_LENGTH"] = 64 * 1024 * 1024  # 64 MB por upload
app.config["SQLALCHEMY_DATABASE_URI"] = _database_url()
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True}

# --- Cookie de sessão endurecido ---
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,        # JavaScript não lê o cookie (anti-XSS)
    SESSION_COOKIE_SAMESITE="Lax",       # não vai em requisições de outros sites
    SESSION_COOKIE_SECURE=IS_PRODUCTION,  # só trafega em HTTPS (em produção)
    PERMANENT_SESSION_LIFETIME=timedelta(days=7),
    WTF_CSRF_TIME_LIMIT=None,            # token de CSRF vale enquanto durar a sessão
)

# Chave que assina o cookie de sessão. EM PRODUÇÃO é obrigatória.
_secret = os.environ.get("SECRET_KEY", "").strip()
if not _secret:
    if IS_PRODUCTION:
        raise RuntimeError(
            "SECRET_KEY não definida. Em produção, defina a variável de "
            "ambiente SECRET_KEY com um valor longo e aleatório.")
    _secret = "dev-inseguro-troque-em-producao"
    print("[AVISO] SECRET_KEY não definida — usando chave de desenvolvimento. "
          "Defina SECRET_KEY no .env antes de publicar.")
app.config["SECRET_KEY"] = _secret

db = SQLAlchemy(app)

# Proteção contra CSRF (Cross-Site Request Forgery) em todos os POST/PUT/DELETE.
csrf = CSRFProtect(app)

# Limite de requisições (anti força-bruta / abuso). Em produção com vários
# servidores, aponte RATELIMIT_STORAGE_URI para um Redis.
limiter = Limiter(
    get_remote_address, app=app,
    storage_uri=os.environ.get("RATELIMIT_STORAGE_URI", "memory://"),
)

login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Faça login para acessar esta página."


@app.after_request
def aplicar_cabecalhos_seguranca(resp):
    """Cabeçalhos HTTP que reduzem a superfície de ataque do navegador."""
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"            # impede clickjacking
    resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    resp.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=(self)"
    # Política de conteúdo: só carrega recursos do próprio site. 'unsafe-inline'
    # é necessário porque a interface usa scripts/estilos embutidos (onclick etc.).
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "img-src 'self' data:; "
        "style-src 'self' 'unsafe-inline'; "
        "script-src 'self' 'unsafe-inline'; "
        "object-src 'none'; base-uri 'self'; frame-ancestors 'none'; "
        "form-action 'self'")
    if IS_PRODUCTION:
        resp.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains")
    return resp


@app.errorhandler(CSRFError)
def tratar_csrf(e):
    return jsonify({"erro": "Sessão expirada ou inválida. Recarregue a página "
                    "e tente novamente."}), 400


def _senha_fraca(senha):
    return len(senha or "") < SENHA_MIN


# ---------------------------------------------------------------------------
# Modelos (tabelas do banco)
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


@login_manager.user_loader
def carregar_usuario(user_id):
    return db.session.get(Usuario, int(user_id))


# ---------------------------------------------------------------------------
# Inicialização do banco (cria tabelas, migra dados antigos e cria o admin)
# ---------------------------------------------------------------------------
def init_db():
    with app.app_context():
        db.create_all()
        _migrar_obras_antigas()
        _criar_admin_inicial()


def _migrar_obras_antigas():
    """Bancos antigos (antes do login) têm 'obras' sem a coluna usuario_id.
    Adiciona a coluna para não perder os dados já cadastrados."""
    insp = inspect(db.engine)
    if not insp.has_table("obras"):
        return
    colunas = [c["name"] for c in insp.get_columns("obras")]
    if "usuario_id" not in colunas:
        db.session.execute(text("ALTER TABLE obras ADD COLUMN usuario_id INTEGER"))
        db.session.commit()
    # Normaliza caminhos antigos salvos com "\" (Windows) para "/".
    db.session.execute(text(
        r"UPDATE fotos SET arquivo = REPLACE(arquivo, '\', '/') "
        r"WHERE arquivo LIKE '%\%'"))
    db.session.commit()


def _criar_admin_inicial():
    """Cria o primeiro usuário administrador se ainda não houver nenhum usuário,
    e adota as obras 'órfãs' (de antes do login) para esse admin."""
    if Usuario.query.count() == 0:
        email = os.environ.get("ADMIN_EMAIL", "admin@stewart.local").strip().lower()
        senha = os.environ.get("ADMIN_SENHA", "admin")
        admin = Usuario(email=email, nome="Administrador", is_admin=True,
                        criado_em=datetime.now().isoformat())
        admin.definir_senha(senha)
        db.session.add(admin)
        db.session.commit()
        print("[INFO] Usuário administrador criado.")
        print(f"       Email: {email}")
        if not os.environ.get("ADMIN_SENHA"):
            print("       Senha: admin   <-- TROQUE em 'Minha conta' após entrar!")

    admin = Usuario.query.filter_by(is_admin=True).order_by(Usuario.id).first()
    if admin:
        orfas = Obra.query.filter(Obra.usuario_id.is_(None)).all()
        for o in orfas:
            o.usuario_id = admin.id
        if orfas:
            db.session.commit()


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def slugify(text, default="item"):
    text = unicodedata.normalize("NFKD", text or "")
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text).strip()
    text = re.sub(r"[\s_-]+", "_", text)
    return text or default


def periodo_label(mes, ano):
    try:
        return f"{MESES[int(mes) - 1]} {int(ano)}"
    except (ValueError, IndexError, TypeError):
        agora = datetime.now()
        return f"{MESES[agora.month - 1]} {agora.year}"


def foto_abs_path(arquivo):
    # O caminho é guardado sempre com "/"; convertemos para o separador do SO.
    return os.path.join(UPLOAD_DIR, *arquivo.split("/"))


def processar_imagem(file_storage, dest_path):
    """Corrige orientação (EXIF), redimensiona e salva como JPEG."""
    img = Image.open(file_storage.stream)
    img = ImageOps.exif_transpose(img)
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    elif img.mode == "L":
        img = img.convert("RGB")
    img.thumbnail((MAX_IMG_SIDE, MAX_IMG_SIDE), Image.LANCZOS)
    img.save(dest_path, "JPEG", quality=JPEG_QUALITY, optimize=True)


# ---- Busca com verificação de dono (só o dono — ou admin — acessa) --------
def obra_do_usuario(obra_id):
    obra = db.session.get(Obra, obra_id)
    if obra is None or not _pode_acessar(obra.usuario_id):
        abort(404)
    return obra


def comodo_do_usuario(comodo_id):
    comodo = db.session.get(Comodo, comodo_id)
    if comodo is None or not _pode_acessar(comodo.obra.usuario_id):
        abort(404)
    return comodo


def foto_do_usuario(foto_id):
    foto = db.session.get(Foto, foto_id)
    if foto is None or not _pode_acessar(foto.comodo.obra.usuario_id):
        abort(404)
    return foto


def _pode_acessar(usuario_id):
    return current_user.is_authenticated and (
        usuario_id == current_user.id or current_user.is_admin)


def comodos_com_fotos(obra):
    grupos = []
    for c in sorted(obra.comodos, key=lambda c: (c.ordem, c.id)):
        fotos = sorted(c.fotos, key=lambda f: (f.ordem, f.id))
        grupos.append({"comodo": c, "fotos": fotos})
    return grupos


def _remover_arquivos_da_obra(obra):
    for c in obra.comodos:
        for f in c.fotos:
            try:
                os.remove(foto_abs_path(f.arquivo))
            except OSError:
                pass


def _destino_seguro(target):
    """Evita redirecionamento aberto: só aceita caminhos internos."""
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return None


# ---------------------------------------------------------------------------
# Autenticação
# ---------------------------------------------------------------------------
@app.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        senha = request.form.get("senha") or ""
        usuario = Usuario.query.filter_by(email=email).first()
        if usuario and usuario.conferir_senha(senha):
            session.permanent = True
            login_user(usuario)
            destino = _destino_seguro(request.args.get("next"))
            return redirect(destino or url_for("index"))
        # Mensagem genérica: não revela se o email existe (evita enumeração).
        return render_template("login.html", erro="Email ou senha inválidos.")
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


@app.route("/conta", methods=["GET", "POST"])
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
            if _senha_fraca(nova_senha):
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


@app.route("/admin/usuarios")
@login_required
def admin_usuarios():
    _exige_admin()
    usuarios = Usuario.query.order_by(Usuario.id).all()
    return render_template("admin_usuarios.html", usuarios=usuarios)


@app.route("/admin/usuarios/criar", methods=["POST"])
@login_required
def admin_criar_usuario():
    _exige_admin()
    email = (request.form.get("email") or "").strip().lower()
    nome = (request.form.get("nome") or "").strip()
    senha = request.form.get("senha") or ""
    is_admin = request.form.get("is_admin") == "on"
    if not email or not senha:
        return _admin_msg("Informe email e senha.", erro=True)
    if _senha_fraca(senha):
        return _admin_msg(f"A senha deve ter pelo menos {SENHA_MIN} caracteres.", erro=True)
    if Usuario.query.filter_by(email=email).first():
        return _admin_msg("Já existe um usuário com esse email.", erro=True)
    usuario = Usuario(email=email, nome=nome, is_admin=is_admin,
                      criado_em=datetime.now().isoformat())
    usuario.definir_senha(senha)
    db.session.add(usuario)
    db.session.commit()
    return _admin_msg(f"Usuário {email} criado.")


@app.route("/admin/usuarios/<int:user_id>/senha", methods=["POST"])
@login_required
def admin_redefinir_senha(user_id):
    _exige_admin()
    usuario = db.session.get(Usuario, user_id) or abort(404)
    nova = request.form.get("senha") or ""
    if _senha_fraca(nova):
        return _admin_msg(f"A nova senha deve ter pelo menos {SENHA_MIN} caracteres.", erro=True)
    usuario.definir_senha(nova)
    db.session.commit()
    return _admin_msg(f"Senha de {usuario.email} redefinida.")


@app.route("/admin/usuarios/<int:user_id>/excluir", methods=["POST"])
@login_required
def admin_excluir_usuario(user_id):
    _exige_admin()
    if user_id == current_user.id:
        return _admin_msg("Você não pode excluir a própria conta.", erro=True)
    usuario = db.session.get(Usuario, user_id) or abort(404)
    for obra in usuario.obras:
        _remover_arquivos_da_obra(obra)
    db.session.delete(usuario)
    db.session.commit()
    return _admin_msg(f"Usuário {usuario.email} excluído.")


def _admin_msg(msg, erro=False):
    usuarios = Usuario.query.order_by(Usuario.id).all()
    chave = "erro" if erro else "ok"
    return render_template("admin_usuarios.html", usuarios=usuarios, **{chave: msg})


# ---------------------------------------------------------------------------
# Páginas
# ---------------------------------------------------------------------------
@app.route("/")
@login_required
def index():
    obras = (Obra.query.filter_by(usuario_id=current_user.id)
             .order_by(Obra.id.desc()).all())
    dados = []
    for o in obras:
        dados.append({
            "id": o.id, "nome": o.nome, "endereco": o.endereco,
            "total_comodos": len(o.comodos),
            "total_fotos": sum(len(c.fotos) for c in o.comodos),
        })
    return render_template("index.html", obras=dados)


@app.route("/obra/<int:obra_id>")
@login_required
def obra_detail(obra_id):
    obra = obra_do_usuario(obra_id)
    grupos = comodos_com_fotos(obra)
    agora = datetime.now()
    return render_template("obra.html", obra=obra, grupos=grupos,
                           meses=MESES, mes_atual=agora.month,
                           ano_atual=agora.year, ia_ativa=ia_disponivel())


# ---------------------------------------------------------------------------
# API — Obras
# ---------------------------------------------------------------------------
@app.route("/obras", methods=["POST"])
@login_required
def criar_obra():
    nome = (request.form.get("nome") or "").strip()
    endereco = (request.form.get("endereco") or "").strip()
    if not nome:
        return redirect(url_for("index"))
    obra = Obra(usuario_id=current_user.id, nome=nome, endereco=endereco,
                criado_em=datetime.now().isoformat())
    db.session.add(obra)
    db.session.commit()
    return redirect(url_for("index"))


@app.route("/obra/<int:obra_id>/editar", methods=["POST"])
@login_required
def editar_obra(obra_id):
    obra = obra_do_usuario(obra_id)
    obra.nome = (request.form.get("nome") or "").strip()
    obra.endereco = (request.form.get("endereco") or "").strip()
    db.session.commit()
    return redirect(url_for("obra_detail", obra_id=obra_id))


@app.route("/obra/<int:obra_id>/excluir", methods=["POST"])
@login_required
def excluir_obra(obra_id):
    obra = obra_do_usuario(obra_id)
    _remover_arquivos_da_obra(obra)
    db.session.delete(obra)
    db.session.commit()
    return redirect(url_for("index"))


# ---------------------------------------------------------------------------
# API — Cômodos
# ---------------------------------------------------------------------------
@app.route("/obra/<int:obra_id>/comodos", methods=["POST"])
@login_required
def criar_comodo(obra_id):
    obra = obra_do_usuario(obra_id)
    nome = (request.form.get("nome") or "").strip()
    if not nome:
        return jsonify({"erro": "Nome do cômodo é obrigatório"}), 400
    ordem = max((c.ordem for c in obra.comodos), default=0) + 1
    comodo = Comodo(obra_id=obra.id, nome=nome, ordem=ordem)
    db.session.add(comodo)
    db.session.commit()
    return jsonify({"id": comodo.id, "nome": nome})


@app.route("/comodo/<int:comodo_id>/renomear", methods=["POST"])
@login_required
def renomear_comodo(comodo_id):
    comodo = comodo_do_usuario(comodo_id)
    nome = (request.form.get("nome") or "").strip()
    if not nome:
        return jsonify({"erro": "Nome inválido"}), 400
    comodo.nome = nome
    db.session.commit()
    return jsonify({"ok": True, "nome": nome})


@app.route("/comodo/<int:comodo_id>/excluir", methods=["POST"])
@login_required
def excluir_comodo(comodo_id):
    comodo = comodo_do_usuario(comodo_id)
    for f in comodo.fotos:
        try:
            os.remove(foto_abs_path(f.arquivo))
        except OSError:
            pass
    db.session.delete(comodo)
    db.session.commit()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# API — Fotos
# ---------------------------------------------------------------------------
@app.route("/comodo/<int:comodo_id>/fotos", methods=["POST"])
@login_required
def upload_foto(comodo_id):
    comodo = comodo_do_usuario(comodo_id)

    file = request.files.get("foto")
    if file is None or file.filename == "":
        return jsonify({"erro": "Nenhum arquivo enviado"}), 400

    descricao = (request.form.get("descricao") or "").strip()
    # Já inicia a legenda com o nome do cômodo, no modelo "Sala - ".
    if not descricao:
        descricao = f"{comodo.nome} - "
    # Caminho relativo guardado SEMPRE com "/" (compatível com URL e Windows).
    rel_dir = f"{comodo.obra_id}/{comodo_id}"
    abs_dir = os.path.join(UPLOAD_DIR, str(comodo.obra_id), str(comodo_id))
    os.makedirs(abs_dir, exist_ok=True)
    nome_arquivo = f"{uuid.uuid4().hex}.jpg"
    rel_path = f"{rel_dir}/{nome_arquivo}"

    try:
        processar_imagem(file, os.path.join(abs_dir, nome_arquivo))
    except Exception as e:  # noqa: BLE001
        return jsonify({"erro": f"Falha ao processar imagem: {e}"}), 400

    ordem = max((f.ordem for f in comodo.fotos), default=0) + 1
    foto = Foto(comodo_id=comodo_id, arquivo=rel_path, descricao=descricao,
                ordem=ordem, criado_em=datetime.now().isoformat())
    db.session.add(foto)
    db.session.commit()
    return jsonify({
        "id": foto.id,
        "url": url_for("servir_foto", filename=rel_path),
        "descricao": descricao,
    })


@app.route("/comodo/<int:comodo_id>/reordenar", methods=["POST"])
@login_required
def reordenar_fotos(comodo_id):
    """Recebe os ids das fotos na nova ordem e atualiza o campo 'ordem'.

    Essa ordem é a que vale no relatório PowerPoint e no .zip.
    """
    comodo = comodo_do_usuario(comodo_id)
    ids = request.form.get("ordem", "")
    id_list = [int(x) for x in ids.split(",") if x.strip().isdigit()]
    fotos = {f.id: f for f in comodo.fotos}
    for posicao, foto_id in enumerate(id_list):
        if foto_id in fotos:
            fotos[foto_id].ordem = posicao
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/foto/<int:foto_id>/descricao", methods=["POST"])
@login_required
def atualizar_descricao(foto_id):
    foto = foto_do_usuario(foto_id)
    foto.descricao = (request.form.get("descricao") or "").strip()
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/foto/<int:foto_id>/excluir", methods=["POST"])
@login_required
def excluir_foto(foto_id):
    foto = foto_do_usuario(foto_id)
    try:
        os.remove(foto_abs_path(foto.arquivo))
    except OSError:
        pass
    db.session.delete(foto)
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/uploads/<path:filename>")
@login_required
def servir_foto(filename):
    # Garante que só o dono (ou admin) veja a imagem: o 1º trecho do caminho
    # é o id da obra (ex.: "12/34/uuid.jpg").
    try:
        obra_id = int(filename.split("/")[0])
    except (ValueError, IndexError):
        abort(404)
    obra_do_usuario(obra_id)   # aborta 404 se não for o dono
    return send_from_directory(UPLOAD_DIR, filename)


# ---------------------------------------------------------------------------
# Edição de fotos por IA (OpenAI)
# ---------------------------------------------------------------------------
def _preview_rel(arquivo):
    """Caminho relativo da prévia da edição (ainda não aplicada)."""
    return arquivo + ".preview.jpg"


@app.route("/foto/<int:foto_id>/editar-ia", methods=["POST"])
@login_required
@limiter.limit("20 per hour")
def editar_foto_ia(foto_id):
    if not ia_disponivel():
        return jsonify({"erro": "A edição por IA não está configurada. "
                        "Crie um arquivo .env com OPENAI_API_KEY."}), 400
    foto = foto_do_usuario(foto_id)
    prompt = (request.form.get("prompt") or "").strip()
    if not prompt:
        return jsonify({"erro": "Descreva a alteração desejada."}), 400

    origem = foto_abs_path(foto.arquivo)
    if not os.path.exists(origem):
        return jsonify({"erro": "Arquivo da foto não encontrado."}), 404

    try:
        novos_bytes = editar_imagem(origem, prompt)
    except Exception as e:  # noqa: BLE001
        return jsonify({"erro": str(e)}), 502

    preview_rel = _preview_rel(foto.arquivo)
    with open(foto_abs_path(preview_rel), "wb") as fh:
        fh.write(novos_bytes)

    return jsonify({
        "preview_url": url_for("servir_foto", filename=preview_rel),
        "original_url": url_for("servir_foto", filename=foto.arquivo),
    })


@app.route("/foto/<int:foto_id>/aplicar-edicao", methods=["POST"])
@login_required
def aplicar_edicao_ia(foto_id):
    foto = foto_do_usuario(foto_id)
    preview_abs = foto_abs_path(_preview_rel(foto.arquivo))
    if not os.path.exists(preview_abs):
        return jsonify({"erro": "Nenhuma prévia para aplicar."}), 400
    # Substitui o arquivo original pela versão editada (mantém o mesmo nome).
    os.replace(preview_abs, foto_abs_path(foto.arquivo))
    return jsonify({
        "ok": True,
        "url": url_for("servir_foto", filename=foto.arquivo),
    })


@app.route("/foto/<int:foto_id>/descartar-edicao", methods=["POST"])
@login_required
def descartar_edicao_ia(foto_id):
    foto = foto_do_usuario(foto_id)
    preview_abs = foto_abs_path(_preview_rel(foto.arquivo))
    try:
        os.remove(preview_abs)
    except OSError:
        pass
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Geração de relatório (.pptx) e download das fotos (.zip)
# ---------------------------------------------------------------------------
@app.route("/obra/<int:obra_id>/relatorio.pptx")
@login_required
def baixar_relatorio(obra_id):
    obra = obra_do_usuario(obra_id)
    label = periodo_label(request.args.get("mes"), request.args.get("ano"))

    comodos = []
    for grupo in comodos_com_fotos(obra):
        fotos = [{"path": foto_abs_path(f.arquivo),
                  "descricao": f.descricao} for f in grupo["fotos"]]
        if fotos:
            comodos.append({"nome": grupo["comodo"].nome, "fotos": fotos})

    out = io.BytesIO()
    tmp_path = os.path.join(DATA_DIR, f"_relatorio_{uuid.uuid4().hex}.pptx")
    gerar_relatorio(TEMPLATE_PATH, tmp_path,
                    {"nome": obra.nome, "endereco": obra.endereco},
                    label, comodos)
    with open(tmp_path, "rb") as fh:
        out.write(fh.read())
    os.remove(tmp_path)
    out.seek(0)

    nome_arq = f"Relatorio_{slugify(obra.nome)}_{slugify(label)}.pptx"
    return send_file(
        out, as_attachment=True, download_name=nome_arq,
        mimetype=("application/vnd.openxmlformats-officedocument"
                  ".presentationml.presentation"))


@app.route("/obra/<int:obra_id>/fotos.zip")
@login_required
def baixar_fotos_zip(obra_id):
    obra = obra_do_usuario(obra_id)
    buffer = io.BytesIO()
    obra_slug = slugify(obra.nome, "obra")
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for grupo in comodos_com_fotos(obra):
            comodo_slug = slugify(grupo["comodo"].nome, "comodo")
            for i, f in enumerate(grupo["fotos"], start=1):
                src = foto_abs_path(f.arquivo)
                if not os.path.exists(src):
                    continue
                desc = slugify(f.descricao, "")[:40]
                base = f"{i:02d}_{desc}" if desc else f"{i:02d}"
                arcname = f"{obra_slug}/{comodo_slug}/{base}.jpg"
                zf.write(src, arcname)
    buffer.seek(0)
    return send_file(buffer, as_attachment=True,
                     download_name=f"Fotos_{obra_slug}.zip",
                     mimetype="application/zip")


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
