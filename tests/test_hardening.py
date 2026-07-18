"""Hardening pós-auditoria — critérios da spec hardening-auditoria.md.

Cobre os defeitos da auditoria de 18/07/2026: exclusões que violavam FK
(usuário com vínculos de manutenção/compras; obra referenciada por pedido),
fiscalização de FK no SQLite, PDF com caracteres especiais, dinheiro como
Decimal e validações de fronteira em Compras (400, nunca 500).
"""

from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import (Fornecedor, ItemPedido, Manutencao, Obra, ObraEntregue,
                    OrdemCompra, PedidoCompra, Usuario)

from .conftest import _criar_usuario, login


@pytest.fixture()
def cenario(app):
    """Admin, comprador (setor), solicitante com pedido aberto e fornecedor.

    Os textos levam <, > e & de propósito: são entradas reais (medidas de
    material, razões sociais) que o PDF precisa aguentar.
    """
    admin = _criar_usuario("admin@teste.com", admin=True)
    comprador = _criar_usuario("comprador@teste.com")
    comprador.papel = "compras"
    solic = _criar_usuario("solic@teste.com")
    db.session.commit()

    pedido = PedidoCompra(obra_nome="Obra Central", solicitante_id=solic.id,
                          criado_em=datetime.now().isoformat())
    db.session.add(pedido)
    db.session.commit()
    db.session.add(ItemPedido(pedido_id=pedido.id,
                              descricao='Vergalhão 3/8" <CA-50 & aço',
                              unidade="UNID", quantidade=3, ordem=1))
    fornecedor = Fornecedor(nome="Aço & Cia", cnpj="00.000.000/0001-00",
                            criado_em=datetime.now().isoformat())
    db.session.add(fornecedor)
    db.session.commit()
    return {"admin": admin, "comprador": comprador, "solic": solic,
            "pedido": pedido, "fornecedor": fornecedor}


def _criar_ordem(client, cenario):
    return client.post(
        f"/compras/pedido/{cenario['pedido'].id}/ordem/criar",
        data={"fornecedor_id": cenario["fornecedor"].id})


# ---------------------------------------------------------------------------
# FKs fiscalizadas no SQLite (dev/testes iguais ao Postgres de produção)
# ---------------------------------------------------------------------------
def test_fk_invalida_e_recusada_no_sqlite(app):
    db.session.add(ItemPedido(pedido_id=99999, descricao="órfão",
                              quantidade=1, ordem=1))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


# ---------------------------------------------------------------------------
# Exclusões íntegras (histórico sobrevive, vínculos ficam NULL)
# ---------------------------------------------------------------------------
def test_excluir_usuario_com_vinculos_de_manutencao_e_compras(client, cenario):
    solic = cenario["solic"]
    obra_e = ObraEntregue(cliente="Cliente Antigo",
                          criado_em=datetime.now().isoformat())
    db.session.add(obra_e)
    db.session.commit()
    m = Manutencao(obra_entregue_id=obra_e.id, titulo="Rejunte da varanda",
                   responsavel_id=solic.id, criador_id=solic.id,
                   criado_em=datetime.now().isoformat())
    db.session.add(m)
    db.session.commit()
    m_id, pedido_id, solic_id = m.id, cenario["pedido"].id, solic.id

    login(client, "admin@teste.com")
    resp = client.post(f"/admin/usuarios/{solic_id}/excluir")
    assert resp.status_code == 200

    assert db.session.get(Usuario, solic_id) is None
    m = db.session.get(Manutencao, m_id)
    assert m is not None and m.responsavel_id is None and m.criador_id is None
    pedido = db.session.get(PedidoCompra, pedido_id)
    assert pedido is not None and pedido.solicitante_id is None


def test_excluir_obra_preserva_pedido_de_compra(client, cenario):
    dono = cenario["solic"]
    obra = Obra(usuario_id=dono.id, nome="Obra Vinculada",
                criado_em=datetime.now().isoformat())
    db.session.add(obra)
    db.session.commit()
    cenario["pedido"].obra_id = obra.id
    db.session.commit()
    obra_id, pedido_id = obra.id, cenario["pedido"].id

    login(client, "solic@teste.com")
    resp = client.post(f"/obra/{obra_id}/excluir")
    assert resp.status_code in (302, 303)

    pedido = db.session.get(PedidoCompra, pedido_id)
    assert pedido is not None and pedido.obra_id is None
    assert pedido.obra_nome == "Obra Central"   # nome desnormalizado fica


# ---------------------------------------------------------------------------
# PDF aguenta texto real (markup não interpretado)
# ---------------------------------------------------------------------------
def test_pdf_com_caracteres_especiais(client, cenario):
    login(client, "comprador@teste.com")
    ordem_id = _criar_ordem(client, cenario).get_json()["id"]
    resp = client.post(f"/compras/ordem/{ordem_id}/editar",
                       data={"obs": "Entregar <i>antes do dia 25 & avisar"})
    assert resp.status_code == 200
    resp = client.get(f"/compras/ordem/{ordem_id}/pdf")
    assert resp.status_code == 200
    assert resp.data.startswith(b"%PDF")


# ---------------------------------------------------------------------------
# Dinheiro é Decimal: total exato, sem resíduo de float
# ---------------------------------------------------------------------------
def test_totais_monetarios_exatos(client, cenario):
    login(client, "comprador@teste.com")
    ordem_id = _criar_ordem(client, cenario).get_json()["id"]
    ordem = db.session.get(OrdemCompra, ordem_id)
    item_id = ordem.itens[0].id

    resp = client.post(f"/compras/ordem/{ordem_id}/editar",
                       data={f"valor_unit_{item_id}": "1,10",
                             "frete": "0,10", "desconto": "0,05"})
    assert resp.status_code == 200
    assert resp.get_json()["subtotal"] == pytest.approx(3.30)

    db.session.expire_all()
    ordem = db.session.get(OrdemCompra, ordem_id)
    assert ordem.subtotal() == Decimal("3.30")   # 3 × 1,10 sem erro binário
    assert ordem.total() == Decimal("3.35")


def test_valores_arredondam_para_a_escala_da_coluna(client, cenario):
    """O que vale é o valor que o Postgres grava (escala da coluna).

    Sem quantizar antes das checagens, '0,0004' passa no guard de
    quantidade > 0 mas vira 0.000 no banco, e '999999999,9999' passa no
    teto mas arredonda para 1e9 e estoura Numeric(12,3) — 500 em produção,
    invisível no SQLite dos testes.
    """
    login(client, "solic@teste.com")

    def criar(qtde):
        return client.post("/compras/pedidos/criar", data={
            "obra_nome": "Obra X", "descricao": ["Cimento"],
            "unidade": ["SC"], "quantidade": [qtde]})

    for qtde in ("0,0004", "999999999,9999", "1e50"):
        resp = criar(qtde)
        assert resp.status_code == 400, f"quantidade={qtde!r}"
        assert "erro" in resp.get_json()

    resp = criar("2,5")   # sanidade: valor normal continua passando
    assert resp.status_code == 200
    pedido_id = resp.get_json()["id"]
    item = ItemPedido.query.filter_by(pedido_id=pedido_id).one()
    assert item.quantidade == Decimal("2.500")


def test_pdf_quantidade_grande_sem_notacao_cientifica():
    from compras_pdf import _qtde
    assert _qtde(Decimal("1000000.000")) == "1000000"
    assert _qtde(Decimal("1234567")) == "1234567"
    assert _qtde(Decimal("3.000")) == "3"      # não "3.000" (lê "três mil")
    assert _qtde(Decimal("2.500")) == "2.5"
    assert _qtde(None) == "0"


# ---------------------------------------------------------------------------
# Fronteiras respondem 400 com JSON de erro (nunca 500)
# ---------------------------------------------------------------------------
def test_pedido_com_obra_inexistente_da_400(client, cenario):
    login(client, "solic@teste.com")
    resp = client.post("/compras/pedidos/criar", data={
        "obra_nome": "Obra X", "obra_id": "99999",
        "descricao": ["Cimento"], "unidade": ["SC"], "quantidade": ["2"]})
    assert resp.status_code == 400
    assert "erro" in resp.get_json()


def test_fornecedor_invalido_da_400(client, cenario):
    login(client, "comprador@teste.com")
    for valor in ("abc", "99999", ""):
        resp = client.post(
            f"/compras/pedido/{cenario['pedido'].id}/ordem/criar",
            data={"fornecedor_id": valor})
        assert resp.status_code == 400, f"fornecedor_id={valor!r}"
        assert "erro" in resp.get_json()


def test_segunda_ordem_no_mesmo_pedido_da_400(client, cenario):
    login(client, "comprador@teste.com")
    assert _criar_ordem(client, cenario).status_code == 200
    resp = _criar_ordem(client, cenario)
    assert resp.status_code == 400
    assert OrdemCompra.query.filter_by(
        pedido_id=cenario["pedido"].id).count() == 1
