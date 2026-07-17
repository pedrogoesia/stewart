"""Agenda de Tarefas — critérios de aceite da spec fase1-agenda-tarefas.md.

Papéis: engenheiro membro (e admin/dono) gerencia tarefas; encarregado e
estagiário veem tudo da obra mas só mudam o status das próprias tarefas.
Quem não é membro recebe 404 e não deixa rastro.
"""

from datetime import date, datetime, timedelta

import pytest

from extensions import db
from models import Obra, Tarefa

from .conftest import _criar_usuario, login

HOJE = date.today()


def _tarefa(obra_id, titulo, responsavel_id=None, prazo=None,
            status="pendente"):
    t = Tarefa(obra_id=obra_id, titulo=titulo, responsavel_id=responsavel_id,
               prazo=prazo, status=status,
               criado_em=datetime.now().isoformat())
    db.session.add(t)
    db.session.commit()
    return t


@pytest.fixture()
def equipe(app):
    """Obra do admin com eng/enc/est vinculados + obra sem vínculos +
    um engenheiro de fora + uma tarefa atribuída ao encarregado."""
    admin = _criar_usuario("admin@teste.com", admin=True)
    eng = _criar_usuario("eng@teste.com")
    enc = _criar_usuario("enc@teste.com")
    est = _criar_usuario("est@teste.com")
    fora = _criar_usuario("fora@teste.com")
    eng.papel, enc.papel, est.papel, fora.papel = (
        "engenheiro", "encarregado", "estagiario", "engenheiro")

    obra = Obra(usuario_id=admin.id, nome="Obra Central", endereco="Rua Y",
                criado_em=datetime.now().isoformat())
    fechada = Obra(usuario_id=admin.id, nome="Obra Fechada", endereco="",
                   criado_em=datetime.now().isoformat())
    obra.membros = [eng, enc, est]
    db.session.add_all([obra, fechada])
    db.session.commit()

    tarefa = _tarefa(obra.id, "Conferir alvenaria", responsavel_id=enc.id,
                     prazo=HOJE)
    return {"admin": admin, "eng": eng, "enc": enc, "est": est, "fora": fora,
            "obra": obra, "fechada": fechada, "tarefa": tarefa}


# ---------------------------------------------------------------------------
# Criar / editar / excluir (só engenheiro membro, dono ou admin)
# ---------------------------------------------------------------------------
def test_engenheiro_cria_edita_exclui(client, equipe):
    login(client, "eng@teste.com")
    obra_id = equipe["obra"].id

    resp = client.post(f"/obra/{obra_id}/tarefas/criar", data={
        "titulo": "Pedir cimento", "prazo": HOJE.isoformat(),
        "responsavel_id": equipe["est"].id})
    assert resp.status_code == 200
    tarefa_id = resp.get_json()["id"]

    resp = client.post(f"/tarefa/{tarefa_id}/editar",
                       data={"titulo": "Pedir cimento CP-II"})
    assert resp.status_code == 200
    db.session.expire_all()
    assert db.session.get(Tarefa, tarefa_id).titulo == "Pedir cimento CP-II"

    assert client.post(f"/tarefa/{tarefa_id}/excluir").status_code == 200
    db.session.expire_all()
    assert db.session.get(Tarefa, tarefa_id) is None


def test_admin_gerencia_sem_vinculo_explicito(client, equipe):
    login(client, "admin@teste.com")
    resp = client.post(f"/obra/{equipe['obra'].id}/tarefas/criar",
                       data={"titulo": "Vistoria mensal"})
    assert resp.status_code == 200


@pytest.mark.parametrize("email", ["enc@teste.com", "est@teste.com"])
def test_encarregado_e_estagiario_nao_gerenciam(client, equipe, email):
    login(client, email)
    obra_id, tarefa_id = equipe["obra"].id, equipe["tarefa"].id
    assert client.post(f"/obra/{obra_id}/tarefas/criar",
                       data={"titulo": "Nao posso"}).status_code == 403
    assert client.post(f"/tarefa/{tarefa_id}/editar",
                       data={"titulo": "invadido"}).status_code == 403
    assert client.post(f"/tarefa/{tarefa_id}/excluir").status_code == 403
    db.session.expire_all()
    t = db.session.get(Tarefa, tarefa_id)
    assert t is not None and t.titulo == "Conferir alvenaria"


# ---------------------------------------------------------------------------
# Status (responsável ou quem gerencia)
# ---------------------------------------------------------------------------
def test_responsavel_muda_status_da_sua_tarefa(client, equipe):
    login(client, "enc@teste.com")
    resp = client.post(f"/tarefa/{equipe['tarefa'].id}/status",
                       data={"status": "concluida"})
    assert resp.status_code == 200
    db.session.expire_all()
    t = db.session.get(Tarefa, equipe["tarefa"].id)
    assert t.status == "concluida" and t.concluida_em


def test_membro_nao_muda_status_de_tarefa_alheia(client, equipe):
    login(client, "est@teste.com")   # membro, mas a tarefa é do encarregado
    resp = client.post(f"/tarefa/{equipe['tarefa'].id}/status",
                       data={"status": "concluida"})
    assert resp.status_code == 403
    db.session.expire_all()
    assert db.session.get(Tarefa, equipe["tarefa"].id).status == "pendente"


def test_engenheiro_muda_status_de_qualquer_tarefa_da_obra(client, equipe):
    login(client, "eng@teste.com")
    resp = client.post(f"/tarefa/{equipe['tarefa'].id}/status",
                       data={"status": "em_andamento"})
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Isolamento: quem não é membro recebe 404 e não deixa rastro
# ---------------------------------------------------------------------------
def test_nao_membro_nao_ve_nem_altera(client, equipe):
    login(client, "fora@teste.com")   # engenheiro, mas de fora da obra
    obra_id, tarefa_id = equipe["obra"].id, equipe["tarefa"].id
    assert client.get(f"/obra/{obra_id}/tarefas").status_code == 404
    assert client.post(f"/obra/{obra_id}/tarefas/criar",
                       data={"titulo": "invasao"}).status_code == 404
    assert client.post(f"/tarefa/{tarefa_id}/editar",
                       data={"titulo": "invadido"}).status_code == 404
    assert client.post(f"/tarefa/{tarefa_id}/status",
                       data={"status": "concluida"}).status_code == 404
    assert client.post(f"/tarefa/{tarefa_id}/excluir").status_code == 404
    db.session.expire_all()
    t = db.session.get(Tarefa, tarefa_id)
    assert (t is not None and t.titulo == "Conferir alvenaria"
            and t.status == "pendente")
    assert len(equipe["obra"].tarefas) == 1


def test_engenheiro_membro_ve_a_obra(client, equipe):
    # Sanidade: os 404 acima vêm do vínculo, não de rota quebrada.
    login(client, "eng@teste.com")
    resp = client.get(f"/obra/{equipe['obra'].id}/tarefas")
    assert resp.status_code == 200
    assert "Conferir alvenaria" in resp.get_data(as_text=True)


def test_sem_ferramenta_tarefas_recebe_403(client, equipe):
    equipe["eng"].definir_ferramentas(["relatorios"])
    db.session.commit()
    login(client, "eng@teste.com")
    assert client.get("/tarefas").status_code == 403


# ---------------------------------------------------------------------------
# Validações (400 sem efeito no banco)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("form", [
    {"titulo": ""},                                      # título vazio
    {"titulo": "X", "prazo": "31-12-2026"},              # prazo inválido
    {"titulo": "X", "responsavel_id": "999"},            # não é membro
])
def test_criar_invalida_retorna_400(client, equipe, form):
    login(client, "eng@teste.com")
    resp = client.post(f"/obra/{equipe['obra'].id}/tarefas/criar", data=form)
    assert resp.status_code == 400
    assert len(equipe["obra"].tarefas) == 1


def test_status_invalido_retorna_400(client, equipe):
    login(client, "enc@teste.com")
    resp = client.post(f"/tarefa/{equipe['tarefa'].id}/status",
                       data={"status": "feito"})
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Minha semana
# ---------------------------------------------------------------------------
def test_minha_semana_agrupa_por_prazo(client, equipe):
    from blueprints.tarefas import agrupar_por_prazo
    obra_id, enc_id = equipe["obra"].id, equipe["enc"].id
    atrasada = _tarefa(obra_id, "Atrasada", enc_id, HOJE - timedelta(days=2))
    semana = equipe["tarefa"]                    # prazo hoje
    futura = _tarefa(obra_id, "Futura", enc_id, HOJE + timedelta(days=30))
    sem_prazo = _tarefa(obra_id, "Sem prazo", enc_id)
    feita = _tarefa(obra_id, "Feita", enc_id, HOJE - timedelta(days=5),
                    status="concluida")

    grupos = agrupar_por_prazo([atrasada, semana, futura, sem_prazo, feita],
                               hoje=HOJE)
    assert [t.titulo for t in grupos["atrasadas"]] == ["Atrasada"]
    assert [t.titulo for t in grupos["semana"]] == ["Conferir alvenaria"]
    assert [t.titulo for t in grupos["proximas"]] == ["Futura", "Sem prazo"]
    assert all(t.status != "concluida"
               for g in grupos.values() for t in g)


def test_minha_semana_so_mostra_as_minhas(client, equipe):
    _tarefa(equipe["obra"].id, "Do estagiario", equipe["est"].id, HOJE)
    login(client, "enc@teste.com")
    resp = client.get("/tarefas")
    assert resp.status_code == 200
    corpo = resp.get_data(as_text=True)
    assert "Conferir alvenaria" in corpo
    assert "Do estagiario" not in corpo
