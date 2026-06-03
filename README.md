# Stewart Construtora — Relatórios Fotográficos de Obras

Sistema web (computador **e** celular) para montar os relatórios fotográficos
mensais das obras da Stewart. A pessoa em campo anexa as fotos, escreve a
descrição embaixo de cada uma e organiza por cômodo. Com um clique o sistema
gera o **relatório em PowerPoint** (no modelo oficial da Stewart) e também
permite **baixar todas as fotos em um `.zip` com uma pasta por cômodo**.

## Funcionalidades

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

## Estrutura do projeto

```
app.py               # Servidor web (Flask) + API + banco SQLite
pptx_generator.py    # Geração do .pptx a partir do template oficial
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
