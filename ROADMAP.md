# Roadmap — Plataforma Stewart

> Documento de goal do produto. Cada fase segue o ciclo spec-driven:
> **spec (com critérios de aceite) → plano aprovado → implementação → testes
> (isolamento incluso para todo modelo novo) → deploy**. Antes de iniciar uma
> fase, responder as "perguntas abertas" dela — elas viram a spec.

## Visão

Plataforma única de soluções da Stewart Engenharia: ferramentas de IA e de
gestão para quem está nas obras (engenheiros, encarregados, estagiários) e
para os setores internos (manutenção, compras). Cada ferramenta é um
blueprint com permissão própria (modelo `FERRAMENTAS` em models.py).

## Estado atual (base pronta)

- ✅ Relatórios fotográficos de obras (.pptx + .zip, edição de foto por IA)
- ✅ Assistente de Atas (.docx no navegador, preenchimento por IA)
- ✅ Usuários com permissão por ferramenta, auditoria de atividades
- ✅ Testes de isolamento por usuário (`tests/`)

---

## Fase 0 — Fundação contínua ✅ (17/07/2026)

- ✅ Cobertura de testes das áreas existentes (isolamento, ferramentas/admin,
  fluxo upload→relatório, atas, tarefas, manutenções)
- ✅ CI: `.github/workflows/tests.yml` roda a suíte a cada push/PR
- Pendente contínuo: avaliar Alembic quando as migrações manuais
  (`_migrar_colunas`) ficarem pesadas

## Fase 1 — Agenda e tarefas por obra

**Objetivo:** engenheiro, encarregado e estagiário abrem a plataforma e veem
a agenda e as tarefas **da sua obra** (o que fazer, prazos, status).

**Spec fechada em 17/07/2026 → `specs/fase1-agenda-tarefas.md`.**
Decisões: engenheiro + admin criam/atribuem tarefas; papéis
(engenheiro/encarregado/estagiário) com vínculo usuário↔obra; v1 é tarefas
com prazo + visão "minha semana"; notificação só na plataforma (badge).

## Fase 2 — Setor de Manutenção ✅ (17/07/2026)

**Spec: `specs/fase2-manutencao.md`.** Decisões: obra entregue é entidade
própria; setor agenda / encarregado executa; conclusão com descrição + fotos.
Implementada: papel `manutencao`, ferramenta `manutencao`,
`blueprints/manutencao.py`, testes em `tests/test_manutencao.py`.

## Fase 3 — Setor de Compras

**Objetivo:** eliminar o PDF manual. Fluxo hoje: engenheiros mandam pedido
por email → comprador monta PDF à mão → envia a 1+ fornecedores → preenche
o PDF com o melhor preço e os dados do comprador → manda por email ao
financeiro.

**Esboço:** entrada de pedidos (formulário na plataforma e/ou leitura dos
emails), geração automática do PDF de cotação, registro das respostas dos
fornecedores, comparativo de preços, PDF final + envio por email ao
financeiro.

**Decisão tomada (17/07/2026):** pedidos entram *pela plataforma* (formulário
estruturado). Spec rascunhada em `specs/fase3-compras.md` — implementação
**bloqueada nos insumos**: exemplo do PDF atual, email de pedido típico,
dados do comprador e decisão sobre envio automático de email (v1 pode ser
baixar o PDF e enviar manualmente).

---

## Atenções técnicas transversais

- **Papéis e vínculo usuário↔obra** (fases 1 e 2) são a mudança estrutural
  mais importante — desenhar uma vez, usar em tudo.
- **Todo modelo novo entra com testes de isolamento** no padrão de
  `tests/test_isolamento.py`.
- **Migrações**: `create_all()` não altera tabelas existentes; toda coluna
  nova em tabela existente precisa de migração em `_migrar_colunas()` (ou
  Alembic, quando adotado).
- **Emails** (fases 2 e 3): centralizar num módulo único de envio.
