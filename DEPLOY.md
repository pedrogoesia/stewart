# Como publicar o Stewart OS no Render

O projeto já vem pronto para o Render (arquivo `render.yaml`): ele cria o site,
o banco PostgreSQL e o disco das fotos automaticamente.

## Passo a passo

1. **Garanta que o código está no GitHub** (este repositório, na branch
   `claude/determined-thompson-IO3vD`).

2. Crie uma conta em **https://render.com** e clique em **New → Blueprint**.

3. **Conecte este repositório** e selecione a branch
   `claude/determined-thompson-IO3vD`. O Render vai ler o `render.yaml` e montar:
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
