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

from extensions import db
from models import (PAPEIS, STATUS_TAREFA, Obra, Tarefa, Usuario,
                    eh_membro_da_obra, obra_do_membro, pode_gerenciar_tarefas,
                    registrar_atividade, tarefa_do_membro)

bp = Blueprint("tarefas", __name__)


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
    sem prazo por último). Cada grupo ordenado por prazo."""
    hoje = hoje or date.today()
    domingo = _fim_da_semana(hoje)
    grupos = {"atrasadas": [], "semana": [], "proximas": []}
    pendentes = sorted((t for t in tarefas if t.status != "concluida"),
                       key=lambda t: (t.prazo is None, t.prazo or date.max))
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
    pendentes = agrupar_por_prazo(obra.tarefas)
    concluidas = sorted((t for t in obra.tarefas if t.status == "concluida"),
                        key=lambda t: t.concluida_em or "", reverse=True)
    # Quem pode ser responsável: dono + membros (sem repetir).
    membros = {obra.usuario.id: obra.usuario}
    membros.update({m.id: m for m in obra.membros})
    return render_template(
        "obra_tarefas.html", obra=obra, grupos=pendentes,
        concluidas=concluidas, membros=list(membros.values()),
        pode_gerenciar=pode_gerenciar_tarefas(obra), papeis=PAPEIS,
        hoje=date.today())


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

    tarefa = Tarefa(obra_id=obra.id, titulo=titulo,
                    descricao=(request.form.get("descricao") or "").strip(),
                    responsavel_id=responsavel_id, criador_id=current_user.id,
                    prazo=prazo, criado_em=datetime.now().isoformat())
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
    db.session.commit()
    return jsonify({"ok": True})


@bp.route("/tarefa/<int:tarefa_id>/status", methods=["POST"])
@login_required
def mudar_status(tarefa_id):
    tarefa = tarefa_do_membro(tarefa_id)
    if not (pode_gerenciar_tarefas(tarefa.obra)
            or tarefa.responsavel_id == current_user.id):
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
