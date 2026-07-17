"""Permissão por ferramenta e rotas de administração.

Usuário sem a ferramenta liberada recebe 403; rotas /admin/* são exclusivas
de admin (403 para os demais, sem efeito no banco).
"""

import pytest

from extensions import db
from models import Usuario

from .conftest import _criar_usuario, login


@pytest.fixture()
def so_relatorios(app):
    """Usuário com apenas a ferramenta 'relatorios' liberada."""
    u = _criar_usuario("relatorios@teste.com")
    u.definir_ferramentas(["relatorios"])
    db.session.commit()
    return u


@pytest.fixture()
def so_atas(app):
    """Usuário com apenas a ferramenta 'atas' liberada."""
    u = _criar_usuario("atas@teste.com")
    u.definir_ferramentas(["atas"])
    db.session.commit()
    return u


def test_sem_ferramenta_atas_recebe_403(client, so_relatorios):
    login(client, "relatorios@teste.com")
    assert client.get("/atas").status_code == 403
    assert client.post("/atas/ia", json={"texto": "reunião"}).status_code == 403


def test_sem_ferramenta_relatorios_recebe_403(client, so_atas):
    login(client, "atas@teste.com")
    assert client.get("/relatorios").status_code == 403
    assert client.post("/obras", data={"nome": "Obra X"}).status_code == 403


def test_com_ferramenta_acessa(client, so_relatorios, so_atas):
    login(client, "relatorios@teste.com")
    assert client.get("/relatorios").status_code == 200
    client.get("/logout")
    login(client, "atas@teste.com")
    assert client.get("/atas").status_code == 200


def test_atas_ia_sem_texto_retorna_400(client, so_atas):
    # Validação barata vem antes de qualquer chamada à OpenAI.
    login(client, "atas@teste.com")
    resp = client.post("/atas/ia", json={"texto": ""})
    assert resp.status_code == 400


def test_login_com_senha_errada_nao_entra(client, dados):
    resp = client.post("/login", data={"email": "a@teste.com",
                                       "senha": "senha-errada"})
    assert resp.status_code == 200          # volta ao login com erro
    # Continua deslogado: página inicial redireciona ao login.
    resp = client.get("/")
    assert resp.status_code in (302, 303)
    assert "/login" in resp.headers["Location"]


ROTAS_ADMIN_GET = ["/admin/usuarios", "/admin/atividades"]


@pytest.mark.parametrize("rota", ROTAS_ADMIN_GET)
def test_nao_admin_nao_ve_paginas_admin(client, dados, rota):
    login(client, "a@teste.com")
    assert client.get(rota).status_code == 403


def test_nao_admin_nao_cria_usuario(client, dados):
    login(client, "a@teste.com")
    resp = client.post("/admin/usuarios/criar",
                       data={"email": "novo@teste.com", "senha": "senha12345"})
    assert resp.status_code == 403
    assert Usuario.query.filter_by(email="novo@teste.com").first() is None


def test_nao_admin_nao_exclui_nem_troca_senha(client, dados):
    login(client, "a@teste.com")
    alvo = dados["b"].id
    assert client.post(f"/admin/usuarios/{alvo}/excluir").status_code == 403
    assert client.post(f"/admin/usuarios/{alvo}/senha",
                       data={"senha": "outra12345"}).status_code == 403
    db.session.expire_all()
    b = db.session.get(Usuario, alvo)
    assert b is not None and b.conferir_senha("senha12345")


def test_admin_cria_usuario_com_ferramentas(client, dados):
    login(client, "admin@teste.com")
    resp = client.post("/admin/usuarios/criar", data={
        "email": "novo@teste.com", "senha": "senha12345",
        "ferramentas": ["atas"]})
    assert resp.status_code == 200
    novo = Usuario.query.filter_by(email="novo@teste.com").first()
    assert novo is not None
    assert novo.pode_ver_ferramenta("atas")
    assert not novo.pode_ver_ferramenta("relatorios")


def test_admin_define_papel_e_vincula_obras(client, dados):
    login(client, "admin@teste.com")
    alvo, obra = dados["a"], dados["obra"]
    resp = client.post(f"/admin/usuarios/{alvo.id}/equipe",
                       data={"papel": "encarregado", "obras": [obra.id]})
    assert resp.status_code == 200
    db.session.expire_all()
    a = db.session.get(Usuario, alvo.id)
    assert a.papel == "encarregado"
    assert [o.id for o in a.obras_membro] == [obra.id]

    # Desmarcar tudo remove papel e vínculos.
    client.post(f"/admin/usuarios/{alvo.id}/equipe", data={"papel": ""})
    db.session.expire_all()
    a = db.session.get(Usuario, alvo.id)
    assert a.papel is None and a.obras_membro == []


def test_nao_admin_nao_define_equipe(client, dados):
    login(client, "a@teste.com")
    resp = client.post(f"/admin/usuarios/{dados['b'].id}/equipe",
                       data={"papel": "engenheiro"})
    assert resp.status_code == 403
    db.session.expire_all()
    assert db.session.get(Usuario, dados["b"].id).papel is None


def test_admin_nao_cria_usuario_com_senha_fraca(client, dados):
    login(client, "admin@teste.com")
    client.post("/admin/usuarios/criar",
                data={"email": "fraco@teste.com", "senha": "123"})
    assert Usuario.query.filter_by(email="fraco@teste.com").first() is None
