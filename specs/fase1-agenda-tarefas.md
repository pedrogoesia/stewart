# Spec — Fase 1: Agenda e Tarefas por Obra

> Decisões de produto tomadas em 17/07/2026: engenheiro + admin criam tarefas;
> papéis com vínculo por obra; v1 = tarefas com prazo + "minha semana";
> notificação só dentro da plataforma.

## Objetivo

Engenheiro, encarregado e estagiário abrem a plataforma e veem as tarefas da
sua obra: o que fazer, de quem é, prazo e status. Cada pessoa tem a visão
"minha semana" com as suas tarefas (atrasadas em destaque).

## Papéis e acesso

- Novo campo `Usuario.papel`: `engenheiro` | `encarregado` | `estagiario`
  (opcional; contas atuais ficam sem papel e nada muda para elas).
  `is_admin` continua existindo e manda em tudo.
- Novo vínculo usuário↔obra (tabela `obra_membros`, N:N): a pessoa só vê as
  obras às quais foi vinculada. Admin vincula pessoas às obras.
- **Permissões nas tarefas:**
  - Engenheiro (vinculado à obra) e admin: criam, editam, atribuem e excluem
    tarefas da obra.
  - Encarregado e estagiário: veem todas as tarefas das suas obras, mas só
    alteram o **status** das tarefas atribuídas a eles.
- A ferramenta entra no catálogo `FERRAMENTAS` como `"tarefas"` (permissão
  por ferramenta, como as demais).
- **Não muda nada nos Relatórios/Atas**: o dono da obra nos relatórios segue
  sendo `Obra.usuario_id`. Compartilhar relatórios com a equipe fica fora
  desta fase.

## Modelo de dados

- `Usuario.papel` — string opcional (migração em `_migrar_colunas`).
- `obra_membros(usuario_id, obra_id)` — tabela de associação (criada por
  `create_all`, sem migração de dados).
- `Tarefa`: `id, obra_id, titulo, descricao, responsavel_id, criador_id,
  prazo (date), status (pendente | em_andamento | concluida), criado_em,
  concluida_em`.

## Telas e rotas

- `/tarefas` — **Minha semana**: tarefas atribuídas a mim, em grupos
  *Atrasadas* / *Esta semana* / *Próximas*, ordenadas por prazo. Badge no
  menu com a contagem de atrasadas + desta semana.
- `/obra/<id>/tarefas` — tarefas da obra (membros veem; engenheiro/admin
  gerenciam). POSTs no padrão das rotas existentes (CSRF, JSON).

## Critérios de aceite (viram testes)

1. Engenheiro vinculado cria/edita/atribui/exclui tarefa na sua obra; em obra
   **não** vinculada recebe 404 e nada muda no banco (padrão
   `test_isolamento.py`).
2. Encarregado/estagiário não cria/edita/exclui (403), mas muda o status de
   tarefa atribuída a ele.
3. Ninguém muda status de tarefa atribuída a outra pessoa (404/403).
4. Usuário sem vínculo com a obra não vê nem altera nada dela.
5. "Minha semana" traz só as tarefas do usuário logado, agrupadas e ordenadas
   por prazo.
6. `init_db()` em banco existente cria as estruturas novas sem perder dados.
7. Suíte inteira verde (36 testes atuais + os novos).

## Casos de erro

- Título vazio → 400. Prazo inválido → 400. Status desconhecido → 400.
- Responsável que não é membro da obra → 400.

## Fora de escopo (v1)

Calendário com horários; notificações por email/WhatsApp; comentários e
anexos em tarefas; equipe ver relatórios fotográficos da obra.
