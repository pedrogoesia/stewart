"""Configuração dos testes.

DATA_DIR é apontado para uma pasta temporária ANTES de importar a aplicação
(config.py lê o ambiente no import), então os testes usam um SQLite e uma
pasta de uploads isolados — nunca tocam o data/ real nem o banco de produção.
"""

import os
import tempfile
from datetime import datetime

_tmp = tempfile.mkdtemp(prefix="stewart-testes-")
os.environ["DATA_DIR"] = _tmp
os.environ.pop("DATABASE_URL", None)   # testes sempre no SQLite temporário
os.environ.pop("FLASK_ENV", None)

import pytest  # noqa: E402
from PIL import Image  # noqa: E402

from app import app as flask_app  # noqa: E402
from config import UPLOAD_DIR  # noqa: E402
from extensions import db, limiter  # noqa: E402
from models import Comodo, Foto, Obra, Usuario  # noqa: E402

SENHA_TESTE = "senha12345"


def _criar_usuario(email, admin=False):
    u = Usuario(email=email, nome=email.split("@")[0], is_admin=admin,
                criado_em=datetime.now().isoformat())
    u.definir_senha(SENHA_TESTE)
    db.session.add(u)
    db.session.commit()
    return u


@pytest.fixture()
def app():
    flask_app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    limiter.enabled = False   # o rate limit tem outra função; aqui atrapalharia
    with flask_app.app_context():
        db.create_all()
        yield flask_app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def dados(app):
    """Usuários A, B e admin + uma obra completa (cômodo e foto) do B.

    A foto tem arquivo real no UPLOAD_DIR para os testes de /uploads.
    """
    a = _criar_usuario("a@teste.com")
    b = _criar_usuario("b@teste.com")
    admin = _criar_usuario("admin@teste.com", admin=True)

    obra = Obra(usuario_id=b.id, nome="Obra do B", endereco="Rua X",
                criado_em=datetime.now().isoformat())
    db.session.add(obra)
    db.session.commit()

    comodo = Comodo(obra_id=obra.id, nome="Sala", ordem=1)
    db.session.add(comodo)
    db.session.commit()

    abs_dir = os.path.join(UPLOAD_DIR, str(obra.id), str(comodo.id))
    os.makedirs(abs_dir, exist_ok=True)
    Image.new("RGB", (10, 10), "white").save(os.path.join(abs_dir, "foto.jpg"))

    foto = Foto(comodo_id=comodo.id, arquivo=f"{obra.id}/{comodo.id}/foto.jpg",
                descricao="Sala - parede", ordem=1,
                criado_em=datetime.now().isoformat())
    db.session.add(foto)
    db.session.commit()

    return {"a": a, "b": b, "admin": admin,
            "obra": obra, "comodo": comodo, "foto": foto}


def login(client, email):
    resp = client.post("/login", data={"email": email, "senha": SENHA_TESTE})
    assert resp.status_code in (302, 303), "login deveria redirecionar"
    return resp
