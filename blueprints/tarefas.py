"""Ferramenta: Agenda de Tarefas por obra (spec: specs/fase1-agenda-tarefas.md).

Quem gerencia (cria/edita/atribui/exclui) tarefas de uma obra: admin, dono da
obra ou engenheiro membro. Encarregado e estagiário veem as tarefas das suas
obras e mudam o status das que estão atribuídas a eles. Quem não é membro
recebe 404 (o recurso "não existe" para ele).
"""

from datetime import date, datetime, timedelta

from flask import (Blueprint, abort, jsonify, redirect, render_template,
                   request, url_for)
from flask_login import current_user, login_required
from sqlalchemy import func

from extensions import db
from models import (PAPEIS, PRIORIDADES_TAREFA, STATUS_TAREFA, ItemChecklist,
                    Obra, Tarefa, Usuario, eh_membro_da_obra,
                    item_checklist_do_membro, obra_do_membro,
                    pode_gerenciar_tarefas, pode_mudar_andamento,
                    registrar_atividade, tarefa_do_membro)

bp = Blueprint("tarefas", __name__)

# Prioridade desconhecida no banco (edição manual, import) degrada para
# 'media' na ordenação em vez de derrubar a página com ValueError.
_ORDEM_PRIORIDADE = {p: i for i, p in enumerate(PRIORIDADES_TAREFA)}


def _chave_prioridade_prazo(t):
    """Ordenação padrão das listas: prioridade (alta primeiro), depois prazo
    (sem prazo por último)."""
    return (_ORDEM_PRIORIDADE.get(t.prioridade, _ORDEM_PRIORIDADE["media"]),
            t.prazo is None, t.prazo or date.max)


@bp.before_request
def _exige_acesso():
    """Exige login e que o usuário tenha a ferramenta 'Tarefas' liberada."""
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login", next=request.url))
    if not current_user.pode_ver_ferramenta("tarefas"):
        abort(403)


def _fim_da_semana(hoje):
    return hoje + timedelta(days=6 - hoje.weekday())   # domingo


def agrupar_por_prazo(tarefas, hoje=None):
    """Grupos da visão "minha semana" (concluídas ficam de fora):
    atrasadas (prazo passou) / semana (até domingo) / próximas (resto,
    sem prazo por último). Dentro de cada grupo: prioridade (alta
    primeiro) e depois prazo."""
    hoje = hoje or date.today()
    domingo = _fim_da_semana(hoje)
    grupos = {"atrasadas": [], "semana": [], "proximas": []}
    pendentes = sorted((t for t in tarefas if t.status != "concluida"),
                       key=_chave_prioridade_prazo)
    for t in pendentes:
        if t.prazo and t.prazo < hoje:
            grupos["atrasadas"].append(t)
        elif t.prazo and t.prazo <= domingo:
            grupos["semana"].append(t)
        else:
            grupos["proximas"].append(t)
    return grupos


def _obras_do_usuario():
    """Obras que aparecem na Agenda: as do dono + as vinculadas (admin: todas)."""
    if current_user.is_admin:
        return Obra.query.order_by(Obra.nome).all()
    vistos, obras = set(), []
    for o in list(current_user.obras) + list(current_user.obras_membro):
        if o.id not in vistos:
            vistos.add(o.id)
            obras.append(o)
    return sorted(obras, key=lambda o: o.nome.lower())


def _ler_prazo(valor):
    """'' → sem prazo; 'AAAA-MM-DD' → date; outro formato → erro."""
    valor = (valor or "").strip()
    if not valor:
        return None, None
    try:
        return date.fromisoformat(valor), None
    except ValueError:
        return None, "Prazo inválido: use o formato AAAA-MM-DD."


def _ler_prioridade(valor):
    """'' → 'media' (default); senão precisa ser uma das PRIORIDADES_TAREFA."""
    valor = (valor or "").strip().lower()
    if not valor:
        return "media", None
    if valor not in PRIORIDADES_TAREFA:
        return None, "Prioridade inválida: use alta, media ou baixa."
    return valor, None


def _ler_texto_item(valor):
    """Texto de item do checklist: obrigatório (não pode ficar vazio)."""
    valor = (valor or "").strip()
    if not valor:
        return None, "Escreva o item do checklist."
    return valor, None


def _ler_responsavel(valor, obra):
    """'' → sem responsável; senão precisa ser membro da obra."""
    valor = (valor or "").strip()
    if not valor:
        return None, None
    try:
        rid = int(valor)
    except ValueError:
        return None, "Responsável inválido."
    usuario = db.session.get(Usuario, rid)
    if usuario is None or not eh_membro_da_obra(obra, usuario):
        return None, "O responsável precisa ser membro da obra."
    return rid, None


# ---------------------------------------------------------------------------
# Páginas
# ---------------------------------------------------------------------------
@bp.route("/tarefas")
@login_required
def index():
    minhas = (Tarefa.query.filter_by(responsavel_id=current_user.id)
              .order_by(Tarefa.prazo).all())
    return render_template("tarefas.html", grupos=agrupar_por_prazo(minhas),
                           obras=_obras_do_usuario(), hoje=date.today())


@bp.route("/obra/<int:obra_id>/tarefas")
@login_required
def obra_tarefas(obra_id):
    obra = obra_do_membro(obra_id)
    # Quadro kanban (Fase 1b): uma coluna por status. Pendentes e em andamento
    # por prioridade/prazo; concluídas da mais recente para a mais antiga.
    colunas = {s: [] for s in STATUS_TAREFA}
    for t in obra.tarefas:
        colunas.get(t.status, colunas["pendente"]).append(t)
    for s in ("pendente", "em_andamento"):
        colunas[s].sort(key=_chave_prioridade_prazo)
    colunas["concluida"].sort(key=lambda t: t.concluida_em or "", reverse=True)
    # Quem pode ser responsável: dono + membros (sem repetir).
    membros = {obra.usuario.id: obra.usuario}
    membros.update({m.id: m for m in obra.membros})
    return render_template(
        "obra_tarefas.html", obra=obra, colunas=colunas,
        membros=list(membros.values()),
        pode_gerenciar=pode_gerenciar_tarefas(obra), papeis=PAPEIS,
        prioridades=PRIORIDADES_TAREFA, hoje=date.today())


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
@bp.route("/obra/<int:obra_id>/tarefas/criar", methods=["POST"])
@login_required
def criar_tarefa(obra_id):
    obra = obra_do_membro(obra_id)
    if not pode_gerenciar_tarefas(obra):
        abort(403)
    titulo = (request.form.get("titulo") or "").strip()
    if not titulo:
        return jsonify({"erro": "Dê um título à tarefa."}), 400
    prazo, erro = _ler_prazo(request.form.get("prazo"))
    if erro:
        return jsonify({"erro": erro}), 400
    responsavel_id, erro = _ler_responsavel(
        request.form.get("responsavel_id"), obra)
    if erro:
        return jsonify({"erro": erro}), 400
    prioridade, erro = _ler_prioridade(request.form.get("prioridade"))
    if erro:
        return jsonify({"erro": erro}), 400

    tarefa = Tarefa(obra_id=obra.id, titulo=titulo,
                    descricao=(request.form.get("descricao") or "").strip(),
                    responsavel_id=responsavel_id, criador_id=current_user.id,
                    prazo=prazo, prioridade=prioridade,
                    criado_em=datetime.now().isoformat())
    db.session.add(tarefa)
    db.session.commit()
    registrar_atividade("tarefa_criada",
                        f"Criou a tarefa '{titulo}' em '{obra.nome}'",
                        obra_id=obra.id)
    return jsonify({"id": tarefa.id, "titulo": titulo})


@bp.route("/tarefa/<int:tarefa_id>/editar", methods=["POST"])
@login_required
def editar_tarefa(tarefa_id):
    tarefa = tarefa_do_membro(tarefa_id)
    if not pode_gerenciar_tarefas(tarefa.obra):
        abort(403)
    if "titulo" in request.form:
        titulo = (request.form.get("titulo") or "").strip()
        if not titulo:
            return jsonify({"erro": "Dê um título à tarefa."}), 400
        tarefa.titulo = titulo
    if "descricao" in request.form:
        tarefa.descricao = (request.form.get("descricao") or "").strip()
    if "prazo" in request.form:
        prazo, erro = _ler_prazo(request.form.get("prazo"))
        if erro:
            return jsonify({"erro": erro}), 400
        tarefa.prazo = prazo
    if "responsavel_id" in request.form:
        responsavel_id, erro = _ler_responsavel(
            request.form.get("responsavel_id"), tarefa.obra)
        if erro:
            return jsonify({"erro": erro}), 400
        tarefa.responsavel_id = responsavel_id
    # Vazio na edição mantém o valor atual (diferente de criar, onde vazio
    # vira o default) — um form que sempre envia o campo não rebaixa a tarefa.
    if (request.form.get("prioridade") or "").strip():
        prioridade, erro = _ler_prioridade(request.form.get("prioridade"))
        if erro:
            return jsonify({"erro": erro}), 400
        tarefa.prioridade = prioridade
    db.session.commit()
    return jsonify({"ok": True})


@bp.route("/tarefa/<int:tarefa_id>/status", methods=["POST"])
@login_required
def mudar_status(tarefa_id):
    tarefa = tarefa_do_membro(tarefa_id)
    if not pode_mudar_andamento(tarefa):
        abort(403)
    status = (request.form.get("status") or "").strip()
    if status not in STATUS_TAREFA:
        return jsonify({"erro": "Status inválido."}), 400
    tarefa.status = status
    tarefa.concluida_em = (datetime.now().isoformat()
                           if status == "concluida" else None)
    db.session.commit()
    if status == "concluida":
        registrar_atividade("tarefa_concluida",
                            f"Concluiu a tarefa '{tarefa.titulo}'",
                            obra_id=tarefa.obra_id)
    return jsonify({"ok": True, "status": status})


@bp.route("/tarefa/<int:tarefa_id>/excluir", methods=["POST"])
@login_required
def excluir_tarefa(tarefa_id):
    tarefa = tarefa_do_membro(tarefa_id)
    if not pode_gerenciar_tarefas(tarefa.obra):
        abort(403)
    titulo = tarefa.titulo
    db.session.delete(tarefa)
    db.session.commit()
    registrar_atividade("tarefa_excluida", f"Excluiu a tarefa '{titulo}'",
                        obra_id=tarefa.obra_id)
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Checklist (subtarefas) — spec: specs/fase1b-agenda-kanban.md
# Criar/editar/excluir itens: quem gerencia a tarefa. Marcar feito: também o
# responsável (é o "andamento fino", mesma regra de mudar o status).
# ---------------------------------------------------------------------------
@bp.route("/tarefa/<int:tarefa_id>/checklist/criar", methods=["POST"])
@login_required
def criar_item_checklist(tarefa_id):
    tarefa = tarefa_do_membro(tarefa_id)
    if not pode_gerenciar_tarefas(tarefa.obra):
        abort(403)
    texto, erro = _ler_texto_item(request.form.get("texto"))
    if erro:
        return jsonify({"erro": erro}), 400
    # Agregado no banco (não carrega a coleção); empate raro entre criações
    # simultâneas fica estável pelo desempate por id no order_by do modelo.
    ultima_ordem = (db.session.query(func.max(ItemChecklist.ordem))
                    .filter(ItemChecklist.tarefa_id == tarefa.id)
                    .scalar()) or 0
    item = ItemChecklist(tarefa_id=tarefa.id, texto=texto,
                         ordem=ultima_ordem + 1)
    db.session.add(item)
    db.session.commit()
    return jsonify({"id": item.id, "texto": texto})


@bp.route("/checklist/<int:item_id>/editar", methods=["POST"])
@login_required
def editar_item_checklist(item_id):
    item = item_checklist_do_membro(item_id)
    if not pode_gerenciar_tarefas(item.tarefa.obra):
        abort(403)
    texto, erro = _ler_texto_item(request.form.get("texto"))
    if erro:
        return jsonify({"erro": erro}), 400
    item.texto = texto
    db.session.commit()
    return jsonify({"ok": True})


@bp.route("/checklist/<int:item_id>/feito", methods=["POST"])
@login_required
def marcar_item_checklist(item_id):
    item = item_checklist_do_membro(item_id)
    if not pode_mudar_andamento(item.tarefa):
        abort(403)
    valor = (request.form.get("feito") or "").strip().lower()
    if valor not in ("0", "1", "true", "false"):
        return jsonify({"erro": "Valor de 'feito' inválido."}), 400
    item.feito = valor in ("1", "true")
    db.session.commit()
    feitos, total = item.tarefa.progresso_checklist()
    return jsonify({"ok": True, "feitos": feitos, "total": total})


@bp.route("/checklist/<int:item_id>/excluir", methods=["POST"])
@login_required
def excluir_item_checklist(item_id):
    item = item_checklist_do_membro(item_id)
    if not pode_gerenciar_tarefas(item.tarefa.obra):
        abort(403)
    db.session.delete(item)
    db.session.commit()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Badge do menu: minhas tarefas atrasadas ou desta semana (não concluídas)
# ---------------------------------------------------------------------------
@bp.app_context_processor
def _badge():
    def tarefas_badge():
        if (not current_user.is_authenticated
                or not current_user.pode_ver_ferramenta("tarefas")):
            return 0
        return (Tarefa.query
                .filter(Tarefa.responsavel_id == current_user.id,
                        Tarefa.status != "concluida",
                        Tarefa.prazo.isnot(None),
                        Tarefa.prazo <= _fim_da_semana(date.today()))
                .count())
    return {"tarefas_badge": tarefas_badge}
