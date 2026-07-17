"""Compras — critérios de aceite da spec fase3-compras.md (v1).

Solicitante cria pedidos e vê só os seus; o setor (papel 'compras'/admin)
vê a fila, cadastra fornecedores, monta a ordem de compra e baixa o PDF.
"""

from datetime import date, datetime, timedelta

import pytest

from extensions import db
from models import (Fornecedor, ItemPedido, OrdemCompra, PedidoCompra)

from .conftest import _criar_usuario, login

HOJE = date.today()


@pytest.fixture()
def compras(app):
    comprador = _criar_usuario("comprador@teste.com")
    comprador.papel = "compras"
    solic1 = _criar_usuario("solic1@teste.com")
    solic2 = _criar_usuario("solic2@teste.com")
    sem = _criar_usuario("sem@teste.com")
    sem.definir_ferramentas(["relatorios"])
    db.session.commit()

    pedido = PedidoCompra(obra_nome="Residência Murilo e Ana Flávia",
                          solicitante_id=solic1.id,
                          data_prevista=HOJE + timedelta(days=3),
                          criado_em=datetime.now().isoformat())
    db.session.add(pedido)
    db.session.commit()
    db.session.add_all([
        ItemPedido(pedido_id=pedido.id, descricao="Repelente Off",
                   unidade="UNID", quantidade=3, ordem=1),
        ItemPedido(pedido_id=pedido.id, descricao="Balde de desmoldante Denver 18L",
                   unidade="UNID", quantidade=5, ordem=2),
    ])
    fornecedor = Fornecedor(nome="Materiais Cruzada LTDA",
                            cnpj="42.462.242/0001-47",
                            email="vendas@cruzadanet.com.br",
                            contato="Carolina",
                            criado_em=datetime.now().isoformat())
    db.session.add(fornecedor)
    db.session.commit()
    return {"comprador": comprador, "solic1": solic1, "solic2": solic2,
            "sem": sem, "pedido": pedido, "fornecedor": fornecedor}


def _criar_ordem(client, compras_fix):
    resp = client.post(
        f"/compras/pedido/{compras_fix['pedido'].id}/ordem/criar",
        data={"fornecedor_id": compras_fix["fornecedor"].id,
              "faturamento_razao": "MURILO LEITE DE OLIVEIRA",
              "faturamento_cnpj_cpf": "649.623.933-91",
              "entrega_endereco": "Rua Félix Pacheco, 52 - Leblon, RJ"})
    return resp


# ---------------------------------------------------------------------------
# Pedidos (solicitante)
# ---------------------------------------------------------------------------
def test_solicitante_cria_pedido_com_itens(client, compras):
    login(client, "solic2@teste.com")
    resp = client.post("/compras/pedidos/criar", data={
        "obra_nome": "Obra Central",
        "data_prevista": (HOJE + timedelta(days=5)).isoformat(),
        "descricao": ["Cimento CP-II 50kg", "Areia média (m³)"],
        "unidade": ["SC", "M3"],
        "quantidade": ["20", "4"]})
    assert resp.status_code == 200
    pedido = db.session.get(PedidoCompra, resp.get_json()["id"])
    assert pedido.obra_nome == "Obra Central"
    assert [i.descricao for i in pedido.itens] == ["Cimento CP-II 50kg",
                                                   "Areia média (m³)"]
    assert pedido.status == "aberto"


@pytest.mark.parametrize("form", [
    {"obra_nome": "X"},                                        # sem itens
    {"obra_nome": "X", "descricao": [""], "unidade": ["UN"],
     "quantidade": ["1"]},                                     # item vazio
    {"obra_nome": "X", "descricao": ["Cimento"], "unidade": ["SC"],
     "quantidade": ["abc"]},                                   # qtde inválida
    {"obra_nome": "", "descricao": ["Cimento"], "unidade": ["SC"],
     "quantidade": ["1"]},                                     # sem obra
])
def test_pedido_invalido_retorna_400(client, compras, form):
    login(client, "solic2@teste.com")
    antes = PedidoCompra.query.count()
    assert client.post("/compras/pedidos/criar", data=form).status_code == 400
    assert PedidoCompra.query.count() == antes


def test_solicitante_ve_so_os_seus(client, compras):
    pid = compras["pedido"].id
    login(client, "solic1@teste.com")
    assert client.get(f"/compras/pedido/{pid}").status_code == 200
    client.get("/logout")
    login(client, "solic2@teste.com")
    assert client.get(f"/compras/pedido/{pid}").status_code == 404
    client.get("/logout")
    login(client, "comprador@teste.com")
    assert client.get(f"/compras/pedido/{pid}").status_code == 200


def test_fila_do_setor_e_meus_pedidos(client, compras):
    login(client, "comprador@teste.com")
    corpo = client.get("/compras").get_data(as_text=True)
    assert "Residência Murilo e Ana Flávia" in corpo
    client.get("/logout")
    login(client, "solic2@teste.com")
    corpo = client.get("/compras").get_data(as_text=True)
    assert "Residência Murilo e Ana Flávia" not in corpo   # não é dele


def test_sem_ferramenta_recebe_403(client, compras):
    login(client, "sem@teste.com")
    assert client.get("/compras").status_code == 403


# ---------------------------------------------------------------------------
# Fornecedores (setor)
# ---------------------------------------------------------------------------
def test_so_setor_cadastra_fornecedor(client, compras):
    login(client, "solic1@teste.com")
    resp = client.post("/compras/fornecedores/criar", data={"nome": "X"})
    assert resp.status_code == 403
    client.get("/logout")
    login(client, "comprador@teste.com")
    resp = client.post("/compras/fornecedores/criar", data={
        "nome": "Stan Elétrica LTDA", "email": "vendas@stan.com.br"})
    assert resp.status_code == 200
    assert Fornecedor.query.filter_by(nome="Stan Elétrica LTDA").first()
    assert client.post("/compras/fornecedores/criar",
                       data={"nome": " "}).status_code == 400


# ---------------------------------------------------------------------------
# Ordem de compra (setor)
# ---------------------------------------------------------------------------
def test_setor_cria_ordem_a_partir_do_pedido(client, compras):
    login(client, "comprador@teste.com")
    resp = _criar_ordem(client, compras)
    assert resp.status_code == 200
    ordem = db.session.get(OrdemCompra, resp.get_json()["id"])
    assert [i.descricao for i in ordem.itens] == [
        "Repelente Off", "Balde de desmoldante Denver 18L"]
    db.session.expire_all()
    assert db.session.get(PedidoCompra, compras["pedido"].id) \
             .status == "atendido"


def test_solicitante_nao_cria_ordem(client, compras):
    login(client, "solic1@teste.com")   # dono do pedido, mas não é do setor
    assert _criar_ordem(client, compras).status_code == 403
    assert OrdemCompra.query.count() == 0


def test_editar_precos_calcula_totais(client, compras):
    login(client, "comprador@teste.com")
    ordem_id = _criar_ordem(client, compras).get_json()["id"]
    ordem = db.session.get(OrdemCompra, ordem_id)
    i1, i2 = ordem.itens
    resp = client.post(f"/compras/ordem/{ordem_id}/editar", data={
        f"valor_unit_{i1.id}": "25.50", f"valor_unit_{i2.id}": "89.90",
        "frete": "40", "desconto": "10",
        "cond_pagamento": "DEPÓSITO X 28 DIAS"})
    assert resp.status_code == 200
    db.session.expire_all()
    ordem = db.session.get(OrdemCompra, ordem_id)
    # 3×25.50 + 5×89.90 = 76.50 + 449.50 = 526.00 → +40 −10 = 556.00
    assert ordem.subtotal() == pytest.approx(526.00)
    assert ordem.total() == pytest.approx(556.00)
    assert ordem.cond_pagamento == "DEPÓSITO X 28 DIAS"


def test_valor_invalido_retorna_400(client, compras):
    login(client, "comprador@teste.com")
    ordem_id = _criar_ordem(client, compras).get_json()["id"]
    resp = client.post(f"/compras/ordem/{ordem_id}/editar",
                       data={"frete": "abc"})
    assert resp.status_code == 400


def test_pdf_da_ordem_so_para_o_setor(client, compras):
    login(client, "comprador@teste.com")
    ordem_id = _criar_ordem(client, compras).get_json()["id"]
    resp = client.get(f"/compras/ordem/{ordem_id}/pdf")
    assert resp.status_code == 200
    assert resp.data[:5] == b"%PDF-"
    assert len(resp.data) > 2000
    client.get("/logout")
    login(client, "solic1@teste.com")
    assert client.get(f"/compras/ordem/{ordem_id}/pdf").status_code == 404
