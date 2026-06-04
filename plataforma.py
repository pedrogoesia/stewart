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
]


def ferramenta_por_slug(slug):
    for f in FERRAMENTAS:
        if f["slug"] == slug:
            return f
    return None


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
