# Stewart — Guia para assistentes de IA

> Documento autossuficiente para qualquer IA de código trabalhar neste
> projeto. Leia inteiro antes de alterar qualquer coisa. Última revisão:
> 17/07/2026.

## O que é

Plataforma web da **Stewart Engenharia** (construtora, RJ/GO) com ferramentas
para as obras e os setores internos. Cada ferramenta é um blueprint Flask com
permissão própria:

| Ferramenta | O que faz | Quem gerencia |
|---|---|---|
| Relatório de Obras | Fotos por cômodo → relatório .pptx mensal + .zip; edição de foto por IA | Dono da obra |
| Assistente de Atas | Ata de reunião .docx no navegador; preenchimento por IA (OpenAI) | Qualquer usuário com a ferramenta |
| Agenda de Tarefas | Tarefas por obra com prazo/status; visão "minha semana" + badge | Admin, dono da obra ou engenheiro membro |
| Manutenções | Obras entregues (clientes antigos), agenda do setor, conclusão com fotos | Admin ou papel `manutencao` |
| Compras | Pedido de material → ordem de compra → PDF no layout oficial | Admin ou papel `compras` |

## Stack e como rodar

- Python 3.11 + Flask 3 (Flask-SQLAlchemy, Flask-Login, Flask-WTF/CSRF,
  Flask-Limiter), Jinja + CSS/JS puro (sem framework de frontend)
- Banco: SQLite local (`data/stewart.db`) / PostgreSQL Neon em produção —
  mesmo código; geração de arquivos: python-pptx, reportlab
- IA (opcional, `OPENAI_API_KEY` no `.env`): `gpt-image-1` (fotos) e
  `gpt-5.4-mini` (atas) — defaults em `ai_edit.py`

```bash
./run.sh                               # sobe em http://localhost:5000
./.venv/bin/python -m pytest tests/    # RODE ANTES DE QUALQUER COMMIT
# o .venv não tem pip; instalar pacotes: uv pip install -r requirements-dev.txt
```

## Estrutura

```
app.py               # create_app(), init_db() (cria tabelas + migrações leves)
config.py            # caminhos (DATA_DIR), constantes, database_url()
models.py            # TODOS os modelos + helpers de acesso (fonte da verdade)
extensions.py        # instâncias das extensões Flask
blueprints/          # auth, relatorios, atas, tarefas, manutencao, compras
pptx_generator.py    # .pptx do template oficial | compras_pdf.py  # PDF da ordem
ai_edit.py           # integração OpenAI | utils.py  # imagens, slugify, paths
templates/ static/   # telas | tests/  # 91 testes | specs/  # specs por fase
```

## REGRAS INEGOCIÁVEIS (não regredir)

1. **Isolamento por dono/papel**: toda query filtra pelo usuário logado e
   toda rota confere posse/permissão via helpers de `models.py`
   (`obra_do_usuario`, `tarefa_do_membro`, `manutencao_do_usuario`,
   `pedido_do_usuario`, …). Recurso alheio responde **404** (não vaza
   existência); ação sem permissão de gestão responde **403**. Até a entrega
   de imagens (`/uploads/...`, `/manutencao/foto/<id>`) checa o dono.
2. **Todo modelo novo entra com testes de isolamento** no padrão de
   `tests/test_isolamento.py` (usuário A nunca lê/altera recurso do B, e a
   tentativa não deixa rastro no banco).
3. **CSRF em toda escrita** (Flask-WTF; fetch envia header `X-CSRFToken`),
   rate limit no login e nas rotas de IA, senhas com hash (mín. 8 chars).
4. **Migrações**: `create_all()` NÃO altera tabela existente. Coluna nova em
   tabela existente exige ALTER em `_migrar_colunas()` (app.py). Nada de
   perder dados.
5. **Uploads sempre dentro de `DATA_DIR`** (em produção é disco persistente
   `/var/data`); imagens passam por `utils.processar_imagem` (EXIF, resize
   2000px, JPEG). Alta resolução nunca é recusada — é reduzida.
6. **Totais são calculados, nunca digitados** (ex.: `OrdemCompra.subtotal/total`).
7. Relatório de obras é sempre **.pptx** (nunca PDF) — decisão de produto.

## Papéis e permissões

- `is_admin` manda em tudo. Papéis opcionais (`Usuario.papel`): `engenheiro`,
  `encarregado`, `estagiario`, `manutencao` (setor), `compras` (setor).
- Vínculo usuário↔obra: tabela `obra_membros` (Agenda de Tarefas).
- Permissão por ferramenta: `Usuario.ferramentas` (slugs CSV) +
  `pode_ver_ferramenta(slug)`; todo blueprint tem `before_request` exigindo
  login + ferramenta. Catálogo: `FERRAMENTAS` em models.py.

## Convenções

- **Tudo em pt-BR**: código, comentários, commits, UI (seguir o estilo do
  `git log`). Comentários explicam o *porquê*, não o óbvio.
- Padrão de rota nova: helper de acesso primeiro (404/403), validação barata
  com JSON `{"erro": "..."}` e status 400, depois efeito + `registrar_atividade`.
- Frontend: forms simples ou `fetch` + `FormData` + `X-CSRFToken` +
  `location.reload()`. Modais com `<dialog class="modal">`. Reaproveitar as
  classes CSS existentes (`.tarefa-item`, `.cards`, `.panel`, `.tabela`).

## Método de trabalho (obrigatório)

1. **Spec antes de código**: objetivo, critérios de aceite ("pronto quando
   X, Y, Z"), casos de erro, fora de escopo — em `specs/`. Não invente
   requisitos: se faltar decisão de produto, PERGUNTE.
2. **Testes primeiro**: os critérios viram testes que nascem falhando.
3. Implementar até a suíte inteira passar (`pytest tests/`), sem quebrar os
   existentes.
4. **Evidência real**: além dos testes, exercite o fluxo (servidor local,
   PDF/PPTX gerado de verdade). "Compila" não é evidência.
5. Commits pequenos em pt-BR, um assunto por commit. NÃO faça push sem o
   Pedro autorizar: **push na `main` = deploy automático no Render**.

## Deploy (Render)

`render.yaml` (Blueprint): branch `main`, auto-deploy; banco Neon via
`DATABASE_URL`; fotos em `DATA_DIR=/var/data`; `startCommand` roda
`app.init_db()` antes do gunicorn; `SECRET_KEY` obrigatória em produção.
CI: GitHub Actions roda a suíte a cada push (`.github/workflows/tests.yml`).

## Estado e próximos passos (v2)

Fases 0–3 do `ROADMAP.md` implementadas em 17/07/2026; hardening
pós-auditoria em 18/07/2026 (`specs/hardening-auditoria.md`; 91 testes
verdes — FKs fiscalizadas também no SQLite, dinheiro em Decimal).
Backlog v2: comparativo automático de cotações entre fornecedores; leitura
do orçamento do fornecedor (PDF) com IA; envio de email pela plataforma
(SMTP — definir domínio/remetente); alçada de aprovação por valor em
compras; calendário com horários e notificações na Agenda de Tarefas;
alertas de fim de garantia em Manutenções; Alembic quando as migrações
manuais pesarem.
