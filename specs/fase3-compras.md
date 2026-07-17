# Spec — Fase 3: Setor de Compras (RASCUNHO — aguardando insumos)

> Decisão de produto (17/07/2026): os pedidos entram **pela plataforma**
> (formulário estruturado), não por leitura de email. Elimina o email de
> entrada e torna o PDF de cotação automático.

## Objetivo

Eliminar o PDF manual do setor de compras. Fluxo alvo:

1. Engenheiro abre um **pedido de compra** na plataforma (obra, itens com
   material/quantidade/unidade, observações).
2. O setor de compras vê a fila de pedidos, agrupa itens e gera o **PDF de
   cotação** automaticamente para enviar aos fornecedores.
3. As respostas dos fornecedores são registradas (preço por item, prazo,
   condições) e o sistema monta o **comparativo de preços**.
4. Com o vencedor escolhido, o sistema gera o **PDF final** (melhor preço +
   dados do comprador) para envio ao financeiro.

## Insumos pendentes (bloqueiam a spec final — pedir ao usuário)

- [ ] **Exemplo do PDF atual** feito à mão (modelo a reproduzir: campos,
      logo, assinaturas).
- [ ] Exemplo de **email de pedido típico** de um engenheiro (para conferir
      se o formulário cobre os campos reais).
- [ ] Lista de **dados do comprador** que entram no PDF final.
- [ ] Envio de email pela plataforma (cotação → fornecedores; PDF final →
      financeiro): v1 pode ser **baixar o PDF e enviar manualmente**?
      Automatizar exige serviço SMTP/API (Resend, SES…) e domínio próprio.
- [ ] Existe alçada/aprovação por valor antes de ir ao financeiro?

## Esboço técnico (a confirmar após os insumos)

- Papel novo `compras` ("Setor de Compras") + ferramenta `compras`.
- Modelos: `PedidoCompra` (obra, solicitante, status: aberto → em cotação →
  fechado), `ItemPedido` (material, quantidade, unidade), `Fornecedor`
  (nome, email, telefone), `Cotacao` (fornecedor, preços por item, prazo).
- Geração de PDF no servidor (avaliar `reportlab` — dependência nova).
- Permissões no padrão das demais ferramentas: engenheiro cria pedido e
  acompanha os seus; setor de compras gerencia tudo; 404 para quem não deve
  ver, testes de isolamento desde o primeiro commit.

## Critérios de aceite (rascunho)

1. Engenheiro cria pedido com itens; vê só os pedidos dele.
2. Setor de compras vê a fila, gera PDF de cotação de 1+ pedidos.
3. Registro de cotações por fornecedor e comparativo com menor preço por item.
4. PDF final gerado com o vencedor e os dados do comprador.
5. Isolamento: engenheiro não vê pedido de outro; sem a ferramenta, 403.
6. Suíte inteira verde.
