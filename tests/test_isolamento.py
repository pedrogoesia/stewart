"""Isolamento por usuário: A nunca lê/altera recursos do B.

Toda rota de obra/cômodo/foto/upload deve responder 404 para quem não é o
dono (nem admin) e não deixar rastro no banco. Estes testes são a garantia
de segurança mais importante do sistema — se algum falhar, NÃO publique.
"""

import pytest

from extensions import db
from models import Comodo, Foto, Obra

from .conftest import login

# Rotas de leitura: {obra}/{comodo}/{foto}/{arquivo} são preenchidos com os
# recursos do usuário B; o A logado deve receber 404 em todas.
LEITURA = [
    "/obra/{obra}",
    "/obra/{obra}/relatorio.pptx",
    "/obra/{obra}/fotos.zip",
    "/uploads/{arquivo}",
]

# Rotas de escrita: além do 404, nada pode mudar no banco.
ESCRITA = [
    ("/obra/{obra}/editar", {"nome": "invadido"}),
    ("/obra/{obra}/excluir", {}),
    ("/obra/{obra}/comodos", {"nome": "Invasao"}),
    ("/obra/{obra}/comodo-geral", {}),
    ("/obra/{obra}/comodos/reordenar", {"ordem": "1"}),
    ("/comodo/{comodo}/renomear", {"nome": "invadido"}),
    ("/comodo/{comodo}/excluir", {}),
    ("/comodo/{comodo}/reordenar", {"ordem": "1"}),
    ("/comodo/{comodo}/fotos", {}),
    ("/foto/{foto}/descricao", {"descricao": "invadido"}),
    ("/foto/{foto}/excluir", {}),
    ("/foto/{foto}/aplicar-edicao", {}),
    ("/foto/{foto}/descartar-edicao", {}),
]


def _url(template, dados):
    return template.format(obra=dados["obra"].id,
                           comodo=dados["comodo"].id,
                           foto=dados["foto"].id,
                           arquivo=dados["foto"].arquivo)


def _nada_mudou(dados):
    """Recarrega do banco e confere que os dados do B seguem intactos."""
    db.session.expire_all()
    obra = db.session.get(Obra, dados["obra"].id)
    comodo = db.session.get(Comodo, dados["comodo"].id)
    foto = db.session.get(Foto, dados["foto"].id)
    assert obra is not None and obra.nome == "Obra do B"
    assert comodo is not None and comodo.nome == "Sala"
    assert foto is not None and foto.descricao == "Sala - parede"
    assert len(obra.comodos) == 1, "cômodo criado por quem não é o dono"


@pytest.mark.parametrize("rota", LEITURA)
def test_leitura_cruzada_retorna_404(client, dados, rota):
    login(client, "a@teste.com")
    resp = client.get(_url(rota, dados))
    assert resp.status_code == 404


@pytest.mark.parametrize("rota,form", ESCRITA)
def test_escrita_cruzada_retorna_404_e_nao_altera(client, dados, rota, form):
    login(client, "a@teste.com")
    resp = client.post(_url(rota, dados), data=form)
    assert resp.status_code == 404
    _nada_mudou(dados)


def test_editar_ia_cruzado_nunca_processa(client, dados):
    # Sem OPENAI_API_KEY a rota responde 400 antes de olhar a foto; com a
    # chave, o dono é verificado (404) antes de qualquer chamada à OpenAI.
    # Nos dois casos, nunca 200 e nada muda.
    login(client, "a@teste.com")
    resp = client.post(f"/foto/{dados['foto'].id}/editar-ia",
                       data={"prompt": "apagar tudo"})
    assert resp.status_code in (400, 404)
    _nada_mudou(dados)


def test_anonimo_e_redirecionado_para_login(client, dados):
    resp = client.get(f"/obra/{dados['obra'].id}")
    assert resp.status_code in (302, 303)
    assert "/login" in resp.headers["Location"]


def test_dono_acessa_normalmente(client, dados):
    # Sanidade: garante que os 404 acima vêm do isolamento, não de rota quebrada.
    login(client, "b@teste.com")
    assert client.get(f"/obra/{dados['obra'].id}").status_code == 200
    assert client.get(f"/uploads/{dados['foto'].arquivo}").status_code == 200
    assert client.get(f"/obra/{dados['obra'].id}/fotos.zip").status_code == 200


def test_admin_acessa_recursos_de_todos(client, dados):
    login(client, "admin@teste.com")
    assert client.get(f"/obra/{dados['obra'].id}").status_code == 200
