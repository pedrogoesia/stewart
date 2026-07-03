# Stewart Construtora — Relatórios Fotográficos de Obras

Sistema web (computador **e** celular) para montar os relatórios fotográficos
mensais das obras da Stewart. A pessoa em campo anexa as fotos, escreve a
descrição embaixo de cada uma e organiza por cômodo. Com um clique o sistema
gera o **relatório em PowerPoint** (no modelo oficial da Stewart) e também
permite **baixar todas as fotos em um `.zip` com uma pasta por cômodo**.

## Funcionalidades

- 🔐 **Login por usuário** — cada pessoa entra com email e senha e vê **apenas
  as próprias obras**. O administrador cria os usuários; cada um pode alterar o
  próprio nome, email e senha em "Minha conta". As senhas são guardadas com
  hash (nunca em texto puro).
- 📁 **Várias obras** — cada obra com nome e endereço.
- 🚪 **Organização por cômodo** — Sala, Cozinha, Banheiro, etc.
- 📷 **Upload pelo celular ou computador** — tirar foto na hora (câmera) ou
  escolher da galeria; envio de várias fotos de uma vez.
- ✍️ **Descrição (legenda) embaixo de cada foto** — salva automaticamente.
- 📊 **Relatório em PowerPoint (.pptx)** — gerado a partir do template oficial
  `TEMPLATE_STEWART.pptx`: capa com nome/endereço da obra e mês/ano, e slides
  com **2 fotos por slide** agrupadas por cômodo, com a legenda embaixo.
- 🗂️ **Download das fotos em `.zip`** — uma pasta por cômodo, prontas para
  arquivar no computador.
- ✨ **Editar foto por IA (OpenAI gpt-image-1)** — descreva a alteração em texto
  (ex.: "remova a vassoura encostada na parede"); o sistema gera a foto editada,
  mostra o **antes/depois** e **só substitui depois que você autorizar**.

> O relatório é sempre gerado em **PowerPoint (.pptx)**, nunca em PDF — assim a
> equipe pode editar/ajustar antes de enviar.

## Como rodar

### Opção rápida (Linux/macOS)

```bash
./run.sh
```

O script cria um ambiente virtual, instala as dependências e sobe o servidor.

### Manual

```bash
python3 -m venv .venv
source .venv/bin/activate         # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Depois abra **http://localhost:5000** no navegador.

### Primeiro acesso (login)

Na primeira vez que o sistema sobe, ele cria um usuário administrador:

- **Email:** `admin@stewart.local` (ou o valor de `ADMIN_EMAIL` no `.env`)
- **Senha:** `admin` (ou o valor de `ADMIN_SENHA` no `.env`)

Entre com esse usuário, vá em **"Minha conta"** e troque a senha. Depois, em
**"Usuários"**, crie as contas das demais pessoas da equipe.

### Banco de dados

- **Local (desenvolvimento):** SQLite, sem configurar nada (arquivo
  `data/stewart.db`).
- **Produção (online):** PostgreSQL — defina `DATABASE_URL` no `.env` com a URL
  fornecida pela hospedagem. O mesmo código funciona nos dois.
- Defina também `SECRET_KEY` (chave longa e aleatória) ao publicar.

### Usando pelo celular

Rode o servidor no computador e, no celular conectado à **mesma rede Wi-Fi**,
acesse `http://IP-DO-COMPUTADOR:5000` (ex.: `http://192.168.0.10:5000`).
Para descobrir o IP: `ipconfig` (Windows) ou `ifconfig`/`ip a` (Linux/macOS).

## Como usar

1. **Nova obra** → informe nome e endereço.
2. Abra a obra e **adicione os cômodos** (Sala, Cozinha, ...).
3. Em cada cômodo, toque em **📷 Adicionar fotos** para tirar/escolher fotos.
4. Escreva a **descrição** embaixo de cada foto.
5. Escolha **mês/ano** e clique em **⬇ Gerar PowerPoint**.
6. Opcional: **⬇ Baixar fotos (.zip por cômodo)** para arquivar.

## Edição de fotos por IA (OpenAI) — opcional

O sistema funciona normalmente **sem** isso. Para habilitar a edição por prompt:

1. Pegue uma chave em **https://platform.openai.com/api-keys**.
2. Na pasta do projeto, crie um arquivo **`.env`** (copie o `.env.example`):
   ```powershell
   Copy-Item .env.example .env      # Windows
   # cp .env.example .env           # Mac/Linux
   ```
3. Abra o `.env` e cole a chave: `OPENAI_API_KEY=sua_chave_aqui`
4. Reinicie o servidor (`python app.py`).

Depois, em cada foto aparece o botão **✨** — clique, descreva a mudança,
clique em **Gerar** e, se gostar do resultado, em **Autorizar e aplicar**.

> 🔒 **Segurança:** o arquivo `.env` está no `.gitignore` e nunca vai para o
> GitHub. Nunca compartilhe sua chave. A edição usa o modelo de imagem da
> OpenAI (padrão `gpt-image-1`), configurável via `OPENAI_IMAGE_MODEL` no
> `.env`.
>
> ⚠️ O `gpt-image-1` exige que a sua **organização na OpenAI esteja
> verificada** (verificação de identidade em
> platform.openai.com/settings/organization/general) e que a conta tenha
> **créditos**. A cobrança é por imagem gerada.

## Segurança

O sistema usa **defesa em camadas** (várias proteções somadas). Nenhum sistema
é 100% imune, mas estas camadas elevam muito o custo de um ataque:

- **Isolamento por usuário (row-level)** — toda consulta filtra pelo dono e
  toda rota verifica a posse do recurso. Um usuário nunca vê/acessa obras,
  cômodos, fotos ou arquivos de outro (testado automaticamente). A entrega das
  imagens (`/uploads/...`) também exige login e checa o dono.
- **Senhas com hash** — guardadas com `werkzeug.security` (PBKDF2), nunca em
  texto puro. Tamanho mínimo de 8 caracteres.
- **Proteção CSRF** — todo formulário/requisição de escrita exige um token
  anti-CSRF (Flask-WTF), bloqueando ações forjadas por sites maliciosos.
- **Limite de requisições** (Flask-Limiter) — login limitado por minuto
  (anti força-bruta) e edição por IA limitada por hora (anti abuso/custo).
- **Cookies de sessão endurecidos** — `HttpOnly`, `SameSite=Lax` e `Secure`
  (HTTPS) em produção.
- **Cabeçalhos de segurança** — `Content-Security-Policy`, `X-Frame-Options`
  (anti-clickjacking), `X-Content-Type-Options`, `Referrer-Policy` e, em
  produção, `HSTS`.
- **HTTPS em produção** — via `ProxyFix` (atrás de proxy reverso) + cookies
  Secure. `SECRET_KEY` é **obrigatória** em produção (a app recusa subir sem).
- **SQL injection** — uso de ORM (SQLAlchemy) com consultas parametrizadas.

### Sobre "RLS" (Row Level Security)

RLS é um recurso do **PostgreSQL** que aplica o filtro por dono no próprio
banco, como camada extra. Hoje o isolamento é feito na **aplicação** (o padrão
para apps assim, e o que está testado). Para ligar o RLS do Postgres como
reforço, é preciso informar ao banco "quem é o usuário atual" a cada requisição
(`SET app.current_user_id`) e criar políticas por tabela — posso configurar
isso quando formos publicar no Postgres, se você quiser essa camada a mais.

### Variáveis de ambiente de segurança (produção)

| Variável | Para quê |
|----------|----------|
| `SECRET_KEY` | Assina o cookie de sessão (obrigatória). Gere com `python -c "import secrets; print(secrets.token_hex(32))"`. |
| `DATABASE_URL` | URL do PostgreSQL. Ativa o "modo produção" (cookies Secure, HSTS). |
| `RATELIMIT_STORAGE_URI` | Redis para o limite de requisições quando houver mais de um servidor. |
| `ADMIN_EMAIL` / `ADMIN_SENHA` | Primeiro administrador, criado na 1ª subida. |

## Estrutura do projeto

```
app.py               # Servidor web (Flask) + API + banco SQLite
pptx_generator.py    # Geração do .pptx a partir do template oficial
ai_edit.py           # Edição de fotos por IA (OpenAI gpt-image-1)
.env.example         # Modelo de configuração da chave da OpenAI
template/            # TEMPLATE_STEWART.pptx (modelo oficial)
templates/           # Páginas HTML (index, obra)
static/              # CSS, JS e logo
data/                # Banco e fotos enviadas (criado em runtime, fora do git)
```

## Observações técnicas

- As fotos são reorientadas (EXIF) e redimensionadas (lado maior 2000px) no
  envio, mantendo o `.pptx` leve.
- Suporte a fotos **HEIC/HEIF** (iPhone) quando o pacote opcional
  `pillow-heif` estiver instalado (já incluído no `requirements.txt`).
- Os dados ficam na pasta `data/` (banco `stewart.db` e fotos). Faça backup
  dessa pasta para preservar os relatórios.
