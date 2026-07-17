"""Gera o PDF da Ordem de Compra no layout da planilha oficial do setor.

Referência: "196 - CRUZADA - ORDEM DE COMPRA" (planilha feita à mão até
17/07/2026). O rodapé do financeiro é fixo e obrigatório em toda ordem.
"""

import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

# Dados fixos da Stewart no rodapé (cobrança/NF). Se mudarem, atualizar aqui.
EMAIL_FINANCEIRO = "financeiro@stewartengenharia.com.br"
EMAIL_COPIA = "julio.rodrigues@stewartengenharia.com.br"
COBRANCA = ("Razão Social: STEWART ENGENHARIA E PARTICIPAÇÕES LTDA — "
            "CNPJ: 00.578.341/0001-49<br/>"
            "Endereço: Avenida das Américas 3939, bloco 01 Cobertura 301 — "
            "Cep: 22631-003")

_base = ParagraphStyle("base", fontName="Helvetica", fontSize=9, leading=12)
_negrito = ParagraphStyle("negrito", parent=_base, fontName="Helvetica-Bold")
_titulo = ParagraphStyle("titulo", parent=_negrito, fontSize=14, leading=18)
_mini = ParagraphStyle("mini", parent=_base, fontSize=8, leading=10)


def moeda(valor):
    """1234.5 → '1.234,50' (formato brasileiro)."""
    inteiro, decimal = f"{valor or 0:,.2f}".split(".")
    return inteiro.replace(",", ".") + "," + decimal


def _data(d):
    return d.strftime("%d/%m/%Y") if d else ""


def gerar_ordem_pdf(ordem):
    """Monta o PDF e devolve os bytes."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm,
        topMargin=14 * mm, bottomMargin=14 * mm,
        title=f"Ordem de compra {ordem.id:04d}")
    f = ordem.fornecedor
    pedido = ordem.pedido
    corpo = [
        Paragraph(f"Ordem de compra - {ordem.id:04d}", _titulo),
        Spacer(1, 4 * mm),
        Paragraph(f"<b>Fornecedor:</b> {f.nome}", _base),
        Paragraph(f"<b>Cnpj:</b> {f.cnpj}", _base),
        Paragraph(f"<b>Telefone:</b> {f.telefone} | <b>E-mail:</b> {f.email}",
                  _base),
        Paragraph(f"<b>Contato:</b> {f.contato}", _base),
        Spacer(1, 4 * mm),
    ]

    faturamento = Paragraph(
        "<b>Dados para faturamento:</b><br/>"
        f"Razão Social: {ordem.faturamento_razao}<br/>"
        f"CNPJ/CPF: {ordem.faturamento_cnpj_cpf}<br/>"
        f"Endereço: {ordem.faturamento_endereco}<br/>"
        f"Cep: {ordem.faturamento_cep}", _base)
    entrega = Paragraph(
        "<b>Dados de entrega:</b><br/>"
        f"Endereço: {ordem.entrega_endereco}<br/>"
        f"Cep: {ordem.entrega_cep}", _base)
    bloco = Table([[faturamento, entrega]], colWidths=[90 * mm, 90 * mm])
    bloco.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    corpo += [bloco, Spacer(1, 4 * mm)]

    solicitante = (pedido.solicitante.nome or pedido.solicitante.email
                   if pedido.solicitante else "")
    corpo += [Paragraph(
        f"<b>N° {ordem.id:04d}</b> &nbsp;&nbsp; Data: {_data(ordem.data)} "
        f"&nbsp;&nbsp; Obra: {pedido.obra_nome} "
        f"&nbsp;&nbsp; Solicitante: {solicitante}", _base),
        Spacer(1, 2 * mm)]

    linhas = [["Item", "Descrição dos insumos", "unid", "Quant",
               "Valor unit.", "Valor total", "Prazo de entrega"]]
    for n, item in enumerate(ordem.itens, start=1):
        linhas.append([
            str(n), Paragraph(item.descricao, _mini), item.unidade,
            f"{item.quantidade:g}", moeda(item.valor_unit),
            moeda(item.quantidade * (item.valor_unit or 0)),
            _data(item.prazo_entrega)])
    tabela = Table(linhas, colWidths=[10 * mm, 72 * mm, 12 * mm, 14 * mm,
                                      22 * mm, 22 * mm, 28 * mm],
                   repeatRows=1)
    tabela.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8),
        ("FONT", (0, 1), (-1, -1), "Helvetica", 8),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8e8e8")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#999999")),
        ("ALIGN", (2, 0), (-1, -1), "CENTER"),
        ("ALIGN", (4, 1), (5, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    corpo += [tabela]

    totais = Table([
        ["SUB TOTAL (R$)", moeda(ordem.subtotal())],
        ["FRETE (R$)", moeda(ordem.frete)],
        ["DESCONTO (R$)", moeda(ordem.desconto)],
        ["TOTAL (R$)", moeda(ordem.total())],
    ], colWidths=[136 * mm, 44 * mm])
    totais.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), "Helvetica-Bold", 8),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#999999")),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#e8e8e8")),
    ]))
    corpo += [totais, Spacer(1, 4 * mm)]

    obs = Table([[Paragraph(f"<b>OBS:</b> {ordem.obs}", _base),
                  Paragraph(f"<b>COND. DE PAG.</b><br/>{ordem.cond_pagamento}",
                            _base)]], colWidths=[110 * mm, 70 * mm])
    obs.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    corpo += [obs, Spacer(1, 6 * mm)]

    corpo += [
        Paragraph("É imprescindível que as notas fiscais eletrônicas e os "
                  "boletos sejam enviados para o e-mail do setor financeiro:",
                  _mini),
        Paragraph(f"<b>{EMAIL_FINANCEIRO}</b>", _mini),
        Paragraph(f"Com cópia para: <b>{EMAIL_COPIA}</b>", _mini),
        Spacer(1, 2 * mm),
        Paragraph("Endereço para envios de cobranças:", _mini),
        Paragraph(COBRANCA, _mini),
    ]

    doc.build(corpo)
    return buf.getvalue()
