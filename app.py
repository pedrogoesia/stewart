"""Stewart — Plataforma de ferramentas para construtora.

Ponto de entrada da aplicação. Monta o app, liga as extensões (banco, login,
CSRF, rate limit), registra os blueprints (cada ferramenta é um módulo) e
aplica a segurança. As ferramentas vivem em blueprints/; o catálogo está em
plataforma.py.

Banco: SQLite no PC (desenvolvimento) e PostgreSQL em produção (DATABASE_URL).
"""

import os
from datetime import datetime, timedelta

from flask import (Flask, jsonify, redirect, render_template, request,
                   url_for)
from flask_login import current_user
from flask_wtf.csrf import CSRFError
from werkzeug.middleware.proxy_fix import ProxyFix

from config import (IS_PRODUCTION, SENHA_MIN, database_url)
from extensions import csrf, db, limiter, login_manager
from utils import destino_seguro

# Suporte opcional a fotos HEIC/HEIF (iPhone), se a lib estiver disponível.
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except Exception:
    pass


def create_app():
    app = Flask(__name__)

    # Confia nos cabeçalhos do proxy reverso (Render/Railway/Nginx) para
    # detectar HTTPS — necessário para os cookies "Secure".
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    app.config["MAX_CONTENT_LENGTH"] = 64 * 1024 * 1024  # 64 MB por upload
    # Cache longo para arquivos estáticos (CSS/JS/imagens). As URLs de CSS/JS
    # levam ?v=<mtime> (ver context processor 'asset'), então atualizações
    # aparecem na hora, mas o navegador não rebaixa tudo a cada navegação.
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 31536000  # 1 ano
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url()
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True}
    app.config["RATELIMIT_STORAGE_URI"] = os.environ.get(
        "RATELIMIT_STORAGE_URI", "memory://")
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,        # JS não lê o cookie (anti-XSS)
        SESSION_COOKIE_SAMESITE="Lax",       # não vai a outros sites
        SESSION_COOKIE_SECURE=IS_PRODUCTION,  # só HTTPS em produção
        PERMANENT_SESSION_LIFETIME=timedelta(days=7),
        # Cookie "lembrar de mim" (Flask-Login): reloga sozinho por 30 dias.
        REMEMBER_COOKIE_DURATION=timedelta(days=30),
        REMEMBER_COOKIE_HTTPONLY=True,
        REMEMBER_COOKIE_SECURE=IS_PRODUCTION,
        REMEMBER_COOKIE_SAMESITE="Lax",
        WTF_CSRF_TIME_LIMIT=None,            # token de CSRF dura a sessão
    )

    # Chave que assina o cookie de sessão. EM PRODUÇÃO é obrigatória.
    secret = os.environ.get("SECRET_KEY", "").strip()
    if not secret:
        if IS_PRODUCTION:
            raise RuntimeError(
                "SECRET_KEY não definida. Em produção, defina a variável de "
                "ambiente SECRET_KEY com um valor longo e aleatório.")
        secret = "dev-inseguro-troque-em-producao"
        print("[AVISO] SECRET_KEY não definida — usando chave de "
              "desenvolvimento. Defina SECRET_KEY no .env antes de publicar.")
    app.config["SECRET_KEY"] = secret

    # Liga as extensões a este app.
    db.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Faça login para acessar esta página."

    # Garante que os modelos e o user_loader sejam registrados.
    import models  # noqa: F401

    # Registra os módulos: núcleo (auth/admin) + ferramentas.
    from blueprints.auth import bp as auth_bp
    from blueprints.relatorios import bp as relatorios_bp
    from blueprints.atas import bp as atas_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(relatorios_bp)
    app.register_blueprint(atas_bp)

    @app.context_processor
    def injetar_assets():
        # URL de estático com "?v=<mtime>" para cache-busting automático.
        def asset(filename):
            try:
                mtime = int(os.path.getmtime(
                    os.path.join(app.static_folder, filename)))
            except OSError:
                mtime = 0
            return url_for("static", filename=filename, v=mtime)
        return {"asset": asset}

    _registrar_seguranca(app)
    return app


def _registrar_seguranca(app):
    @app.after_request
    def aplicar_cabecalhos_seguranca(resp):
        """Cabeçalhos HTTP que reduzem a superfície de ataque do navegador."""
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"            # anti-clickjacking
        resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        resp.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=(self)")
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
        # Não deixa o navegador cachear PÁGINAS (CSS/JS seguem cacheáveis):
        # evita reusar uma página antiga com token CSRF vencido.
        if resp.mimetype == "text/html":
            resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.errorhandler(CSRFError)
    def tratar_csrf(e):
        # Requisições via fetch (JS) mandam o header X-CSRFToken → JSON.
        if request.headers.get("X-CSRFToken") or request.is_json:
            return jsonify({"erro": "Sessão expirada. Recarregue a página e "
                            "tente novamente."}), 400
        if not current_user.is_authenticated:
            return render_template(
                "login.html",
                erro="Sua sessão expirou. Tente entrar de novo."), 400
        destino = destino_seguro(request.referrer)
        return redirect(destino or url_for("auth.home"))


# ---------------------------------------------------------------------------
# Inicialização do banco (cria tabelas, migra dados antigos e cria o admin)
# ---------------------------------------------------------------------------
def init_db():
    from models import Usuario
    with app.app_context():
        db.create_all()
        _criar_admin_inicial(Usuario)
        _resetar_admin_se_pedido(Usuario)


def _resetar_admin_se_pedido(Usuario):
    """Recupera o acesso do admin quando a senha foi esquecida.

    Se a variável de ambiente ADMIN_RESET=1, redefine a senha do admin
    (email = ADMIN_EMAIL) para o valor de ADMIN_SENHA no próximo deploy —
    trocar só ADMIN_SENHA não basta, porque o admin já existe no banco.
    Depois de recuperar o acesso, REMOVA a variável ADMIN_RESET no painel
    (senão a senha volta a esse valor a cada deploy)."""
    if os.environ.get("ADMIN_RESET", "").strip() != "1":
        return
    email = os.environ.get("ADMIN_EMAIL", "admin@stewart.local").strip().lower()
    senha = os.environ.get("ADMIN_SENHA", "").strip()
    if len(senha) < SENHA_MIN:
        print(f"[ADMIN_RESET] Ignorado: defina ADMIN_SENHA com pelo menos "
              f"{SENHA_MIN} caracteres.")
        return
    admin = Usuario.query.filter_by(email=email).first()
    if admin is None:
        admin = Usuario(email=email, nome="Administrador", is_admin=True,
                        criado_em=datetime.now().isoformat())
        db.session.add(admin)
    admin.is_admin = True
    admin.definir_senha(senha)
    db.session.commit()
    print(f"[ADMIN_RESET] Senha do admin {email} redefinida. "
          "REMOVA a variável ADMIN_RESET agora e troque a senha em 'Minha conta'.")


def _criar_admin_inicial(Usuario):
    """Cria o primeiro admin se não houver nenhum usuário ainda."""
    if Usuario.query.count() == 0:
        email = os.environ.get("ADMIN_EMAIL", "admin@stewart.local").strip().lower()
        senha = os.environ.get("ADMIN_SENHA", "").strip()
        if not senha:
            if IS_PRODUCTION:
                raise RuntimeError(
                    "ADMIN_SENHA nao definida. Defina uma senha inicial forte "
                    "antes de publicar.")
            senha = "admin"
        if IS_PRODUCTION and len(senha) < SENHA_MIN:
            raise RuntimeError(
                f"ADMIN_SENHA deve ter pelo menos {SENHA_MIN} caracteres.")
        admin = Usuario(email=email, nome="Administrador", is_admin=True,
                        criado_em=datetime.now().isoformat())
        admin.definir_senha(senha)
        db.session.add(admin)
        db.session.commit()
        print("[INFO] Usuário administrador criado.")
        print(f"       Email: {email}")
        if not os.environ.get("ADMIN_SENHA"):
            print("       Senha: admin   <-- TROQUE em 'Minha conta' após entrar!")


# Cria o app no nível do módulo (usado pelo servidor e pelos testes).
app = create_app()

# Reexporta para os testes/servidor.
from models import Comodo, Foto, Obra, Usuario  # noqa: E402,F401

if __name__ == "__main__":
    init_db()
    debug = os.environ.get("FLASK_DEBUG") == "1" and not IS_PRODUCTION
    # threaded=True: atende vários pedidos ao mesmo tempo (ex.: carregar várias
    # fotos enquanto você clica em botões) — evita a sensação de travamento.
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)),
            debug=debug, threaded=True)
