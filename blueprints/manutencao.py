"""Ferramenta: Manutenções (spec: specs/fase2-manutencao.md).

Obras já entregues (clientes antigos) e o histórico de manutenções de cada
uma. O gestor (admin ou papel 'manutencao') cadastra e agenda; o executor
(ex.: encarregado de manutenção) vê a semana dele e conclui com descrição e
fotos do serviço.
"""

import os
import uuid
from datetime import date, datetime, timedelta

from flask import (Blueprint, abort, jsonify, redirect, render_template,
                   request, send_from_directory, url_for)
from flask_login import current_user, login_required

from config import UPLOAD_DIR
from extensions import db
from models import (STATUS_MANUTENCAO, FotoManutencao, Manutencao,
                    ObraEntregue, Usuario, eh_gestor_manutencao,
                    manutencao_do_usuario, obra_entregue_do_gestor,
                    registrar_atividade)
from utils import foto_abs_path, processar_imagem

bp = Blueprint("manutencao", __name__)


@bp.before_request
def _exige_acesso():
    """Exige login e que o usuário tenha a ferramenta 'Manutenções'."""
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login", next=request.url))
    if not current_user.pode_ver_ferramenta("manutencao"):
        abort(403)


def _ler_data(valor, rotulo):
    valor = (valor or "").strip()
    if not valor:
        return None, None
    try:
        return date.fromisoformat(valor), None
    except ValueError:
        return None, f"{rotulo} inválida: use o formato AAAA-MM-DD."


def _agrupar_semana(manutencoes, hoje=None):
    """Atrasadas / esta semana / próximas (agendadas; concluídas ficam fora)."""
    hoje = hoje or date.today()
    domingo = hoje + timedelta(days=6 - hoje.weekday())
    grupos = {"atrasadas": [], "semana": [], "proximas": []}
    agendadas = sorted(
        (m for m in manutencoes if m.status != "concluida"),
        key=lambda m: (m.data_agendada is None, m.data_agendada or date.max))
    for m in agendadas:
        if m.data_agendada and m.data_agendada < hoje:
            grupos["atrasadas"].append(m)
        elif m.data_agendada and m.data_agendada <= domingo:
            grupos["semana"].append(m)
        else:
            grupos["proximas"].append(m)
    return grupos


# ---------------------------------------------------------------------------
# Páginas
# ---------------------------------------------------------------------------
@bp.route("/manutencao")
@login_required
def index():
    if eh_gestor_manutencao():
        obras = ObraEntregue.query.order_by(ObraEntregue.cliente).all()
        # Kanban do setor (Fase 2b): pendentes por data (sem data por último);
        # concluídas da mais recente para a mais antiga, limitadas.
        pendentes = sorted(
            Manutencao.query.filter(Manutencao.status != "concluida").all(),
            key=lambda m: (m.data_agendada is None,
                           m.data_agendada or date.max))
        colunas = {
            "agendada": [m for m in pendentes if m.status != "em_execucao"],
            "em_execucao": [m for m in pendentes
                            if m.status == "em_execucao"],
            "concluida": (Manutencao.query.filter_by(status="concluida")
                          .order_by(Manutencao.concluida_em.desc())
                          .limit(30).all()),
        }
        return render_template("manutencao.html", obras=obras,
                               colunas=colunas, hoje=date.today())
    minhas = (Manutencao.query
              .filter_by(responsavel_id=current_user.id)
              .order_by(Manutencao.data_agendada).all())
    return render_template("manutencao_semana.html",
                           grupos=_agrupar_semana(minhas), hoje=date.today())


@bp.route("/manutencao/obra/<int:obra_id>")
@login_required
def obra_detalhe(obra_id):
    obra = obra_entregue_do_gestor(obra_id)
    agendadas = _agrupar_semana(obra.manutencoes)
    concluidas = sorted(
        (m for m in obra.manutencoes if m.status == "concluida"),
        key=lambda m: m.concluida_em or "", reverse=True)
    executores = [u for u in Usuario.query.order_by(Usuario.nome).all()
                  if u.pode_ver_ferramenta("manutencao")]
    return render_template("manutencao_obra.html", obra=obra,
                           grupos=agendadas, concluidas=concluidas,
                           executores=executores, hoje=date.today())


# ---------------------------------------------------------------------------
# Obras entregues (gestor)
# ---------------------------------------------------------------------------
@bp.route("/manutencao/obras/criar", methods=["POST"])
@login_required
def criar_obra():
    if not eh_gestor_manutencao():
        abort(403)
    cliente = (request.form.get("cliente") or "").strip()
    if not cliente:
        return jsonify({"erro": "Informe o nome do cliente/obra."}), 400
    data_entrega, erro = _ler_data(request.form.get("data_entrega"),
                                   "Data de entrega")
    if erro:
        return jsonify({"erro": erro}), 400
    fim_garantia, erro = _ler_data(request.form.get("fim_garantia"),
                                   "Fim da garantia")
    if erro:
        return jsonify({"erro": erro}), 400
    obra = ObraEntregue(
        cliente=cliente, endereco=(request.form.get("endereco") or "").strip(),
        data_entrega=data_entrega, fim_garantia=fim_garantia,
        observacoes=(request.form.get("observacoes") or "").strip(),
        criado_em=datetime.now().isoformat())
    db.session.add(obra)
    db.session.commit()
    registrar_atividade("manut_obra_criada",
                        f"Cadastrou a obra entregue '{cliente}'")
    return jsonify({"id": obra.id, "cliente": cliente})


@bp.route("/manutencao/obra/<int:obra_id>/editar", methods=["POST"])
@login_required
def editar_obra(obra_id):
    obra = obra_entregue_do_gestor(obra_id)
    cliente = (request.form.get("cliente") or "").strip()
    if not cliente:
        return jsonify({"erro": "Informe o nome do cliente/obra."}), 400
    data_entrega, erro = _ler_data(request.form.get("data_entrega"),
                                   "Data de entrega")
    if erro:
        return jsonify({"erro": erro}), 400
    fim_garantia, erro = _ler_data(request.form.get("fim_garantia"),
                                   "Fim da garantia")
    if erro:
        return jsonify({"erro": erro}), 400
    obra.cliente = cliente
    obra.endereco = (request.form.get("endereco") or "").strip()
    obra.observacoes = (request.form.get("observacoes") or "").strip()
    obra.data_entrega, obra.fim_garantia = data_entrega, fim_garantia
    db.session.commit()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Agendamento (gestor)
# ---------------------------------------------------------------------------
@bp.route("/manutencao/obra/<int:obra_id>/agendar", methods=["POST"])
@login_required
def agendar(obra_id):
    obra = obra_entregue_do_gestor(obra_id)
    titulo = (request.form.get("titulo") or "").strip()
    if not titulo:
        return jsonify({"erro": "Dê um título à manutenção."}), 400
    data_agendada, erro = _ler_data(request.form.get("data_agendada"), "Data")
    if erro:
        return jsonify({"erro": erro}), 400
    responsavel_id = None
    valor = (request.form.get("responsavel_id") or "").strip()
    if valor:
        try:
            responsavel_id = int(valor)
        except ValueError:
            return jsonify({"erro": "Responsável inválido."}), 400
        usuario = db.session.get(Usuario, responsavel_id)
        if usuario is None or not usuario.pode_ver_ferramenta("manutencao"):
            return jsonify({"erro": "O responsável precisa ter a ferramenta "
                            "Manutenções liberada."}), 400
    m = Manutencao(obra_entregue_id=obra.id, titulo=titulo,
                   detalhes=(request.form.get("detalhes") or "").strip(),
                   responsavel_id=responsavel_id, criador_id=current_user.id,
                   data_agendada=data_agendada,
                   criado_em=datetime.now().isoformat())
    db.session.add(m)
    db.session.commit()
    registrar_atividade("manut_agendada",
                        f"Agendou '{titulo}' em '{obra.cliente}'")
    return jsonify({"id": m.id, "titulo": titulo})


# ---------------------------------------------------------------------------
# Execução (responsável ou gestor)
# ---------------------------------------------------------------------------
@bp.route("/manutencao/<int:manutencao_id>/status", methods=["POST"])
@login_required
def mudar_status(manutencao_id):
    """Arrastar no kanban: agendada ↔ em_execucao. Concluir NÃO passa por
    aqui (rota própria, com descrição obrigatória); reabrir concluída fica
    fora do escopo da Fase 2b."""
    m = manutencao_do_usuario(manutencao_id)
    status = (request.form.get("status") or "").strip()
    if status not in STATUS_MANUTENCAO or status == "concluida":
        return jsonify({"erro": "Status inválido."}), 400
    if m.status == "concluida":
        return jsonify({"erro": "Manutenção concluída não pode ser "
                        "reaberta."}), 400
    m.status = status
    db.session.commit()
    return jsonify({"ok": True, "status": status})


@bp.route("/manutencao/<int:manutencao_id>/concluir", methods=["POST"])
@login_required
def concluir(manutencao_id):
    m = manutencao_do_usuario(manutencao_id)
    descricao = (request.form.get("descricao_realizada") or "").strip()
    if not descricao:
        return jsonify({"erro": "Descreva o serviço realizado."}), 400
    m.descricao_realizada = descricao
    m.status = "concluida"
    m.concluida_em = datetime.now().isoformat()
    db.session.commit()
    registrar_atividade("manut_concluida",
                        f"Concluiu '{m.titulo}' em '{m.obra.cliente}'")
    return jsonify({"ok": True})


@bp.route("/manutencao/<int:manutencao_id>/fotos", methods=["POST"])
@login_required
def enviar_foto(manutencao_id):
    m = manutencao_do_usuario(manutencao_id)
    file = request.files.get("foto")
    if file is None or file.filename == "":
        return jsonify({"erro": "Nenhum arquivo enviado"}), 400
    rel_dir = f"manutencao/{m.id}"
    abs_dir = os.path.join(UPLOAD_DIR, "manutencao", str(m.id))
    os.makedirs(abs_dir, exist_ok=True)
    nome_arquivo = f"{uuid.uuid4().hex}.jpg"
    try:
        processar_imagem(file, os.path.join(abs_dir, nome_arquivo))
    except Exception as e:  # noqa: BLE001
        return jsonify({"erro": f"Falha ao processar imagem: {e}"}), 400
    ordem = max((f.ordem for f in m.fotos), default=0) + 1
    foto = FotoManutencao(manutencao_id=m.id,
                          arquivo=f"{rel_dir}/{nome_arquivo}", ordem=ordem,
                          criado_em=datetime.now().isoformat())
    db.session.add(foto)
    db.session.commit()
    return jsonify({"id": foto.id,
                    "url": url_for("manutencao.servir_foto", foto_id=foto.id)})


@bp.route("/manutencao/foto/<int:foto_id>")
@login_required
def servir_foto(foto_id):
    foto = db.session.get(FotoManutencao, foto_id)
    if foto is None:
        abort(404)
    manutencao_do_usuario(foto.manutencao_id)   # 404 se não puder ver
    try:
        foto_abs_path(foto.arquivo)
    except ValueError:
        abort(404)
    return send_from_directory(UPLOAD_DIR, foto.arquivo, max_age=3600)


@bp.route("/manutencao/<int:manutencao_id>/excluir", methods=["POST"])
@login_required
def excluir(manutencao_id):
    if not eh_gestor_manutencao():
        abort(403)
    m = db.session.get(Manutencao, manutencao_id) or abort(404)
    for f in m.fotos:
        try:
            os.remove(foto_abs_path(f.arquivo))
        except (OSError, ValueError):
            pass
    titulo = m.titulo
    db.session.delete(m)
    db.session.commit()
    registrar_atividade("manut_excluida", f"Excluiu a manutenção '{titulo}'")
    return jsonify({"ok": True})
