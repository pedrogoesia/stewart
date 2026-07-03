"""Configuração central da plataforma (caminhos, constantes e ambiente).

Carrega o .env antes de qualquer leitura de variáveis para que todos os
módulos enxerguem a mesma configuração.
"""

import os
from pathlib import Path

# Carrega variáveis do .env (OPENAI_API_KEY, SECRET_KEY, DATABASE_URL, ...).
try:
    from dotenv import load_dotenv
    _aqui = os.path.dirname(os.path.abspath(__file__))
    load_dotenv(os.path.join(_aqui, ".env"))
    load_dotenv()
except Exception:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Pasta de dados (banco SQLite local e fotos). Em produção (ex.: Render) aponte
# DATA_DIR para um disco persistente, senão as fotos se perdem a cada deploy.
DATA_DIR = os.environ.get("DATA_DIR", "").strip() or os.path.join(BASE_DIR, "data")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
DB_PATH = os.path.join(DATA_DIR, "stewart.db")
TEMPLATE_PATH = os.path.join(BASE_DIR, "template", "TEMPLATE_STEWART.pptx")

MAX_IMG_SIDE = 2000          # redimensiona fotos para no máx. 2000px (lado maior)
JPEG_QUALITY = 85
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP", "HEIF", "HEIC"}
MAX_IMAGE_PIXELS = int(os.environ.get("MAX_IMAGE_PIXELS", "50000000"))
SENHA_MIN = 8                # tamanho mínimo de senha

MESES = ["JANEIRO", "FEVEREIRO", "MARÇO", "ABRIL", "MAIO", "JUNHO", "JULHO",
         "AGOSTO", "SETEMBRO", "OUTUBRO", "NOVEMBRO", "DEZEMBRO"]

# Estamos em produção? (banco externo configurado ou FLASK_ENV=production).
IS_PRODUCTION = (bool(os.environ.get("DATABASE_URL", "").strip())
                 or os.environ.get("FLASK_ENV") == "production")

os.makedirs(UPLOAD_DIR, exist_ok=True)


def database_url():
    """URL do banco: DATABASE_URL (produção) ou SQLite local."""
    url = os.environ.get("DATABASE_URL", "").strip()
    if url:
        # Provedores entregam "postgres://..."; o SQLAlchemy precisa do driver.
        if url.startswith("postgres://"):
            url = "postgresql+psycopg://" + url[len("postgres://"):]
        elif url.startswith("postgresql://"):
            url = "postgresql+psycopg://" + url[len("postgresql://"):]
        return url
    return "sqlite:///" + Path(DB_PATH).as_posix()
