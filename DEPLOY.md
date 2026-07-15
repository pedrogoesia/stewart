# Como publicar o Stewart OS no Render

O projeto já vem pronto para o Render (arquivo `render.yaml`): ele cria o site,
o banco PostgreSQL e o disco das fotos automaticamente.

## Passo a passo

1. **Garanta que o código está no GitHub** (este repositório, na branch
   `main`).

2. Crie uma conta em **https://render.com** e clique em **New → Blueprint**.

3. **Conecte este repositório** e selecione a branch
   `main`. O Render vai ler o `render.yaml` e montar:
   - o site (`stewart-os`);
   - o banco PostgreSQL (`stewart-db`);
   - o disco das fotos (5 GB, em `/var/data`).

4. Antes de finalizar, defina os **segredos** (campos que ficam em branco):
   - `ADMIN_SENHA` → a senha do primeiro administrador (use uma senha forte).
   - `OPENAI_API_KEY` → só se quiser a edição de fotos por IA (opcional).

5. Clique em **Apply / Deploy** e aguarde alguns minutos.

6. Acesse a URL que o Render gerar (algo como `https://stewart-os.onrender.com`)
   e **entre** com:
   - e-mail: `admin@stewart.local` (ou o que você colocou em `ADMIN_EMAIL`)
   - senha: a que você definiu em `ADMIN_SENHA`.

   Depois, em **Minha conta**, troque a senha e, em **Usuários**, crie as contas
   da equipe.

## Sobre custos

- O **disco persistente** (que guarda as fotos) exige o plano **Starter** do
  site (pago, ~US$ 7/mês). É ele que garante que as fotos não se percam.
- O **banco PostgreSQL** tem opções gerenciadas no próprio Render.

### Quer testar de graça primeiro?

Para uma demonstração sem custo, no `render.yaml`:
- troque `plan: starter` por `plan: free` no serviço, e
- **remova** o bloco `disk:` (e a variável `DATA_DIR`).

⚠️ Nesse modo grátis as **fotos não persistem** entre deploys/reinícios (o banco
de dados continua persistente no PostgreSQL). Ótimo para mostrar a interface e
os fluxos, não para uso real com fotos.

## Atualizações

Cada vez que você fizer `git push` para a branch publicada, o Render
**redeploya sozinho**.

## Capacidade (muitos usuários ao mesmo tempo)

O servidor sobe com **workers com threads** (`gunicorn.conf.py`): por padrão
2 processos × 16 threads = **32 requisições simultâneas**. Como o trabalho é
quase todo I/O (banco, OpenAI, disco), isso atende bem centenas de usuários
navegando ao mesmo tempo. Para ajustar sem mexer no código, defina no painel:

- `WEB_CONCURRENCY` → nº de processos (suba junto com o plano/CPU; ex.: 4 no
  plano Standard).
- `GUNICORN_THREADS` → threads por processo (padrão 16).

Dicas para carga alta:

- **Neon:** use a connection string **pooled** (com `-pooler` no host, via
  PgBouncer) na `DATABASE_URL` — ela aguenta muito mais conexões simultâneas
  que a direta.
- **Rate limit:** com mais de um processo, o limite de requisições é contado
  por processo. Para contagem exata, aponte `RATELIMIT_STORAGE_URI` para um
  Redis (ex.: o Key Value do próprio Render).
- Os arquivos estáticos (CSS/JS/imagens) são servidos pelo WhiteNoise com
  cache de 1 ano, sem ocupar a aplicação.
