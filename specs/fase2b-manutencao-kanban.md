# Spec — Fase 2b: Kanban do setor de Manutenções

> Decisões de 19/07/2026 (Pedro): kanban como o das tarefas, com 3 colunas
> (status novo `em_execucao`), na **visão geral do gestor** (quadro único do
> setor, card mostra o cliente/obra). Sem prioridade por enquanto. A página
> por obra entregue e a "minha semana" do executor continuam como estão.

## Objetivo

A página inicial de Manutenções do **gestor** vira um quadro kanban do setor
inteiro: Agendada / Em execução / Concluída. Arrastar o card muda o status;
arrastar para "Concluída" abre o diálogo de conclusão (descrição do serviço
continua obrigatória — a regra do módulo não afrouxa). Cards mostram
cliente/obra, título, responsável e data (atrasada em vermelho).

## Modelo de dados

- `STATUS_MANUTENCAO = ("agendada", "em_execucao", "concluida")` em
  `models.py` — vocabulário novo; a coluna `status` já é texto livre, **sem
  migração de schema**. Manutenções existentes seguem `agendada`.
- `em_execucao` conta como "não concluída" em tudo que já existe
  (`_agrupar_semana`, contagens): os filtros usam `!= "concluida"`, nada muda.

## Permissões (mesmas do módulo — nada novo a decidir)

- Mudar status (arrastar): gestor ou responsável pela manutenção
  (`manutencao_do_usuario`, como no concluir). O quadro em si só aparece
  para o gestor (página dele); o executor continua na "minha semana".
- Concluir: continua exclusivo de `POST /manutencao/<id>/concluir`, com
  `descricao_realizada` obrigatória.

## Rotas (padrão das existentes: CSRF, JSON, 400/403/404)

- `POST /manutencao/<id>/status` — `{status: agendada|em_execucao}`.
  `concluida` aqui → 400 (concluir tem rota própria com descrição);
  reabrir concluída fica fora do escopo (como hoje, não existe reabrir).
- Rotas existentes não mudam de contrato.

## UI (JS/CSS puros; reusa .kanban do CSS da Fase 1b)

- `templates/manutencao.html` (visão do gestor): a seção da agenda da semana
  dá lugar ao quadro de 3 colunas; a lista de obras entregues continua.
- Card: cliente/obra + título, responsável, data agendada (atrasada em
  vermelho quando não concluída).
- Drag & drop nativo com o mesmo contrato da Fase 1b: o card só fica na
  coluna nova se o servidor confirmar; falha → volta e mostra o erro.
- Soltar em "Concluída" NÃO muda nada de imediato: abre o diálogo de
  conclusão (descrição obrigatória); cancelar → card volta.

## Critérios de aceite (viram testes)

1. `/status`: gestor e responsável movem agendada ↔ em_execucao; valor
   inválido ou `concluida` → 400; quem não é gestor nem responsável → 404;
   sem a ferramenta → 403.
2. Concluir segue exigindo descrição (sem regressão) e continua fechando a
   manutenção a partir de qualquer coluna.
3. Página do gestor renderiza as 3 colunas com os cards do setor inteiro.
4. `em_execucao` aparece na agenda da semana (e no badge de contagens) como
   pendente.
5. Suíte inteira verde.

## Casos de erro

- Drag com falha de rede/validação: card volta para a coluna original e a UI
  mostra o erro (não pode mentir que salvou).
- Concluir sem descrição → 400 com mensagem no diálogo.

## Restrições

- `POST /manutencao/<id>/concluir` intocada; sem migração de schema; sem
  dependência JS nova. Não commitar/publicar sem OK do Pedro.
