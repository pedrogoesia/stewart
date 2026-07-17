# Stewart — Relatórios Fotográficos de Obras

Sistema web (Flask) da Stewart Construtora: equipe em campo sobe fotos das obras
organizadas por cômodo, escreve legendas e gera o relatório mensal em PowerPoint
(modelo oficial) ou baixa as fotos em .zip. Tem também atas de reunião (.docx)
com preenchimento por IA e edição de fotos por IA.

## Stack

- Python 3.11 + Flask 3 (Flask-SQLAlchemy, Flask-Login, Flask-WTF/CSRF, Flask-Limiter)
- Banco: SQLite local (`data/stewart.db`) / PostgreSQL em produção (Neon) — mesmo código
- Frontend: templates Jinja (`templates/`) + CSS/JS puro em `static/` (sem framework)
- Geração de arquivos: python-pptx (relatórios), python-docx (atas)
- IA (opcional, precisa de `OPENAI_API_KEY`): edição de fotos (`gpt-image-1`) e
  texto das atas (`gpt-5.4-mini`) — defaults em `ai_edit.py`, configuráveis via
  `OPENAI_IMAGE_MODEL` / `OPENAI_TEXT_MODEL`

## Como rodar / verificar

```bash
./run.sh                 # cria .venv, instala deps e sobe em http://localhost:5000
# ou manualmente:
source .venv/bin/activate && python app.py
```

- Primeiro acesso: `admin@stewart.local` / senha do `ADMIN_SENHA` no `.env` (default `admin`)

### Testes

```bash
./.venv/bin/python -m pytest tests/    # o venv não tem pip; instalar deps com: uv pip install -r requirements-dev.txt
```

- `tests/test_isolamento.py` — isolamento por usuário (a garantia de segurança
  mais crítica) — **rodar sempre antes de commit que toque em rotas/consultas;
  se falhar, não publicar.**
- `tests/test_ferramentas_admin.py` — permissão por ferramenta (403) e rotas /admin/*.
- `tests/test_fluxo_relatorio.py` — fluxo completo: upload real (resize p/ 2000px),
  legenda, .pptx e .zip.
- O `tests/conftest.py` aponta `DATA_DIR` para pasta temporária antes de
  importar o app — os testes nunca tocam `data/` nem banco de produção.
  Manter esse padrão em testes novos. **Todo modelo novo entra com testes de
  isolamento no padrão de test_isolamento.py.**
- Sem cobertura (não testar com chamadas reais à OpenAI): conteúdo gerado pela
  IA (atas e edição de fotos) — validar manualmente ao mexer em `ai_edit.py`.

## Roadmap

A visão de produto e as próximas fases (agenda/tarefas por obra, setor de
manutenção, setor de compras) estão em `ROADMAP.md` — consultar antes de
propor mudanças estruturais (papéis de usuário, vínculo usuário↔obra, emails).

## Estrutura

```
app.py               # App Flask principal + init_db() (cria tabelas e admin)
config.py            # Config central: caminhos (DATA_DIR), constantes, database_url()
models.py            # Modelos SQLAlchemy
extensions.py        # Instâncias das extensões Flask
blueprints/
  auth.py            # Login/usuários
  relatorios.py      # Obras, cômodos, fotos, geração de relatórios
  atas.py            # Atas de reunião (.docx, com IA)
pptx_generator.py    # Gera o .pptx a partir de template/TEMPLATE_STEWART.pptx
ai_edit.py           # Integração OpenAI (edição de fotos + texto das atas)
utils.py             # Processamento de imagem (EXIF, resize, formatos)
data/                # Banco + uploads (runtime, fora do git) — em prod é DATA_DIR=/var/data
```

## Convenções

- **Tudo em pt-BR**: código, comentários, commits, UI e docs — manter assim.
- Comentários explicam o "porquê" (o código existente faz isso bem; seguir o padrão).
- Commits pequenos e descritivos em pt-BR (ver `git log` como referência de estilo).

## Segurança — NÃO regredir estas camadas

Toda mudança em rotas/consultas deve preservar:

1. **Isolamento por dono (row-level na aplicação)**: toda query filtra pelo
   usuário logado e toda rota confere a posse do recurso — inclusive a entrega
   de imagens em `/uploads/...`. Nunca criar rota/consulta que exponha dados de
   outro usuário.
2. **CSRF** em toda escrita (Flask-WTF), **rate limit** no login e nas rotas de IA
   (Flask-Limiter), senhas com hash PBKDF2 (mín. 8 chars).
3. Em produção (`IS_PRODUCTION` em config.py): cookies Secure, HSTS, CSP,
   `SECRET_KEY` obrigatória (a app recusa subir sem).

## Deploy (Render)

- Blueprint em `render.yaml`; deploy automático pela branch **main** (push na main = deploy).
- Banco PostgreSQL externo no Neon (`DATABASE_URL` definida no painel do Render).
- Fotos ficam no disco persistente do Render (`DATA_DIR=/var/data`) — **nunca**
  gravar uploads fora de `DATA_DIR`, senão somem no próximo deploy.
- `startCommand` roda `app.init_db()` antes do gunicorn — mudanças de schema
  precisam funcionar nesse fluxo (não há Alembic/migrations; `init_db` só cria
  tabelas novas, não altera colunas existentes).
- Detalhes passo a passo em `DEPLOY.md`.

## Pegadinhas

- Fotos são processadas no upload (`utils.py`): reorientação EXIF, resize p/ 2000px,
  HEIC/HEIF via `pillow-heif`. Alta resolução nunca deve ser recusada — é reduzida.
- `config.py` carrega o `.env` antes de tudo; qualquer módulo pode ler `os.environ`
  depois de importar `config`.
- O template oficial `template/TEMPLATE_STEWART.pptx` é a fonte do layout do
  relatório — mudanças de layout se fazem preferencialmente nele/no
  `pptx_generator.py`, mantendo 2 fotos por slide agrupadas por cômodo.
- O relatório é sempre **.pptx** (nunca PDF) — decisão de produto, a equipe edita antes de enviar.
