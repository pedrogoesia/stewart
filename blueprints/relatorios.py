"""Ferramenta: Relatórios Fotográficos de Obras.

Página inicial da ferramenta em /relatorios. As rotas de obra/cômodo/foto
mantêm os mesmos caminhos de antes para não quebrar o front-end existente.
"""

import io
import os
import uuid
import zipfile
from datetime import datetime

from flask import (Blueprint, abort, jsonify, redirect, render_template,
                   request, send_file, send_from_directory, url_for)
from flask_login import current_user, login_required

from ai_edit import editar_imagem, ia_disponivel
from config import DATA_DIR, MESES, TEMPLATE_PATH, UPLOAD_DIR
from extensions import db, limiter
from models import (Comodo, Foto, Obra, comodo_do_usuario, foto_do_usuario,
                    obra_do_usuario, registrar_atividade)
from pptx_generator import gerar_relatorio
from utils import (comodos_com_fotos, foto_abs_path, periodo_label,
                   preview_rel, processar_imagem, remover_arquivos_da_obra,
                   slugify)

bp = Blueprint("relatorios", __name__)

# Nome interno da seção de fotos avulsas (aparece na pasta do .zip).
NOME_COMODO_GERAL = "Fotos"


@bp.before_request
def _exige_acesso():
    """Exige login e que o usuário tenha a solução 'Relatórios' liberada."""
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login", next=request.url))
    if not current_user.pode_ver_ferramenta("relatorios"):
        abort(403)


def _foto_path_or_404(arquivo):
    try:
        return foto_abs_path(arquivo)
    except ValueError:
        abort(404)


def _remover_foto_arquivo(arquivo):
    try:
        os.remove(foto_abs_path(arquivo))
    except (OSError, ValueError):
        pass


# ---------------------------------------------------------------------------
# Páginas
# ---------------------------------------------------------------------------
@bp.route("/relatorios")
@login_required
def index():
    obras = (Obra.query.filter_by(usuario_id=current_user.id)
             .order_by(Obra.id.desc()).all())
    dados = []
    for o in obras:
        dados.append({
            "id": o.id, "nome": o.nome, "endereco": o.endereco,
            "total_comodos": len(o.comodos),
            "total_fotos": sum(len(c.fotos) for c in o.comodos),
        })
    return render_template("index.html", obras=dados)


@bp.route("/obra/<int:obra_id>")
@login_required
def obra_detail(obra_id):
    obra = obra_do_usuario(obra_id)
    grupos = comodos_com_fotos(obra)
    agora = datetime.now()
    return render_template("obra.html", obra=obra, grupos=grupos,
                           meses=MESES, mes_atual=agora.month,
                           ano_atual=agora.year, ia_ativa=ia_disponivel())


# ---------------------------------------------------------------------------
# API — Obras
# ---------------------------------------------------------------------------
@bp.route("/obras", methods=["POST"])
@login_required
def criar_obra():
    nome = (request.form.get("nome") or "").strip()
    endereco = (request.form.get("endereco") or "").strip()
    if not nome:
        return redirect(url_for("relatorios.index"))
    obra = Obra(usuario_id=current_user.id, nome=nome, endereco=endereco,
                criado_em=datetime.now().isoformat())
    db.session.add(obra)
    db.session.commit()
    registrar_atividade("obra_criada", f"Criou a obra '{nome}'", obra_id=obra.id)
    return redirect(url_for("relatorios.index"))


@bp.route("/obra/<int:obra_id>/editar", methods=["POST"])
@login_required
def editar_obra(obra_id):
    obra = obra_do_usuario(obra_id)
    obra.nome = (request.form.get("nome") or "").strip()
    obra.endereco = (request.form.get("endereco") or "").strip()
    db.session.commit()
    return redirect(url_for("relatorios.obra_detail", obra_id=obra_id))


@bp.route("/obra/<int:obra_id>/excluir", methods=["POST"])
@login_required
def excluir_obra(obra_id):
    obra = obra_do_usuario(obra_id)
    nome_obra = obra.nome
    remover_arquivos_da_obra(obra)
    # Pedidos de compra citam a obra só como referência: sobrevivem com o
    # nome desnormalizado (obra_nome); a FK exige limpar antes de excluir.
    from models import PedidoCompra
    PedidoCompra.query.filter_by(obra_id=obra.id).update({"obra_id": None})
    db.session.delete(obra)
    db.session.commit()
    registrar_atividade("obra_excluida", f"Excluiu a obra '{nome_obra}'",
                        obra_id=obra_id)
    return redirect(url_for("relatorios.index"))


# ---------------------------------------------------------------------------
# API — Cômodos
# ---------------------------------------------------------------------------
@bp.route("/obra/<int:obra_id>/comodos", methods=["POST"])
@login_required
def criar_comodo(obra_id):
    obra = obra_do_usuario(obra_id)
    nome = (request.form.get("nome") or "").strip()
    if not nome:
        return jsonify({"erro": "Nome do cômodo é obrigatório"}), 400
    ordem = max((c.ordem for c in obra.comodos), default=0) + 1
    comodo = Comodo(obra_id=obra.id, nome=nome, ordem=ordem)
    db.session.add(comodo)
    db.session.commit()
    registrar_atividade("comodo_criado",
                        f"Adicionou o cômodo '{nome}' em '{obra.nome}'",
                        obra_id=obra.id)
    return jsonify({"id": comodo.id, "nome": nome})


@bp.route("/obra/<int:obra_id>/comodo-geral", methods=["POST"])
@login_required
def criar_comodo_geral(obra_id):
    """Seção única de fotos avulsas (sem separar por cômodo).

    Se a obra já tem a seção, devolve a existente (não cria duplicada).
    """
    obra = obra_do_usuario(obra_id)
    existente = next((c for c in obra.comodos if c.geral), None)
    if existente is not None:
        return jsonify({"id": existente.id, "nome": existente.nome,
                        "existente": True})
    ordem = max((c.ordem for c in obra.comodos), default=0) + 1
    comodo = Comodo(obra_id=obra.id, nome=NOME_COMODO_GERAL, ordem=ordem,
                    geral=True)
    db.session.add(comodo)
    db.session.commit()
    registrar_atividade("comodo_criado",
                        f"Adicionou a seção de fotos sem cômodo em '{obra.nome}'",
                        obra_id=obra.id)
    return jsonify({"id": comodo.id, "nome": comodo.nome, "existente": False})


@bp.route("/obra/<int:obra_id>/comodos/reordenar", methods=["POST"])
@login_required
def reordenar_comodos(obra_id):
    """Atualiza a ordem dos cômodos da obra (a ordem que vale no PowerPoint)."""
    obra = obra_do_usuario(obra_id)
    ids = request.form.get("ordem", "")
    id_list = [int(x) for x in ids.split(",") if x.strip().isdigit()]
    comodos = {c.id: c for c in obra.comodos}
    for posicao, comodo_id in enumerate(id_list):
        if comodo_id in comodos:
            comodos[comodo_id].ordem = posicao
    db.session.commit()
    return jsonify({"ok": True})


@bp.route("/comodo/<int:comodo_id>/renomear", methods=["POST"])
@login_required
def renomear_comodo(comodo_id):
    comodo = comodo_do_usuario(comodo_id)
    if comodo.geral:
        return jsonify({"erro": "A seção de fotos sem cômodo não pode "
                        "ser renomeada"}), 400
    nome = (request.form.get("nome") or "").strip()
    if not nome:
        return jsonify({"erro": "Nome inválido"}), 400
    comodo.nome = nome
    db.session.commit()
    return jsonify({"ok": True, "nome": nome})


@bp.route("/comodo/<int:comodo_id>/excluir", methods=["POST"])
@login_required
def excluir_comodo(comodo_id):
    comodo = comodo_do_usuario(comodo_id)
    for f in comodo.fotos:
        _remover_foto_arquivo(f.arquivo)
    db.session.delete(comodo)
    db.session.commit()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# API — Fotos
# ---------------------------------------------------------------------------
@bp.route("/comodo/<int:comodo_id>/fotos", methods=["POST"])
@login_required
def upload_foto(comodo_id):
    comodo = comodo_do_usuario(comodo_id)

    file = request.files.get("foto")
    if file is None or file.filename == "":
        return jsonify({"erro": "Nenhum arquivo enviado"}), 400

    descricao = (request.form.get("descricao") or "").strip()
    # Já inicia a legenda com o nome do cômodo, no modelo "Sala - ".
    # Na seção de fotos avulsas (sem cômodo) a descrição fica livre.
    if not descricao and not comodo.geral:
        descricao = f"{comodo.nome} - "
    # Caminho relativo guardado SEMPRE com "/" (compatível com URL e Windows).
    rel_dir = f"{comodo.obra_id}/{comodo_id}"
    abs_dir = os.path.join(UPLOAD_DIR, str(comodo.obra_id), str(comodo_id))
    os.makedirs(abs_dir, exist_ok=True)
    nome_arquivo = f"{uuid.uuid4().hex}.jpg"
    rel_path = f"{rel_dir}/{nome_arquivo}"

    try:
        processar_imagem(file, os.path.join(abs_dir, nome_arquivo))
    except Exception as e:  # noqa: BLE001
        return jsonify({"erro": f"Falha ao processar imagem: {e}"}), 400

    ordem = max((f.ordem for f in comodo.fotos), default=0) + 1
    foto = Foto(comodo_id=comodo_id, arquivo=rel_path, descricao=descricao,
                ordem=ordem, criado_em=datetime.now().isoformat())
    db.session.add(foto)
    db.session.commit()
    registrar_atividade("foto_enviada",
                        f"Enviou foto no cômodo '{comodo.nome}'",
                        obra_id=comodo.obra_id)
    return jsonify({
        "id": foto.id,
        "url": url_for("relatorios.servir_foto", filename=rel_path),
        "descricao": descricao,
    })


@bp.route("/comodo/<int:comodo_id>/reordenar", methods=["POST"])
@login_required
def reordenar_fotos(comodo_id):
    """Recebe os ids das fotos na nova ordem e atualiza o campo 'ordem'.

    Essa ordem é a que vale no relatório PowerPoint e no .zip.
    """
    comodo = comodo_do_usuario(comodo_id)
    ids = request.form.get("ordem", "")
    id_list = [int(x) for x in ids.split(",") if x.strip().isdigit()]
    fotos = {f.id: f for f in comodo.fotos}
    for posicao, foto_id in enumerate(id_list):
        if foto_id in fotos:
            fotos[foto_id].ordem = posicao
    db.session.commit()
    return jsonify({"ok": True})


@bp.route("/foto/<int:foto_id>/descricao", methods=["POST"])
@login_required
def atualizar_descricao(foto_id):
    foto = foto_do_usuario(foto_id)
    foto.descricao = (request.form.get("descricao") or "").strip()
    db.session.commit()
    return jsonify({"ok": True})


@bp.route("/foto/<int:foto_id>/excluir", methods=["POST"])
@login_required
def excluir_foto(foto_id):
    foto = foto_do_usuario(foto_id)
    _remover_foto_arquivo(foto.arquivo)
    db.session.delete(foto)
    db.session.commit()
    return jsonify({"ok": True})


@bp.route("/uploads/<path:filename>")
@login_required
def servir_foto(filename):
    # Garante que só o dono (ou admin) veja a imagem: o 1º trecho do caminho
    # é o id da obra (ex.: "12/34/uuid.jpg").
    try:
        obra_id = int(filename.split("/")[0])
    except (ValueError, IndexError):
        abort(404)
    obra_do_usuario(obra_id)   # aborta 404 se não for o dono
    _foto_path_or_404(filename)
    # Cache de 1h no navegador: revisitar a obra carrega as fotos do cache
    # (rápido no celular). Edições por IA já fazem cache-bust na hora.
    return send_from_directory(UPLOAD_DIR, filename, max_age=3600)


# ---------------------------------------------------------------------------
# Edição de fotos por IA (OpenAI)
# ---------------------------------------------------------------------------
@bp.route("/foto/<int:foto_id>/editar-ia", methods=["POST"])
@login_required
@limiter.limit("20 per hour")
def editar_foto_ia(foto_id):
    if not ia_disponivel():
        return jsonify({"erro": "A edição por IA não está configurada. "
                        "Crie um arquivo .env com OPENAI_API_KEY."}), 400
    foto = foto_do_usuario(foto_id)
    prompt = (request.form.get("prompt") or "").strip()
    if not prompt:
        return jsonify({"erro": "Descreva a alteração desejada."}), 400

    origem = _foto_path_or_404(foto.arquivo)
    if not os.path.exists(origem):
        return jsonify({"erro": "Arquivo da foto não encontrado."}), 404

    try:
        novos_bytes = editar_imagem(origem, prompt)
    except Exception as e:  # noqa: BLE001
        return jsonify({"erro": str(e)}), 502

    pv_rel = preview_rel(foto.arquivo)
    with open(_foto_path_or_404(pv_rel), "wb") as fh:
        fh.write(novos_bytes)

    return jsonify({
        "preview_url": url_for("relatorios.servir_foto", filename=pv_rel),
        "original_url": url_for("relatorios.servir_foto", filename=foto.arquivo),
    })


@bp.route("/foto/<int:foto_id>/aplicar-edicao", methods=["POST"])
@login_required
def aplicar_edicao_ia(foto_id):
    foto = foto_do_usuario(foto_id)
    preview_abs = _foto_path_or_404(preview_rel(foto.arquivo))
    if not os.path.exists(preview_abs):
        return jsonify({"erro": "Nenhuma prévia para aplicar."}), 400
    # Substitui o arquivo original pela versão editada (mantém o mesmo nome).
    os.replace(preview_abs, _foto_path_or_404(foto.arquivo))
    registrar_atividade("foto_ia", "Aplicou edição por IA em uma foto",
                        obra_id=foto.comodo.obra_id)
    return jsonify({
        "ok": True,
        "url": url_for("relatorios.servir_foto", filename=foto.arquivo),
    })


@bp.route("/foto/<int:foto_id>/descartar-edicao", methods=["POST"])
@login_required
def descartar_edicao_ia(foto_id):
    foto = foto_do_usuario(foto_id)
    preview_abs = _foto_path_or_404(preview_rel(foto.arquivo))
    try:
        os.remove(preview_abs)
    except (OSError, ValueError):
        pass
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Geração de relatório (.pptx) e download das fotos (.zip)
# ---------------------------------------------------------------------------
@bp.route("/obra/<int:obra_id>/relatorio.pptx")
@login_required
def baixar_relatorio(obra_id):
    obra = obra_do_usuario(obra_id)
    label = periodo_label(request.args.get("mes"), request.args.get("ano"))

    comodos = []
    for grupo in comodos_com_fotos(obra):
        fotos = []
        for f in grupo["fotos"]:
            try:
                path = foto_abs_path(f.arquivo)
            except ValueError:
                continue
            fotos.append({"path": path, "descricao": f.descricao})
        if fotos:
            comodos.append({"nome": grupo["comodo"].nome,
                            "geral": grupo["comodo"].geral, "fotos": fotos})

    out = io.BytesIO()
    tmp_path = os.path.join(DATA_DIR, f"_relatorio_{uuid.uuid4().hex}.pptx")
    try:
        gerar_relatorio(TEMPLATE_PATH, tmp_path,
                        {"nome": obra.nome, "endereco": obra.endereco},
                        label, comodos)
        with open(tmp_path, "rb") as fh:
            out.write(fh.read())
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
    out.seek(0)

    registrar_atividade("relatorio_gerado",
                        f"Gerou o relatório da obra '{obra.nome}' ({label})",
                        obra_id=obra.id)
    nome_arq = f"Relatorio_{slugify(obra.nome)}_{slugify(label)}.pptx"
    return send_file(
        out, as_attachment=True, download_name=nome_arq,
        mimetype=("application/vnd.openxmlformats-officedocument"
                  ".presentationml.presentation"))


@bp.route("/obra/<int:obra_id>/fotos.zip")
@login_required
def baixar_fotos_zip(obra_id):
    obra = obra_do_usuario(obra_id)
    buffer = io.BytesIO()
    obra_slug = slugify(obra.nome, "obra")
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for grupo in comodos_com_fotos(obra):
            comodo_slug = slugify(grupo["comodo"].nome, "comodo")
            for i, f in enumerate(grupo["fotos"], start=1):
                try:
                    src = foto_abs_path(f.arquivo)
                except ValueError:
                    continue
                if not os.path.exists(src):
                    continue
                desc = slugify(f.descricao, "")[:40]
                base = f"{i:02d}_{desc}" if desc else f"{i:02d}"
                arcname = f"{obra_slug}/{comodo_slug}/{base}.jpg"
                zf.write(src, arcname)
    buffer.seek(0)
    return send_file(buffer, as_attachment=True,
                     download_name=f"Fotos_{obra_slug}.zip",
                     mimetype="application/zip")
