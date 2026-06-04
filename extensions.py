"""Extensões compartilhadas, criadas sem app (padrão application-factory).

Cada blueprint importa daqui (db, login_manager, csrf, limiter) sem depender
do app.py, evitando importações circulares. O app.py chama .init_app() nelas.
"""

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()
limiter = Limiter(get_remote_address)
