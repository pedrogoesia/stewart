"""Manutenções — critérios de aceite da spec fase2-manutencao.md.

Gestor (admin ou papel 'manutencao') cadastra obras entregues e agenda;
executor (ex.: encarregado) vê só as manutenções dele, conclui com descrição
e envia fotos. Quem não deve ver recebe 404; quem não pode agir, 403.
"""

import io
import os
from datetime import date, datetime, timedelta

import pytest
from PIL import Image

from config import UPLOAD_DIR
from extensions import db
from models import FotoManutencao, Manutencao, ObraEntregue

from .conftest import _criar_usuario, login

HOJE = date.today()


def _manutencao(obra_id, titulo, responsavel_id=None, data=None,
                status="agendada"):
    m = Manutencao(obra_entregue_id=obra_id, titulo=titulo,
                   responsavel_id=responsavel_id, data_agendada=data,
                   status=status, criado_em=datetime.now().isoformat())
    db.session.add(m)
    db.session.commit()
    return m


@pytest.fixture()
def setor(app):
    """Gestor do setor + dois executores + um usuário sem a ferramenta +
    uma obra entregue com manutenção agendada para o executor 1."""
    gestor = _criar_usuario("setor@teste.com")
    gestor.papel = "manutencao"
    exec1 = _criar_usuario("exec1@teste.com")
    exec1.papel = "encarregado"
    exec2 = _criar_usuario("exec2@teste.com")
    exec2.papel = "encarregado"
    sem = _criar_usuario("sem@teste.com")
    sem.definir_ferramentas(["relatorios"])

    obra = ObraEntregue(cliente="Cobertura 14", endereco="Rua Alfa, 100",
                        data_entrega=HOJE - timedelta(days=400),
                        criado_em=datetime.now().isoformat())
    db.session.add(obra)
    db.session.commit()

    m = _manutencao(obra.id, "Revisar infiltração da sacada",
                    responsavel_id=exec1.id, data=HOJE)
    return {"gestor": gestor, "exec1": exec1, "exec2": exec2, "sem": sem,
            "obra": obra, "m": m}


# ---------------------------------------------------------------------------
# Obra entregue (só gestor)
# ---------------------------------------------------------------------------
def test_gestor_cria_e_ve_obra_entregue(client, setor):
    login(client, "setor@teste.com")
    resp = client.post("/manutencao/obras/criar", data={
        "cliente": "Residencial Beta", "endereco": "Rua Beta, 200",
        "data_entrega": (HOJE - timedelta(days=30)).isoformat()})
    assert resp.status_code == 200
    assert ObraEntregue.query.filter_by(cliente="Residencial Beta").first()

    resp = client.get(f"/manutencao/obra/{setor['obra'].id}")
    assert resp.status_code == 200
    assert "Cobertura 14" in resp.get_data(as_text=True)


def test_executor_nao_cria_nem_ve_obra_entregue(client, setor):
    login(client, "exec1@teste.com")
    resp = client.post("/manutencao/obras/criar", data={"cliente": "Invasao"})
    assert resp.status_code == 403
    assert ObraEntregue.query.filter_by(cliente="Invasao").first() is None
    assert client.get(f"/manutencao/obra/{setor['obra'].id}").status_code == 404


def test_sem_ferramenta_recebe_403(client, setor):
    login(client, "sem@teste.com")
    assert client.get("/manutencao").status_code == 403


def test_cliente_vazio_retorna_400(client, setor):
    login(client, "setor@teste.com")
    resp = client.post("/manutencao/obras/criar", data={"cliente": ""})
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Agendamento (só gestor; responsável precisa ter a ferramenta)
# ---------------------------------------------------------------------------
def test_gestor_agenda_para_executor(client, setor):
    login(client, "setor@teste.com")
    resp = client.post(f"/manutencao/obra/{setor['obra'].id}/agendar", data={
        "titulo": "Trocar rejunte da garagem",
        "data_agendada": (HOJE + timedelta(days=3)).isoformat(),
        "responsavel_id": setor["exec2"].id})
    assert resp.status_code == 200
    m = Manutencao.query.filter_by(titulo="Trocar rejunte da garagem").first()
    assert m is not None and m.responsavel_id == setor["exec2"].id


def test_responsavel_sem_ferramenta_retorna_400(client, setor):
    login(client, "setor@teste.com")
    resp = client.post(f"/manutencao/obra/{setor['obra'].id}/agendar", data={
        "titulo": "X", "responsavel_id": setor["sem"].id})
    assert resp.status_code == 400


def test_executor_nao_agenda(client, setor):
    login(client, "exec1@teste.com")
    resp = client.post(f"/manutencao/obra/{setor['obra'].id}/agendar",
                       data={"titulo": "Invasao"})
    assert resp.status_code in (403, 404)   # nem enxerga a obra do setor
    assert Manutencao.query.filter_by(titulo="Invasao").first() is None


# ---------------------------------------------------------------------------
# Minha semana do executor
# ---------------------------------------------------------------------------
def test_executor_ve_so_as_suas(client, setor):
    _manutencao(setor["obra"].id, "Do outro executor",
                responsavel_id=setor["exec2"].id, data=HOJE)
    login(client, "exec1@teste.com")
    resp = client.get("/manutencao")
    assert resp.status_code == 200
    corpo = resp.get_data(as_text=True)
    assert "Revisar infiltração da sacada" in corpo
    assert "Do outro executor" not in corpo
    assert "Cobertura 14" in corpo          # contexto do cliente aparece


# ---------------------------------------------------------------------------
# Conclusão (responsável ou gestor; descrição obrigatória)
# ---------------------------------------------------------------------------
def test_executor_conclui_a_sua_com_descricao(client, setor):
    login(client, "exec1@teste.com")
    m_id = setor["m"].id
    resp = client.post(f"/manutencao/{m_id}/concluir",
                       data={"descricao_realizada": "Refeita a "
                             "impermeabilização e troca do rodapé."})
    assert resp.status_code == 200
    db.session.expire_all()
    m = db.session.get(Manutencao, m_id)
    assert m.status == "concluida" and m.concluida_em
    assert "impermeabilização" in m.descricao_realizada


def test_concluir_sem_descricao_retorna_400(client, setor):
    login(client, "exec1@teste.com")
    resp = client.post(f"/manutencao/{setor['m'].id}/concluir",
                       data={"descricao_realizada": "  "})
    assert resp.status_code == 400
    db.session.expire_all()
    assert db.session.get(Manutencao, setor["m"].id).status == "agendada"


def test_executor_nao_conclui_de_outro(client, setor):
    login(client, "exec2@teste.com")
    resp = client.post(f"/manutencao/{setor['m'].id}/concluir",
                       data={"descricao_realizada": "invadido"})
    assert resp.status_code == 404
    db.session.expire_all()
    assert db.session.get(Manutencao, setor["m"].id).status == "agendada"


def test_gestor_conclui_qualquer_uma(client, setor):
    login(client, "setor@teste.com")
    resp = client.post(f"/manutencao/{setor['m'].id}/concluir",
                       data={"descricao_realizada": "Feito pelo setor."})
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Fotos da manutenção
# ---------------------------------------------------------------------------
def _png(largura=1600, altura=1200):
    buf = io.BytesIO()
    Image.new("RGB", (largura, altura), "gray").save(buf, format="PNG")
    buf.seek(0)
    return buf


def test_responsavel_envia_foto_processada(client, setor):
    login(client, "exec1@teste.com")
    m_id = setor["m"].id
    resp = client.post(f"/manutencao/{m_id}/fotos",
                       data={"foto": (_png(3000, 1500), "servico.png")},
                       content_type="multipart/form-data")
    assert resp.status_code == 200
    foto = FotoManutencao.query.filter_by(manutencao_id=m_id).first()
    assert foto is not None
    caminho = os.path.join(UPLOAD_DIR, foto.arquivo)
    with Image.open(caminho) as img:
        assert img.format == "JPEG" and max(img.size) == 2000

    # Servida para o responsável e para o gestor…
    assert client.get(f"/manutencao/foto/{foto.id}").status_code == 200
    client.get("/logout")
    login(client, "setor@teste.com")
    assert client.get(f"/manutencao/foto/{foto.id}").status_code == 200
    # …mas não para outro executor.
    client.get("/logout")
    login(client, "exec2@teste.com")
    assert client.get(f"/manutencao/foto/{foto.id}").status_code == 404


# ---------------------------------------------------------------------------
# Histórico e exclusão
# ---------------------------------------------------------------------------
def test_historico_mostra_concluidas(client, setor):
    login(client, "exec1@teste.com")
    client.post(f"/manutencao/{setor['m'].id}/concluir",
                data={"descricao_realizada": "Serviço concluído e testado."})
    client.get("/logout")
    login(client, "setor@teste.com")
    corpo = client.get(f"/manutencao/obra/{setor['obra'].id}") \
                  .get_data(as_text=True)
    assert "Serviço concluído e testado." in corpo


def test_so_gestor_exclui_manutencao(client, setor):
    login(client, "exec1@teste.com")
    assert client.post(f"/manutencao/{setor['m'].id}/excluir") \
                 .status_code == 403
    client.get("/logout")
    login(client, "setor@teste.com")
    assert client.post(f"/manutencao/{setor['m'].id}/excluir") \
                 .status_code == 200
    db.session.expire_all()
    assert db.session.get(Manutencao, setor["m"].id) is None


# ---------------------------------------------------------------------------
# Kanban do setor (Fase 2b — specs/fase2b-manutencao-kanban.md)
# ---------------------------------------------------------------------------
def test_status_gestor_e_responsavel_movem(client, setor):
    m_id = setor["m"].id
    login(client, "exec1@teste.com")   # responsável
    resp = client.post(f"/manutencao/{m_id}/status",
                       data={"status": "em_execucao"})
    assert resp.status_code == 200
    db.session.expire_all()
    assert db.session.get(Manutencao, m_id).status == "em_execucao"
    client.get("/logout")

    login(client, "setor@teste.com")   # gestor move de volta
    resp = client.post(f"/manutencao/{m_id}/status",
                       data={"status": "agendada"})
    assert resp.status_code == 200
    db.session.expire_all()
    assert db.session.get(Manutencao, m_id).status == "agendada"


def test_status_400_para_invalido_e_concluida(client, setor):
    m_id = setor["m"].id
    login(client, "setor@teste.com")
    assert client.post(f"/manutencao/{m_id}/status",
                       data={"status": "pausada"}).status_code == 400
    # Concluir não passa pelo /status (descrição é obrigatória lá).
    assert client.post(f"/manutencao/{m_id}/status",
                       data={"status": "concluida"}).status_code == 400
    db.session.expire_all()
    assert db.session.get(Manutencao, m_id).status == "agendada"


def test_status_nao_reabre_concluida(client, setor):
    m = _manutencao(setor["obra"].id, "Já fechada", status="concluida")
    login(client, "setor@teste.com")
    assert client.post(f"/manutencao/{m.id}/status",
                       data={"status": "agendada"}).status_code == 400
    db.session.expire_all()
    assert db.session.get(Manutencao, m.id).status == "concluida"


def test_status_executor_de_fora_e_sem_ferramenta(client, setor):
    m_id = setor["m"].id
    login(client, "exec2@teste.com")   # tem a ferramenta, não é o responsável
    assert client.post(f"/manutencao/{m_id}/status",
                       data={"status": "em_execucao"}).status_code == 404
    client.get("/logout")
    login(client, "sem@teste.com")     # sem a ferramenta
    assert client.post(f"/manutencao/{m_id}/status",
                       data={"status": "em_execucao"}).status_code == 403
    db.session.expire_all()
    assert db.session.get(Manutencao, m_id).status == "agendada"


def test_em_execucao_conta_como_pendente_na_semana(client, setor):
    setor["m"].status = "em_execucao"
    db.session.commit()
    login(client, "exec1@teste.com")
    corpo = client.get("/manutencao").get_data(as_text=True)
    assert "Revisar infiltração da sacada" in corpo   # segue na semana dele


def test_kanban_do_gestor_mostra_colunas_e_cards(client, setor):
    _manutencao(setor["obra"].id, "Trocar rejunte", status="em_execucao")
    login(client, "setor@teste.com")
    resp = client.get("/manutencao")
    assert resp.status_code == 200
    corpo = resp.get_data(as_text=True)
    for coluna in ("Agendada", "Em execução", "Concluída"):
        assert coluna in corpo
    assert "Revisar infiltração da sacada" in corpo
    assert "Trocar rejunte" in corpo
    assert "Cobertura 14" in corpo   # card do quadro geral mostra o cliente
