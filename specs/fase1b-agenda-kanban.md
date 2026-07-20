# Spec — Fase 1b: Agenda de Tarefas turbinada (kanban, prioridade, checklist)

> Decisões de 18/07/2026: Pedro achou a v1 simples demais e delegou as
> escolhas. Escolhido: kanban por status na página da obra + prioridade +
> checklist nas tarefas. Comentários, fotos, recorrência e notificações por
> email ficam para uma fase futura.

## Objetivo

A página de tarefas da obra vira um quadro kanban (Pendente / Em andamento /
Concluída): arrastar o card muda o status. As tarefas ganham **prioridade**
(alta/média/baixa, com destaque visual e ordenação) e **checklist** de
subtarefas com progresso visível no card. A "minha semana" (`/tarefas`)
continua como lista por prazo, agora mostrando prioridade e progresso.

## Modelo de dados

- `Tarefa.prioridade` — string `alta | media | baixa`, default `media`
  (coluna nova em tabela existente → entra em `_migrar_colunas`).
- `ItemChecklist` (`tarefa_checklist`): `id, tarefa_id (FK CASCADE, index),
  texto, feito (bool, default False), ordem (int)`. Tabela nova →
  `create_all` cria; excluir a tarefa leva o checklist junto (cascade,
  padrão dos filhos de Tarefa).

## Permissões (mesmas regras da Fase 1 — nada novo a decidir)

- Arrastar card = `POST /tarefa/<id>/status` existente: engenheiro/admin em
  qualquer card da obra; encarregado/estagiário só nos cards atribuídos a
  eles (cards dos outros não são arrastáveis na UI e a rota já barra).
- Prioridade e itens do checklist (criar/editar/excluir texto): quem pode
  editar a tarefa (engenheiro da obra/admin).
- Marcar/desmarcar item feito: mesma regra do status (responsável também
  pode) — é o "andamento fino" da tarefa.

## Rotas novas (padrão das existentes: CSRF, JSON, 400/403/404)

- `POST /tarefa/<id>/checklist/criar` — `{texto}` → `{id}`.
- `POST /checklist/<id>/editar` — `{texto}`.
- `POST /checklist/<id>/feito` — `{feito: true|false}`.
- `POST /checklist/<id>/excluir`.
- `criar_tarefa`/`editar_tarefa` passam a aceitar `prioridade` (valor fora
  de alta|media|baixa → 400).

## UI (JS/CSS puros, sem framework — padrão do projeto)

- `templates/obra_tarefas.html`: 3 colunas; card mostra título, responsável,
  prazo (atrasado em vermelho), bolinha de prioridade e progresso do
  checklist ("2/5"). Drag & drop nativo (HTML5) com fallback: select de
  status no card continua existindo (funciona no celular, onde drag é ruim).
- Detalhe/edição da tarefa (expandir card): checklist marcável, prioridade.
- `templates/tarefas.html` (minha semana): prioridade + progresso; dentro de
  cada grupo de prazo, ordenar por prioridade (alta primeiro).

## Critérios de aceite (viram testes)

1. Prioridade: criar/editar com valor válido persiste; inválido → 400;
   default `media`; "minha semana" ordena alta→baixa dentro do grupo.
2. Checklist: engenheiro da obra cria/edita/exclui itens; encarregado
   responsável marca/desmarca feito mas não cria/edita/exclui (403);
   quem não é responsável nem gestor não marca (403/404).
3. Isolamento (padrão `test_isolamento.py`): usuário de outra obra não vê
   nem altera checklist/prioridade (404, banco intocado) — obrigatório por
   ser modelo novo.
4. Excluir tarefa remove os itens do checklist (sem órfãos — FK fiscalizada
   pega regressão).
5. `init_db()` em banco existente ganha a coluna e a tabela novas sem
   perder dados.
6. Suíte inteira verde (93 atuais + os novos).

## Casos de erro

- `texto` vazio no checklist → 400; `feito` não-booleano → 400.
- Drag & drop com falha de rede: card volta pra coluna original e mostra o
  erro (a UI não pode mentir que salvou).

## Restrições

- Rotas existentes não mudam de contrato (o select de status continua).
- Sem dependência JS nova; sem migração destrutiva.
- Não commitar/publicar sem OK do Pedro.
