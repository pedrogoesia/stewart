"""Catálogo da plataforma: ferramentas disponíveis e o mapa de processos.

Este é o "índice" da plataforma. Para adicionar uma ferramenta nova no futuro
(ex.: Notas Fiscais), basta:
  1. criar o blueprint da ferramenta em blueprints/;
  2. registrá-lo no app.py;
  3. marcar `ativo=True` e apontar o `endpoint` aqui embaixo.

O FERRAMENTAS alimenta o painel inicial (vitrine). O PROCESSOS alimenta o
"Mapa de Processos" — o diagrama em árvore da construtora, onde cada caixa é
um processo do negócio e algumas já têm ferramenta nesta plataforma.
"""

# ---------------------------------------------------------------------------
# Vitrine de ferramentas (painel inicial)
# ---------------------------------------------------------------------------
FERRAMENTAS = [
    {
        "slug": "relatorios",
        "nome": "Relatórios de Obras",
        "descricao": "Monte o relatório fotográfico mensal em PowerPoint, "
                     "organizado por cômodo, e baixe as fotos em .zip.",
        "icone": "camera",
        "endpoint": "relatorios.index",
        "ativo": True,
    },
    {
        "slug": "notas-fiscais",
        "nome": "Notas Fiscais",
        "descricao": "Organização e controle das notas fiscais de materiais e "
                     "serviços da obra.",
        "icone": "receipt",
        "endpoint": None,
        "ativo": False,
    },
    {
        "slug": "orcamentos",
        "nome": "Orçamentos",
        "descricao": "Montagem e acompanhamento de orçamentos de obra, do custo "
                     "à proposta.",
        "icone": "calculator",
        "endpoint": None,
        "ativo": False,
    },
    {
        "slug": "financeiro",
        "nome": "Financeiro",
        "descricao": "Controle financeiro da obra: contas a pagar e a receber e "
                     "fluxo de caixa.",
        "icone": "chart",
        "endpoint": None,
        "ativo": False,
    },
]


def ferramenta_por_slug(slug):
    for f in FERRAMENTAS:
        if f["slug"] == slug:
            return f
    return None


# ---------------------------------------------------------------------------
# Painel institucional da empresa ("harness" da Stewart Engenharia).
# Por enquanto é só o front: estes valores são placeholders que depois serão
# carregados do banco/back-end. Edite à vontade.
# ---------------------------------------------------------------------------
EMPRESA = {
    "nome": "Stewart Engenharia",
    "tagline": "Construção, reforma e incorporação",
    "sobre": "Espaço reservado para a apresentação institucional da Stewart "
             "Engenharia — história, missão, valores e diferenciais. Este texto "
             "será editável e carregado do sistema em breve.",
    "cadastro": [
        {"rotulo": "Razão social", "valor": "—"},
        {"rotulo": "CNPJ", "valor": "—"},
        {"rotulo": "Inscrição estadual", "valor": "—"},
        {"rotulo": "Inscrição municipal", "valor": "—"},
        {"rotulo": "Fundação", "valor": "—"},
    ],
    "contato": [
        {"rotulo": "Endereço", "valor": "—"},
        {"rotulo": "Telefone", "valor": "—"},
        {"rotulo": "E-mail", "valor": "—"},
        {"rotulo": "Site", "valor": "—"},
    ],
    "tecnico": [
        {"rotulo": "Responsável técnico", "valor": "—"},
        {"rotulo": "CREA / CAU", "valor": "—"},
        {"rotulo": "ART vigente", "valor": "—"},
    ],
    "areas": ["Obras residenciais", "Obras comerciais", "Reformas",
              "Incorporação", "Gerenciamento de obras"],
    "indicadores": [
        {"rotulo": "Obras ativas", "valor": "—"},
        {"rotulo": "Equipe", "valor": "—"},
        {"rotulo": "Anos de atuação", "valor": "—"},
        {"rotulo": "Obras entregues", "valor": "—"},
    ],
    "documentos": [
        "Contrato social",
        "Certidões (CND federal, estadual, municipal, FGTS)",
        "Alvarás e licenças",
        "Certificações de qualidade",
    ],
}


# ---------------------------------------------------------------------------
# Mapa de processos da construtora (árvore). Cada nó pode apontar para uma
# ferramenta (campo "ferramenta" = slug), criando a ponte processo → ferramenta.
# Vá enriquecendo esta árvore conforme mapeia o negócio.
# ---------------------------------------------------------------------------
PROCESSOS = {
    "nome": "Construtora",
    "descricao": "Visão geral dos processos do negócio",
    "filhos": [
        {"nome": "Comercial", "filhos": [
            {"nome": "Prospecção de clientes"},
            {"nome": "Orçamentos", "ferramenta": "orcamentos"},
            {"nome": "Propostas e contratos"},
        ]},
        {"nome": "Planejamento", "filhos": [
            {"nome": "Projetos e aprovações"},
            {"nome": "Cronograma físico-financeiro"},
            {"nome": "Orçamento da obra", "ferramenta": "orcamentos"},
        ]},
        {"nome": "Suprimentos", "filhos": [
            {"nome": "Cotação e compras"},
            {"nome": "Notas fiscais", "ferramenta": "notas-fiscais"},
            {"nome": "Controle de estoque"},
        ]},
        {"nome": "Execução da Obra", "filhos": [
            {"nome": "Acompanhamento fotográfico", "ferramenta": "relatorios"},
            {"nome": "Diário de obra"},
            {"nome": "Controle de qualidade"},
            {"nome": "Segurança do trabalho"},
        ]},
        {"nome": "Financeiro", "filhos": [
            {"nome": "Contas a pagar"},
            {"nome": "Contas a receber"},
            {"nome": "Notas fiscais", "ferramenta": "notas-fiscais"},
        ]},
        {"nome": "Pós-obra", "filhos": [
            {"nome": "Vistoria e entrega"},
            {"nome": "Assistência técnica"},
        ]},
    ],
}
