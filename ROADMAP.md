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

## Fase 0 — Fundação contínua (em andamento)

**Objetivo:** confiança para crescer sem quebrar o que existe.

- Cobertura de testes das áreas existentes (isolamento ✅, ferramentas/admin,
  fluxo upload→relatório, atas)
- CI: rodar `pytest` automaticamente a cada push (GitHub Actions)
- Estratégia de migração de banco: hoje `init_db()`/`_migrar_colunas()` é
  manual — avaliar Alembic quando os modelos das fases 1–3 chegarem

## Fase 1 — Agenda e tarefas por obra

**Objetivo:** engenheiro, encarregado e estagiário abrem a plataforma e veem
a agenda e as tarefas **da sua obra** (o que fazer, prazos, status).

**Spec fechada em 17/07/2026 → `specs/fase1-agenda-tarefas.md`.**
Decisões: engenheiro + admin criam/atribuem tarefas; papéis
(engenheiro/encarregado/estagiário) com vínculo usuário↔obra; v1 é tarefas
com prazo + visão "minha semana"; notificação só na plataforma (badge).

## Fase 2 — Setor de Manutenção

**Objetivo:** registro das obras já entregues (clientes antigos) e do
histórico de manutenções feitas em cada uma; encarregado de manutenção tem
login próprio e vê o que precisa fazer na semana.

**Esboço:** cadastro de obra entregue/cliente, registro de manutenção
(data, o que foi feito, fotos?), agenda semanal do encarregado.

**Perguntas abertas:**
- Obra entregue reaproveita o modelo `Obra` atual ou é entidade separada
  (cliente, endereço, data de entrega, garantia)?
- Quem agenda as manutenções da semana — o setor ou o encarregado?
- Manutenção tem foto/relatório como as obras?

## Fase 3 — Setor de Compras

**Objetivo:** eliminar o PDF manual. Fluxo hoje: engenheiros mandam pedido
por email → comprador monta PDF à mão → envia a 1+ fornecedores → preenche
o PDF com o melhor preço e os dados do comprador → manda por email ao
financeiro.

**Esboço:** entrada de pedidos (formulário na plataforma e/ou leitura dos
emails), geração automática do PDF de cotação, registro das respostas dos
fornecedores, comparativo de preços, PDF final + envio por email ao
financeiro.

**Perguntas abertas:**
- Os engenheiros passam a pedir *pela plataforma* (mais simples e estruturado)
  ou o sistema precisa ler a caixa de email existente (integração IMAP/Gmail)?
- Anexar um exemplo do PDF atual (modelo a reproduzir) e dos emails típicos.
- Existe etapa de aprovação (alçada de valor) antes de mandar ao financeiro?
- Envio de email pela plataforma exige serviço SMTP/API (ex.: Resend, SES) —
  definir remetente e domínio.

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
