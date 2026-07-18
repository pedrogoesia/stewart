"""Ferramenta: Compras (spec: specs/fase3-compras.md).

Solicitante registra o pedido de material com itens; o setor (papel
'compras' ou admin) transforma em Ordem de Compra com fornecedor e preços e
baixa o PDF no layout oficial para enviar ao fornecedor/financeiro.
"""

from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from flask import (Blueprint, abort, jsonify, redirect, render_template,
                   request, send_file, url_for)
from flask_login import current_user, login_required

from compras_pdf import gerar_ordem_pdf
from extensions import db
from models import (Fornecedor, ItemOrdem, ItemPedido, Obra, OrdemCompra,
                    PedidoCompra, eh_setor_compras, ordem_do_setor,
                    pedido_do_usuario, registrar_atividade)

bp = Blueprint("compras", __name__)


@bp.before_request
def _exige_acesso():
    """Exige login e que o usuário tenha a ferramenta 'Compras'."""
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login", next=request.url))
    if not current_user.pode_ver_ferramenta("compras"):
        abort(403)


def _ler_data(valor, rotulo):
    valor = (valor or "").strip()
    if not valor:
        return None, None
    try:
        return date.fromisoformat(valor), None
    except ValueError:
        return None, f"{rotulo} inválida: use o formato AAAA-MM-DD."


def _ler_valor(valor, rotulo, casas=2):
    """'' → 0; aceita vírgula decimal ('12,50').

    Decimal, não float: os valores entram em contas de dinheiro e float
    binário acumula erro de arredondamento nos centavos."""
    valor = (valor or "").strip().replace(",", ".")
    if not valor:
        return Decimal("0"), None
    try:
        v = Decimal(valor)
    except InvalidOperation:
        return None, f"{rotulo} inválido: use números (ex.: 12,50)."
    try:
        # Arredondar para a escala da coluna ANTES das checagens: é o valor
        # que o Postgres vai gravar. Sem isso, 999999999,9999 passa no teto
        # e estoura Numeric(12,3) (500), e 0,0004 passa no "quantidade > 0"
        # mas vira 0.000 no banco. quantize também barra 'nan'/'inf' e
        # números com mais dígitos que a precisão do contexto.
        if not v.is_finite():
            raise InvalidOperation
        v = v.quantize(Decimal(1).scaleb(-casas), rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return None, f"{rotulo} inválido: valor grande demais."
    # O teto respeita a precisão da coluna Numeric(12, casas).
    if v >= Decimal("1000000000"):
        return None, f"{rotulo} inválido: valor grande demais."
    if v < 0:
        return None, f"{rotulo} não pode ser negativo."
    return v, None


# ---------------------------------------------------------------------------
# Páginas
# ---------------------------------------------------------------------------
@bp.route("/compras")
@login_required
def index():
    if eh_setor_compras():
        abertos = (PedidoCompra.query.filter_by(status="aberto")
                   .order_by(PedidoCompra.id.desc()).all())
        ordens = (OrdemCompra.query
                  .order_by(OrdemCompra.id.desc()).limit(30).all())
        fornecedores = Fornecedor.query.order_by(Fornecedor.nome).all()
        return render_template("compras.html", setor=True, abertos=abertos,
                               ordens=ordens, fornecedores=fornecedores,
                               obras=Obra.query.order_by(Obra.nome).all())
    meus = (PedidoCompra.query.filter_by(solicitante_id=current_user.id)
            .order_by(PedidoCompra.id.desc()).all())
    return render_template("compras.html", setor=False, meus=meus,
                           obras=Obra.query.order_by(Obra.nome).all())


@bp.route("/compras/pedido/<int:pedido_id>")
@login_required
def pedido_detalhe(pedido_id):
    pedido = pedido_do_usuario(pedido_id)
    fornecedores = Fornecedor.query.order_by(Fornecedor.nome).all()
    return render_template("compras_pedido.html", pedido=pedido,
                           fornecedores=fornecedores,
                           setor=eh_setor_compras())


@bp.route("/compras/ordem/<int:ordem_id>")
@login_required
def ordem_detalhe(ordem_id):
    ordem = ordem_do_setor(ordem_id)
    return render_template("compras_ordem.html", ordem=ordem)


# ---------------------------------------------------------------------------
# Pedidos (solicitante)
# ---------------------------------------------------------------------------
@bp.route("/compras/pedidos/criar", methods=["POST"])
@login_required
def criar_pedido():
    obra_nome = (request.form.get("obra_nome") or "").strip()
    if not obra_nome:
        return jsonify({"erro": "Informe a obra do pedido."}), 400
    data_prevista, erro = _ler_data(request.form.get("data_prevista"),
                                    "Data prevista")
    if erro:
        return jsonify({"erro": erro}), 400

    descricoes = request.form.getlist("descricao")
    unidades = request.form.getlist("unidade")
    quantidades = request.form.getlist("quantidade")
    itens = []
    for i, descricao in enumerate(descricoes):
        descricao = (descricao or "").strip()
        if not descricao:
            return jsonify({"erro": "Todo item precisa de descrição."}), 400
        qtde, erro = _ler_valor(
            quantidades[i] if i < len(quantidades) else "", "Quantidade",
            casas=3)  # escala da coluna ItemPedido.quantidade Numeric(12,3)
        if erro or not qtde:
            return jsonify({"erro": erro or "Quantidade obrigatória."}), 400
        unidade = ((unidades[i] if i < len(unidades) else "") or
                   "UNID").strip().upper()
        itens.append((descricao, unidade, qtde))
    if not itens:
        return jsonify({"erro": "Adicione pelo menos um item."}), 400

    # obra_id é opcional (obra externa fica só no nome), mas se vier tem que
    # existir — id inventado estouraria a FK no Postgres (500, não 400).
    obra_id = None
    valor = (request.form.get("obra_id") or "").strip()
    if valor:
        obra = db.session.get(Obra, int(valor)) if valor.isdigit() else None
        if obra is None:
            return jsonify({"erro": "Obra inválida."}), 400
        obra_id = obra.id
    pedido = PedidoCompra(
        obra_id=obra_id, obra_nome=obra_nome,
        solicitante_id=current_user.id, data_prevista=data_prevista,
        observacoes=(request.form.get("observacoes") or "").strip(),
        criado_em=datetime.now().isoformat())
    db.session.add(pedido)
    db.session.flush()
    for ordem, (descricao, unidade, qtde) in enumerate(itens, start=1):
        db.session.add(ItemPedido(pedido_id=pedido.id, descricao=descricao,
                                  unidade=unidade, quantidade=qtde,
                                  ordem=ordem))
    db.session.commit()
    registrar_atividade("pedido_compra_criado",
                        f"Pedido de material p/ '{obra_nome}' "
                        f"({len(itens)} item(ns))")
    return jsonify({"id": pedido.id})


@bp.route("/compras/pedido/<int:pedido_id>/excluir", methods=["POST"])
@login_required
def excluir_pedido(pedido_id):
    pedido = pedido_do_usuario(pedido_id)
    if pedido.status != "aberto":
        return jsonify({"erro": "Pedido já atendido não pode ser "
                        "excluído."}), 400
    db.session.delete(pedido)
    db.session.commit()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Fornecedores (setor)
# ---------------------------------------------------------------------------
@bp.route("/compras/fornecedores/criar", methods=["POST"])
@login_required
def criar_fornecedor():
    if not eh_setor_compras():
        abort(403)
    nome = (request.form.get("nome") or "").strip()
    if not nome:
        return jsonify({"erro": "Informe o nome do fornecedor."}), 400
    fornecedor = Fornecedor(
        nome=nome, cnpj=(request.form.get("cnpj") or "").strip(),
        telefone=(request.form.get("telefone") or "").strip(),
        email=(request.form.get("email") or "").strip(),
        contato=(request.form.get("contato") or "").strip(),
        criado_em=datetime.now().isoformat())
    db.session.add(fornecedor)
    db.session.commit()
    return jsonify({"id": fornecedor.id, "nome": nome})


# ---------------------------------------------------------------------------
# Ordens de compra (setor)
# ---------------------------------------------------------------------------
@bp.route("/compras/pedido/<int:pedido_id>/ordem/criar", methods=["POST"])
@login_required
def criar_ordem(pedido_id):
    if not eh_setor_compras():
        abort(403)
    pedido = pedido_do_usuario(pedido_id)
    # v1: uma ordem por pedido (spec fase 3) — também evita ordem duplicada
    # por duplo clique. Múltiplas cotações são v2.
    if pedido.status != "aberto":
        return jsonify({"erro": "Este pedido já virou ordem de compra."}), 400
    valor = (request.form.get("fornecedor_id") or "").strip()
    fornecedor = (db.session.get(Fornecedor, int(valor))
                  if valor.isdigit() else None)
    if fornecedor is None:
        return jsonify({"erro": "Escolha um fornecedor."}), 400
    ordem = OrdemCompra(
        pedido_id=pedido.id, fornecedor_id=fornecedor.id, data=date.today(),
        faturamento_razao=(request.form.get("faturamento_razao") or "").strip(),
        faturamento_cnpj_cpf=(request.form.get("faturamento_cnpj_cpf")
                              or "").strip(),
        faturamento_endereco=(request.form.get("faturamento_endereco")
                              or "").strip(),
        faturamento_cep=(request.form.get("faturamento_cep") or "").strip(),
        entrega_endereco=(request.form.get("entrega_endereco") or "").strip(),
        entrega_cep=(request.form.get("entrega_cep") or "").strip(),
        criado_em=datetime.now().isoformat())
    db.session.add(ordem)
    db.session.flush()
    for item in pedido.itens:
        db.session.add(ItemOrdem(
            ordem_compra_id=ordem.id, descricao=item.descricao,
            unidade=item.unidade, quantidade=item.quantidade,
            prazo_entrega=pedido.data_prevista, ordem=item.ordem))
    pedido.status = "atendido"
    db.session.commit()
    registrar_atividade("ordem_compra_criada",
                        f"Ordem {ordem.id:04d} p/ '{fornecedor.nome}' "
                        f"(pedido de '{pedido.obra_nome}')")
    return jsonify({"id": ordem.id})


@bp.route("/compras/ordem/<int:ordem_id>/editar", methods=["POST"])
@login_required
def editar_ordem(ordem_id):
    ordem = ordem_do_setor(ordem_id)
    for item in ordem.itens:
        campo = f"valor_unit_{item.id}"
        if campo in request.form:
            valor, erro = _ler_valor(request.form.get(campo), "Valor unitário")
            if erro:
                return jsonify({"erro": erro}), 400
            item.valor_unit = valor
        campo = f"prazo_{item.id}"
        if campo in request.form:
            prazo, erro = _ler_data(request.form.get(campo), "Prazo")
            if erro:
                return jsonify({"erro": erro}), 400
            item.prazo_entrega = prazo
    for campo, rotulo in (("frete", "Frete"), ("desconto", "Desconto")):
        if campo in request.form:
            valor, erro = _ler_valor(request.form.get(campo), rotulo)
            if erro:
                return jsonify({"erro": erro}), 400
            setattr(ordem, campo, valor)
    for campo in ("cond_pagamento", "obs", "faturamento_razao",
                  "faturamento_cnpj_cpf", "faturamento_endereco",
                  "faturamento_cep", "entrega_endereco", "entrega_cep"):
        if campo in request.form:
            setattr(ordem, campo, (request.form.get(campo) or "").strip())
    db.session.commit()
    # Decimal não é serializável em JSON; float aqui é só para exibição.
    return jsonify({"ok": True, "subtotal": float(ordem.subtotal()),
                    "total": float(ordem.total())})


@bp.route("/compras/ordem/<int:ordem_id>/pdf")
@login_required
def baixar_pdf(ordem_id):
    ordem = ordem_do_setor(ordem_id)
    import io
    pdf = gerar_ordem_pdf(ordem)
    registrar_atividade("ordem_compra_pdf",
                        f"Gerou o PDF da ordem {ordem.id:04d}")
    return send_file(io.BytesIO(pdf), as_attachment=True,
                     download_name=f"Ordem_de_Compra_{ordem.id:04d}.pdf",
                     mimetype="application/pdf")
