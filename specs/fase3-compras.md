# Spec — Fase 3: Setor de Compras (v1)

> Decisões (17/07/2026): pedidos entram **pela plataforma**; a Ordem de
> Compra sai em **PDF para baixar e enviar manualmente** (sem SMTP no v1).
> Insumos recebidos: planilha real "Ordem de compra 196 - Cruzada", email de
> pedido típico (Gestão de Obras) e orçamento de fornecedor (STAN Elétrica).

## Objetivo

Substituir a planilha manual: o solicitante (engenheiro/gestão de obras)
registra o pedido de material na plataforma; o setor de compras transforma o
pedido em Ordem de Compra com fornecedor e preços e baixa o **PDF no layout
oficial** para enviar ao fornecedor/financeiro.

## Papéis e acesso

- Novo papel `compras` ("Setor de Compras") + ferramenta `compras`.
- **Solicitante** (qualquer usuário com a ferramenta): cria pedidos com
  itens; vê e acompanha **apenas os próprios** pedidos.
- **Setor** (papel `compras` ou admin): vê a fila de todos os pedidos,
  cadastra fornecedores, cria/edita ordens de compra e gera o PDF.
- Sem a ferramenta → 403. Pedido de outro solicitante → 404.

## Modelo de dados (tabelas novas, só `create_all`)

- `Fornecedor`: `nome, cnpj, telefone, email, contato, criado_em`.
- `PedidoCompra`: `obra_id (FK obras, opcional), obra_nome, solicitante_id,
  data_prevista, observacoes, status (aberto | atendido), criado_em`.
- `ItemPedido`: `pedido_id, descricao, unidade, quantidade, ordem`.
- `OrdemCompra`: `numero (= id), pedido_id, fornecedor_id, data,
  faturamento_razao, faturamento_cnpj_cpf, faturamento_endereco,
  faturamento_cep, entrega_endereco, entrega_cep, frete, desconto,
  cond_pagamento, obs, criado_em` — itens copiados do pedido em `ItemOrdem`
  (`descricao, unidade, quantidade, valor_unit, prazo_entrega, ordem`).
- Totais calculados (nunca digitados): subtotal = Σ quant×valor_unit;
  total = subtotal + frete − desconto.

## PDF da Ordem de Compra (layout da planilha real)

Cabeçalho "Ordem de compra - NNNN" · bloco do fornecedor (razão, CNPJ,
telefone/email, contato) · Dados para faturamento × Dados de entrega ·
linha nº/data/obra/solicitante · tabela de itens (Item, Descrição, unid,
Quant, Valor unit., Valor total, Prazo de entrega) · SUB TOTAL/FRETE/
DESCONTO/TOTAL · OBS e COND. DE PAG. · rodapé fixo do financeiro
(NF/boleto → financeiro@stewartengenharia.com.br, cópia ao comprador,
endereço de cobrança da Stewart). Gerado com `reportlab`.

## Critérios de aceite (viram testes)

1. Solicitante cria pedido com itens (descrição/unidade/quantidade); pedido
   sem itens ou com item sem descrição → 400.
2. Solicitante vê só os seus pedidos; pedido de outro → 404; setor vê todos.
3. Só o setor cadastra fornecedor (403 p/ solicitante); nome obrigatório.
4. Setor cria ordem a partir de um pedido (itens copiados; pedido vira
   "atendido"); solicitante tentando → 403.
5. Setor edita preços/frete/desconto/condições; totais calculados certos.
6. PDF da ordem: 200, arquivo PDF válido, só para o setor.
7. Sem a ferramenta `compras` → 403 em tudo. Suíte inteira verde.

## Fora de escopo (v1 → v2)

Comparativo automático de cotações entre fornecedores; leitura do orçamento
do fornecedor (PDF) com IA; envio de email pela plataforma (SMTP); alçada de
aprovação por valor.
