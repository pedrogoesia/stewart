"""Extensões compartilhadas, criadas sem app (padrão application-factory).

Cada blueprint importa daqui (db, login_manager, csrf, limiter) sem depender
do app.py, evitando importações circulares. O app.py chama .init_app() nelas.
"""

import sqlite3

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from sqlalchemy import event
from sqlalchemy.engine import Engine

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()
limiter = Limiter(get_remote_address)


@event.listens_for(Engine, "connect")
def _fiscalizar_fk_no_sqlite(conexao, _registro):
    # SQLite ignora FOREIGN KEYs por padrão; sem isto, dev e testes aceitam
    # vínculos inválidos que o Postgres de produção recusa — bugs dessa
    # classe ficariam invisíveis para a suíte.
    if isinstance(conexao, sqlite3.Connection):
        cursor = conexao.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
