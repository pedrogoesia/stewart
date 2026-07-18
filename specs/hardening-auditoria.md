# Hardening pós-auditoria — correções antes do 1º deploy das fases 1–3

> Spec fechada em 18/07/2026, a partir da auditoria do código das fases 1–3
> contra os padrões globais (AGENTS.md / ARCHITECTURE.md / AI_ENGINEERING.md
> do Pedro). Janela ideal: os 5 commits ainda não foram publicados, então
> mudanças de tipo de coluna não exigem migração de dados em produção.

## Objetivo

Eliminar os defeitos que quebrariam em produção (Postgres/uso real) e fechar
lacunas de validação nas fronteiras, sem mudar comportamento de produto além
do listado aqui.

## Critérios de aceite ("pronto quando")

1. **Exclusões íntegras**: excluir um usuário que é responsável de
   manutenção e/ou solicitante de pedido de compra funciona; os vínculos
   (`Manutencao.responsavel_id/criador_id`, `PedidoCompra.solicitante_id`)
   ficam NULL e o histórico é preservado — como os comentários dos modelos
   já prometem. Excluir uma obra referenciada por pedido de compra também
   funciona: `PedidoCompra.obra_id` fica NULL e o pedido sobrevive (o nome
   fica no campo desnormalizado `obra_nome`). Além da limpeza nas rotas,
   as FKs ganham `ondelete="SET NULL"` no schema (vale para bancos novos —
   produção ainda não existe; o SQLite antigo de dev fica coberto pela
   limpeza nas rotas).
2. **FKs fiscalizadas no SQLite** (dev e testes): inserir uma FK inválida
   levanta `IntegrityError`. Bugs dessa classe passam a aparecer nos testes,
   que hoje rodam cegos (SQLite não fiscaliza FK por padrão).
3. **PDF robusto**: ordem com `<`, `>` ou `&` em qualquer texto digitado
   (descrição de item, fornecedor, observações…) gera PDF válido (200,
   bytes `%PDF`).
4. **Dinheiro exato**: `valor_unit`, `frete`, `desconto` viram
   `Numeric(12,2)` e `quantidade` vira `Numeric(12,3)` (Decimal). Subtotal
   de 3 × R$ 1,10 é exatamente `Decimal("3.30")`. JSON de `editar_ordem`
   continua numérico (float só na serialização, para exibição).
5. **Fronteiras validadas com 400 (nunca 500)**:
   - `obra_id` de pedido inexistente → `{"erro": ...}` 400;
   - `fornecedor_id` não numérico ou inexistente → 400;
   - segunda ordem para pedido não-aberto → 400 (spec fase 3: pedido vira
     "atendido" ao gerar a ordem; múltiplas cotações são v2).
6. **Timeout na edição de imagem** (`ai_edit.py`): cliente OpenAI de imagem
   com timeout explícito, como o de texto já tem.
7. **Suíte inteira verde** (83 testes existentes + os novos), sem regressão.

## Casos de erro cobertos

- Usuário excluído com vínculos nas 3 ferramentas novas (item 1).
- Texto com markup em todo campo livre que entra no PDF (item 3).
- Input não numérico/negativo em valores; ids inexistentes (item 5).

## Fora de escopo (backlog)

- Itens "baixos" da auditoria: auditoria em todas as mutações, IP via
  `remote_addr` do ProxyFix, arquivos órfãos de upload, N+1 nas listagens,
  CHECK constraints de status.
- Pergunta de produto em aberto (não decidir aqui): o solicitante pode abrir
  pedido para **qualquer** obra do cadastro (comportamento atual do form) ou
  só para obras das quais participa? v1 mantém o atual + validação de
  existência.

## Restrições

- Não mudar API/rotas existentes nem o layout do PDF.
- Não commitar/publicar sem OK do Pedro (push na main = deploy).
