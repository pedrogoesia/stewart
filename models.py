"""Modelos do banco (tabelas) e regras de acesso por usuário.

Núcleo: Usuário (login/contas) e Atividade (auditoria). A ferramenta de
Relatórios de Obras adiciona Obra → Cômodo → Foto.
"""

from datetime import datetime

from flask import abort, has_request_context, request
from flask_login import UserMixin, current_user
from werkzeug.security import check_password_hash, generate_password_hash

from config import SENHA_MIN
from extensions import db, login_manager


# ---------------------------------------------------------------------------
# Usuários (núcleo da plataforma)
# ---------------------------------------------------------------------------
# Catálogo de ferramentas da plataforma: slug -> nome exibido. Ao criar uma
# ferramenta nova, inclua-a aqui e proteja o blueprint com pode_ver_ferramenta.
FERRAMENTAS = {
    "relatorios": "Relatório de Obras",
    "atas": "Assistente de Atas",
    "tarefas": "Agenda de Tarefas",
    "manutencao": "Manutenções",
    "compras": "Compras",
}
TODAS_FERRAMENTAS = ",".join(FERRAMENTAS)

# Papéis de quem trabalha nas obras (opcional: contas antigas ficam sem papel).
# Quem gerencia tarefas de uma obra: admin, dono da obra ou engenheiro membro.
# Quem gerencia a ferramenta Manutenções: admin ou papel "manutencao".
PAPEIS = {
    "engenheiro": "Engenheiro",
    "encarregado": "Encarregado",
    "estagiario": "Estagiário",
    "manutencao": "Setor de Manutenção",
    "compras": "Setor de Compras",
}

# Vínculo usuário↔obra: define quais obras cada pessoa vê na Agenda de
# Tarefas (o dono da obra e o admin são membros implícitos).
obra_membros = db.Table(
    "obra_membros",
    db.Column("usuario_id", db.Integer, db.ForeignKey("usuarios.id"),
              primary_key=True),
    db.Column("obra_id", db.Integer, db.ForeignKey("obras.id"),
              primary_key=True),
)


class Usuario(UserMixin, db.Model):
    __tablename__ = "usuarios"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    nome = db.Column(db.String(255), default="")
    senha_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    criado_em = db.Column(db.String(40), nullable=False)
    # Slugs (separados por vírgula) das ferramentas liberadas para o usuário.
    # NULL (contas antigas, antes da migração) equivale a todas liberadas.
    ferramentas = db.Column(db.String(255), default=TODAS_FERRAMENTAS)
    # Papel na equipe (PAPEIS) — opcional; NULL nas contas antigas.
    papel = db.Column(db.String(20))

    obras = db.relationship("Obra", backref="usuario",
                            cascade="all, delete-orphan")
    obras_membro = db.relationship("Obra", secondary=obra_membros,
                                   backref="membros")

    def definir_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def conferir_senha(self, senha):
        return check_password_hash(self.senha_hash, senha or "")

    def ferramentas_liberadas(self):
        """Slugs que este usuário pode usar (admin vê tudo)."""
        if self.is_admin or self.ferramentas is None:
            return set(FERRAMENTAS)
        return {s for s in self.ferramentas.split(",") if s in FERRAMENTAS}

    def definir_ferramentas(self, slugs):
        """Grava a lista de ferramentas, ignorando slugs desconhecidos."""
        self.ferramentas = ",".join(s for s in FERRAMENTAS if s in set(slugs))

    def pode_ver_ferramenta(self, slug):
        return slug in self.ferramentas_liberadas()


# ---------------------------------------------------------------------------
# Ferramenta: Relatórios de Obras
# ---------------------------------------------------------------------------
class Obra(db.Model):
    __tablename__ = "obras"
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"),
                           nullable=False, index=True)
    nome = db.Column(db.String(255), nullable=False)
    endereco = db.Column(db.String(255), default="")
    criado_em = db.Column(db.String(40), nullable=False)

    comodos = db.relationship("Comodo", backref="obra",
                              cascade="all, delete-orphan")


class Comodo(db.Model):
    __tablename__ = "comodos"
    id = db.Column(db.Integer, primary_key=True)
    obra_id = db.Column(db.Integer, db.ForeignKey("obras.id"),
                        nullable=False, index=True)
    nome = db.Column(db.String(255), nullable=False)
    ordem = db.Column(db.Integer, nullable=False, default=0)
    # Seção de fotos avulsas ("sem cômodo"): no máximo uma por obra. As fotos
    # entram no relatório sem o prefixo/sublinhado de nome de cômodo.
    geral = db.Column(db.Boolean, nullable=False, default=False)

    fotos = db.relationship("Foto", backref="comodo",
                            cascade="all, delete-orphan")


class Foto(db.Model):
    __tablename__ = "fotos"
    id = db.Column(db.Integer, primary_key=True)
    comodo_id = db.Column(db.Integer, db.ForeignKey("comodos.id"),
                          nullable=False, index=True)
    arquivo = db.Column(db.String(500), nullable=False)
    descricao = db.Column(db.Text, default="")
    ordem = db.Column(db.Integer, nullable=False, default=0)
    criado_em = db.Column(db.String(40), nullable=False)


# ---------------------------------------------------------------------------
# Ferramenta: Agenda de Tarefas
# ---------------------------------------------------------------------------
STATUS_TAREFA = ("pendente", "em_andamento", "concluida")
# Da mais urgente para a menos: o índice serve de chave de ordenação.
PRIORIDADES_TAREFA = ("alta", "media", "baixa")


class Tarefa(db.Model):
    __tablename__ = "tarefas"
    id = db.Column(db.Integer, primary_key=True)
    obra_id = db.Column(db.Integer, db.ForeignKey("obras.id"),
                        nullable=False, index=True)
    titulo = db.Column(db.String(255), nullable=False)
    descricao = db.Column(db.Text, default="")
    # Responsável/criador ficam NULL se o usuário for excluído (histórico
    # da obra não se perde junto com a conta). O SET NULL vale em banco
    # novo; bancos antigos dependem da limpeza em admin_excluir_usuario.
    responsavel_id = db.Column(
        db.Integer, db.ForeignKey("usuarios.id", ondelete="SET NULL"),
        index=True)
    criador_id = db.Column(
        db.Integer, db.ForeignKey("usuarios.id", ondelete="SET NULL"))
    prazo = db.Column(db.Date, index=True)
    status = db.Column(db.String(20), nullable=False, default="pendente")
    prioridade = db.Column(db.String(10), nullable=False, default="media")
    criado_em = db.Column(db.String(40), nullable=False)
    concluida_em = db.Column(db.String(40))

    obra = db.relationship(
        "Obra", backref=db.backref("tarefas", cascade="all, delete-orphan"))
    responsavel = db.relationship("Usuario", foreign_keys=[responsavel_id])

    def progresso_checklist(self):
        """(feitos, total) — para o "2/5" no card; (0, 0) se não há checklist."""
        return (sum(1 for i in self.checklist if i.feito), len(self.checklist))


class ItemChecklist(db.Model):
    """Subtarefa marcável ('concretar laje' → armar ferragem, pedir concreto…).

    Some junto com a tarefa (CASCADE + delete-orphan): checklist não é
    histórico, é andamento — diferente dos vínculos SET NULL acima.
    """
    __tablename__ = "tarefa_checklist"
    id = db.Column(db.Integer, primary_key=True)
    tarefa_id = db.Column(
        db.Integer, db.ForeignKey("tarefas.id", ondelete="CASCADE"),
        nullable=False, index=True)
    texto = db.Column(db.String(255), nullable=False)
    feito = db.Column(db.Boolean, nullable=False, default=False)
    ordem = db.Column(db.Integer, nullable=False, default=0)

    # Desempate por id: se dois itens empatarem em 'ordem' (criações quase
    # simultâneas), a ordem exibida continua estável entre requisições.
    tarefa = db.relationship(
        "Tarefa", backref=db.backref(
            "checklist", cascade="all, delete-orphan",
            order_by="[ItemChecklist.ordem, ItemChecklist.id]"))


# ---------------------------------------------------------------------------
# Ferramenta: Manutenções (obras entregues / clientes antigos)
# ---------------------------------------------------------------------------
class ObraEntregue(db.Model):
    __tablename__ = "obras_entregues"
    id = db.Column(db.Integer, primary_key=True)
    cliente = db.Column(db.String(255), nullable=False)
    endereco = db.Column(db.String(255), default="")
    data_entrega = db.Column(db.Date)
    fim_garantia = db.Column(db.Date)
    observacoes = db.Column(db.Text, default="")
    criado_em = db.Column(db.String(40), nullable=False)


# Vocabulário do kanban do setor (Fase 2b). 'concluida' só entra pela rota
# de conclusão (descrição obrigatória), nunca pelo POST /status.
STATUS_MANUTENCAO = ("agendada", "em_execucao", "concluida")


class Manutencao(db.Model):
    __tablename__ = "manutencoes"
    id = db.Column(db.Integer, primary_key=True)
    obra_entregue_id = db.Column(
        db.Integer, db.ForeignKey("obras_entregues.id"),
        nullable=False, index=True)
    titulo = db.Column(db.String(255), nullable=False)
    detalhes = db.Column(db.Text, default="")
    # Responsável/criador ficam NULL se o usuário for excluído (o histórico
    # do cliente não se perde junto com a conta). O SET NULL vale em banco
    # novo; bancos antigos dependem da limpeza em admin_excluir_usuario.
    responsavel_id = db.Column(
        db.Integer, db.ForeignKey("usuarios.id", ondelete="SET NULL"),
        index=True)
    criador_id = db.Column(
        db.Integer, db.ForeignKey("usuarios.id", ondelete="SET NULL"))
    data_agendada = db.Column(db.Date, index=True)
    status = db.Column(db.String(20), nullable=False, default="agendada")
    descricao_realizada = db.Column(db.Text, default="")
    concluida_em = db.Column(db.String(40))
    criado_em = db.Column(db.String(40), nullable=False)

    obra = db.relationship(
        "ObraEntregue",
        backref=db.backref("manutencoes", cascade="all, delete-orphan"))
    responsavel = db.relationship("Usuario", foreign_keys=[responsavel_id])


class FotoManutencao(db.Model):
    __tablename__ = "fotos_manutencao"
    id = db.Column(db.Integer, primary_key=True)
    manutencao_id = db.Column(db.Integer, db.ForeignKey("manutencoes.id"),
                              nullable=False, index=True)
    arquivo = db.Column(db.String(500), nullable=False)
    ordem = db.Column(db.Integer, nullable=False, default=0)
    criado_em = db.Column(db.String(40), nullable=False)

    manutencao = db.relationship(
        "Manutencao",
        backref=db.backref("fotos", cascade="all, delete-orphan"))


# ---------------------------------------------------------------------------
# Ferramenta: Compras (pedidos de material e ordens de compra)
# ---------------------------------------------------------------------------
class Fornecedor(db.Model):
    __tablename__ = "fornecedores"
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(255), nullable=False)
    cnpj = db.Column(db.String(30), default="")
    telefone = db.Column(db.String(40), default="")
    email = db.Column(db.String(255), default="")
    contato = db.Column(db.String(255), default="")
    criado_em = db.Column(db.String(40), nullable=False)


class PedidoCompra(db.Model):
    __tablename__ = "pedidos_compra"
    id = db.Column(db.Integer, primary_key=True)
    # Obra pode ser escolhida do cadastro ou digitada livre (obra externa).
    # Se a obra/o solicitante forem excluídos, o pedido sobrevive: obra_id
    # vira NULL (o nome fica em obra_nome, desnormalizado de propósito).
    obra_id = db.Column(db.Integer,
                        db.ForeignKey("obras.id", ondelete="SET NULL"))
    obra_nome = db.Column(db.String(255), nullable=False)
    solicitante_id = db.Column(
        db.Integer, db.ForeignKey("usuarios.id", ondelete="SET NULL"),
        index=True)
    data_prevista = db.Column(db.Date)
    observacoes = db.Column(db.Text, default="")
    status = db.Column(db.String(20), nullable=False, default="aberto")
    criado_em = db.Column(db.String(40), nullable=False)

    solicitante = db.relationship("Usuario", foreign_keys=[solicitante_id])


class ItemPedido(db.Model):
    __tablename__ = "itens_pedido"
    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey("pedidos_compra.id"),
                          nullable=False, index=True)
    descricao = db.Column(db.String(500), nullable=False)
    unidade = db.Column(db.String(20), default="UNID")
    # Numeric/Decimal, não Float: quantidades e valores entram em contas de
    # dinheiro, e float binário acumula erro de arredondamento nos centavos.
    quantidade = db.Column(db.Numeric(12, 3), nullable=False, default=1)
    ordem = db.Column(db.Integer, nullable=False, default=0)

    pedido = db.relationship(
        "PedidoCompra",
        backref=db.backref("itens", cascade="all, delete-orphan",
                           order_by="ItemPedido.ordem"))


class OrdemCompra(db.Model):
    __tablename__ = "ordens_compra"
    id = db.Column(db.Integer, primary_key=True)   # nº da ordem = id
    pedido_id = db.Column(db.Integer, db.ForeignKey("pedidos_compra.id"),
                          nullable=False, index=True)
    fornecedor_id = db.Column(db.Integer, db.ForeignKey("fornecedores.id"),
                              nullable=False)
    data = db.Column(db.Date)
    faturamento_razao = db.Column(db.String(255), default="")
    faturamento_cnpj_cpf = db.Column(db.String(30), default="")
    faturamento_endereco = db.Column(db.String(255), default="")
    faturamento_cep = db.Column(db.String(20), default="")
    entrega_endereco = db.Column(db.String(255), default="")
    entrega_cep = db.Column(db.String(20), default="")
    frete = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    desconto = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    cond_pagamento = db.Column(db.String(255), default="")
    obs = db.Column(db.Text, default="")
    criado_em = db.Column(db.String(40), nullable=False)

    pedido = db.relationship(
        "PedidoCompra",
        backref=db.backref("ordens", cascade="all, delete-orphan"))
    fornecedor = db.relationship("Fornecedor")

    def subtotal(self):
        return sum(i.quantidade * (i.valor_unit or 0) for i in self.itens)

    def total(self):
        return self.subtotal() + (self.frete or 0) - (self.desconto or 0)


class ItemOrdem(db.Model):
    __tablename__ = "itens_ordem"
    id = db.Column(db.Integer, primary_key=True)
    ordem_compra_id = db.Column(db.Integer,
                                db.ForeignKey("ordens_compra.id"),
                                nullable=False, index=True)
    descricao = db.Column(db.String(500), nullable=False)
    unidade = db.Column(db.String(20), default="UNID")
    quantidade = db.Column(db.Numeric(12, 3), nullable=False, default=1)
    valor_unit = db.Column(db.Numeric(12, 2))
    prazo_entrega = db.Column(db.Date)
    ordem = db.Column(db.Integer, nullable=False, default=0)

    ordem_compra = db.relationship(
        "OrdemCompra",
        backref=db.backref("itens", cascade="all, delete-orphan",
                           order_by="ItemOrdem.ordem"))


# ---------------------------------------------------------------------------
# Auditoria: quem fez o quê e quando
# ---------------------------------------------------------------------------
class Atividade(db.Model):
    """Registro de auditoria: quem fez o quê e quando (histórico de ações)."""
    __tablename__ = "atividades"
    id = db.Column(db.Integer, primary_key=True)
    # Guardamos o id E o e-mail (desnormalizado) para o histórico sobreviver
    # mesmo se o usuário for excluído depois.
    usuario_id = db.Column(db.Integer, index=True)
    usuario_email = db.Column(db.String(255))
    acao = db.Column(db.String(60), nullable=False, index=True)
    descricao = db.Column(db.String(500), default="")
    obra_id = db.Column(db.Integer, index=True)
    ip = db.Column(db.String(60))
    criado_em = db.Column(db.String(40), nullable=False, index=True)


def registrar_atividade(acao, descricao="", obra_id=None, email=None):
    """Grava uma linha no histórico de atividades. Nunca quebra a ação
    principal: se algo falhar aqui, apenas ignora."""
    try:
        autenticado = current_user.is_authenticated
        ip = None
        if has_request_context():
            ip = request.headers.get("X-Forwarded-For", request.remote_addr) or ""
            ip = ip.split(",")[0].strip() or None
        log = Atividade(
            usuario_id=current_user.id if autenticado else None,
            usuario_email=email or (current_user.email if autenticado else None),
            acao=acao, descricao=descricao, obra_id=obra_id, ip=ip,
            criado_em=datetime.now().isoformat(),
        )
        db.session.add(log)
        db.session.commit()
    except Exception:
        db.session.rollback()


@login_manager.user_loader
def carregar_usuario(user_id):
    try:
        return db.session.get(Usuario, int(user_id))
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Regras de acesso: só o dono (ou um admin) acessa cada recurso
# ---------------------------------------------------------------------------
def pode_acessar(usuario_id):
    return current_user.is_authenticated and (
        usuario_id == current_user.id or current_user.is_admin)


def obra_do_usuario(obra_id):
    obra = db.session.get(Obra, obra_id)
    if obra is None or not pode_acessar(obra.usuario_id):
        abort(404)
    return obra


def comodo_do_usuario(comodo_id):
    comodo = db.session.get(Comodo, comodo_id)
    if comodo is None or not pode_acessar(comodo.obra.usuario_id):
        abort(404)
    return comodo


def foto_do_usuario(foto_id):
    foto = db.session.get(Foto, foto_id)
    if foto is None or not pode_acessar(foto.comodo.obra.usuario_id):
        abort(404)
    return foto


def eh_membro_da_obra(obra, usuario=None):
    """Membro = vinculado em obra_membros, dono da obra ou admin."""
    u = usuario if usuario is not None else current_user
    if not u.is_authenticated:
        return False
    return (u.is_admin or obra.usuario_id == u.id
            or any(m.id == u.id for m in obra.membros))


def pode_gerenciar_tarefas(obra, usuario=None):
    """Cria/edita/atribui/exclui tarefas: admin, dono ou engenheiro membro."""
    u = usuario if usuario is not None else current_user
    if not eh_membro_da_obra(obra, u):
        return False
    return u.is_admin or obra.usuario_id == u.id or u.papel == "engenheiro"


def pode_mudar_andamento(tarefa, usuario=None):
    """Andamento da tarefa (status e itens do checklist): quem gerencia OU o
    responsável. A spec exige que as duas rotas usem a mesma regra —
    centralizada aqui para não divergirem."""
    u = usuario if usuario is not None else current_user
    return (pode_gerenciar_tarefas(tarefa.obra, u)
            or tarefa.responsavel_id == u.id)


def obra_do_membro(obra_id):
    """Obra visível na Agenda de Tarefas: membros; senão 404 (não vaza)."""
    obra = db.session.get(Obra, obra_id)
    if obra is None or not eh_membro_da_obra(obra):
        abort(404)
    return obra


def tarefa_do_membro(tarefa_id):
    tarefa = db.session.get(Tarefa, tarefa_id)
    if tarefa is None or not eh_membro_da_obra(tarefa.obra):
        abort(404)
    return tarefa


def item_checklist_do_membro(item_id):
    item = db.session.get(ItemChecklist, item_id)
    if item is None or not eh_membro_da_obra(item.tarefa.obra):
        abort(404)
    return item


def eh_gestor_manutencao(usuario=None):
    """Gestor da ferramenta Manutenções: admin ou papel 'manutencao'."""
    u = usuario if usuario is not None else current_user
    return u.is_authenticated and (u.is_admin or u.papel == "manutencao")


def obra_entregue_do_gestor(obra_id):
    obra = db.session.get(ObraEntregue, obra_id)
    if obra is None or not eh_gestor_manutencao():
        abort(404)
    return obra


def manutencao_do_usuario(manutencao_id):
    """Gestor vê qualquer manutenção; executor só as atribuídas a ele."""
    m = db.session.get(Manutencao, manutencao_id)
    if m is None or not (eh_gestor_manutencao()
                         or m.responsavel_id == current_user.id):
        abort(404)
    return m


def eh_setor_compras(usuario=None):
    """Setor de Compras: admin ou papel 'compras'."""
    u = usuario if usuario is not None else current_user
    return u.is_authenticated and (u.is_admin or u.papel == "compras")


def pedido_do_usuario(pedido_id):
    """Setor vê qualquer pedido; solicitante só os próprios."""
    p = db.session.get(PedidoCompra, pedido_id)
    if p is None or not (eh_setor_compras()
                         or p.solicitante_id == current_user.id):
        abort(404)
    return p


def ordem_do_setor(ordem_id):
    ordem = db.session.get(OrdemCompra, ordem_id)
    if ordem is None or not eh_setor_compras():
        abort(404)
    return ordem


def senha_fraca(senha):
    return len(senha or "") < SENHA_MIN
