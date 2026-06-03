"""
Stewart Construtora — Sistema de Relatórios Fotográficos de Obras.

Aplicação web (celular + computador) para:
  - cadastrar obras;
  - anexar fotos organizadas por cômodo, com descrição (legenda) em cada foto;
  - gerar o relatório mensal em PowerPoint (.pptx) usando o template oficial;
  - baixar todas as fotos em um .zip com uma pasta por cômodo.
"""

import io
import os
import re
import sqlite3
import unicodedata
import uuid
import zipfile
from datetime import datetime

from flask import (Flask, abort, g, jsonify, redirect, render_template,
                   request, send_file, send_from_directory, url_for)
from PIL import Image, ImageOps

from pptx_generator import gerar_relatorio

# Suporte opcional a fotos HEIC/HEIF (iPhone), se a lib estiver disponível.
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except Exception:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
DB_PATH = os.path.join(DATA_DIR, "stewart.db")
TEMPLATE_PATH = os.path.join(BASE_DIR, "template", "TEMPLATE_STEWART.pptx")

MAX_IMG_SIDE = 2000          # redimensiona fotos para no máx. 2000px (lado maior)
JPEG_QUALITY = 85

MESES = ["JANEIRO", "FEVEREIRO", "MARÇO", "ABRIL", "MAIO", "JUNHO", "JULHO",
         "AGOSTO", "SETEMBRO", "OUTUBRO", "NOVEMBRO", "DEZEMBRO"]

os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024 * 1024  # 64 MB por upload


# ---------------------------------------------------------------------------
# Banco de dados (SQLite)
# ---------------------------------------------------------------------------
SCHEMA = """
CREATE TABLE IF NOT EXISTS obras (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    nome      TEXT NOT NULL,
    endereco  TEXT DEFAULT '',
    criado_em TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS comodos (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    obra_id INTEGER NOT NULL REFERENCES obras(id) ON DELETE CASCADE,
    nome    TEXT NOT NULL,
    ordem   INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS fotos (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    comodo_id INTEGER NOT NULL REFERENCES comodos(id) ON DELETE CASCADE,
    arquivo   TEXT NOT NULL,
    descricao TEXT DEFAULT '',
    ordem     INTEGER NOT NULL DEFAULT 0,
    criado_em TEXT NOT NULL
);
"""


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.executescript(SCHEMA)
    db.commit()
    db.close()


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def slugify(text, default="item"):
    text = unicodedata.normalize("NFKD", text or "")
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text).strip()
    text = re.sub(r"[\s_-]+", "_", text)
    return text or default


def periodo_label(mes, ano):
    try:
        return f"{MESES[int(mes) - 1]} {int(ano)}"
    except (ValueError, IndexError, TypeError):
        agora = datetime.now()
        return f"{MESES[agora.month - 1]} {agora.year}"


def foto_abs_path(arquivo):
    # O caminho é guardado sempre com "/"; convertemos para o separador do SO.
    return os.path.join(UPLOAD_DIR, *arquivo.split("/"))


def processar_imagem(file_storage, dest_path):
    """Corrige orientação (EXIF), redimensiona e salva como JPEG."""
    img = Image.open(file_storage.stream)
    img = ImageOps.exif_transpose(img)
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    elif img.mode == "L":
        img = img.convert("RGB")
    img.thumbnail((MAX_IMG_SIDE, MAX_IMG_SIDE), Image.LANCZOS)
    img.save(dest_path, "JPEG", quality=JPEG_QUALITY, optimize=True)


def obra_or_404(obra_id):
    obra = get_db().execute("SELECT * FROM obras WHERE id=?",
                            (obra_id,)).fetchone()
    if obra is None:
        abort(404)
    return obra


def comodos_com_fotos(obra_id):
    db = get_db()
    comodos = db.execute(
        "SELECT * FROM comodos WHERE obra_id=? ORDER BY ordem, id",
        (obra_id,)).fetchall()
    resultado = []
    for c in comodos:
        fotos = db.execute(
            "SELECT * FROM fotos WHERE comodo_id=? ORDER BY ordem, id",
            (c["id"],)).fetchall()
        resultado.append({"comodo": c, "fotos": fotos})
    return resultado


# ---------------------------------------------------------------------------
# Páginas
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    db = get_db()
    obras = db.execute("""
        SELECT o.*,
               (SELECT COUNT(*) FROM fotos f
                  JOIN comodos c ON c.id = f.comodo_id
                 WHERE c.obra_id = o.id) AS total_fotos,
               (SELECT COUNT(*) FROM comodos c WHERE c.obra_id = o.id)
                 AS total_comodos
          FROM obras o
      ORDER BY o.id DESC
    """).fetchall()
    return render_template("index.html", obras=obras)


@app.route("/obra/<int:obra_id>")
def obra_detail(obra_id):
    obra = obra_or_404(obra_id)
    grupos = comodos_com_fotos(obra_id)
    agora = datetime.now()
    return render_template("obra.html", obra=obra, grupos=grupos,
                           meses=MESES, mes_atual=agora.month,
                           ano_atual=agora.year)


# ---------------------------------------------------------------------------
# API — Obras
# ---------------------------------------------------------------------------
@app.route("/obras", methods=["POST"])
def criar_obra():
    nome = (request.form.get("nome") or "").strip()
    endereco = (request.form.get("endereco") or "").strip()
    if not nome:
        return redirect(url_for("index"))
    db = get_db()
    db.execute(
        "INSERT INTO obras (nome, endereco, criado_em) VALUES (?,?,?)",
        (nome, endereco, datetime.now().isoformat()))
    db.commit()
    return redirect(url_for("index"))


@app.route("/obra/<int:obra_id>/editar", methods=["POST"])
def editar_obra(obra_id):
    obra_or_404(obra_id)
    nome = (request.form.get("nome") or "").strip()
    endereco = (request.form.get("endereco") or "").strip()
    db = get_db()
    db.execute("UPDATE obras SET nome=?, endereco=? WHERE id=?",
               (nome, endereco, obra_id))
    db.commit()
    return redirect(url_for("obra_detail", obra_id=obra_id))


@app.route("/obra/<int:obra_id>/excluir", methods=["POST"])
def excluir_obra(obra_id):
    obra_or_404(obra_id)
    db = get_db()
    # remove arquivos físicos
    fotos = db.execute("""
        SELECT f.arquivo FROM fotos f
          JOIN comodos c ON c.id = f.comodo_id
         WHERE c.obra_id=?""", (obra_id,)).fetchall()
    for f in fotos:
        try:
            os.remove(foto_abs_path(f["arquivo"]))
        except OSError:
            pass
    db.execute("DELETE FROM obras WHERE id=?", (obra_id,))
    db.commit()
    return redirect(url_for("index"))


# ---------------------------------------------------------------------------
# API — Cômodos
# ---------------------------------------------------------------------------
@app.route("/obra/<int:obra_id>/comodos", methods=["POST"])
def criar_comodo(obra_id):
    obra_or_404(obra_id)
    nome = (request.form.get("nome") or "").strip()
    if not nome:
        return jsonify({"erro": "Nome do cômodo é obrigatório"}), 400
    db = get_db()
    ordem = db.execute(
        "SELECT COALESCE(MAX(ordem), 0) + 1 AS o FROM comodos WHERE obra_id=?",
        (obra_id,)).fetchone()["o"]
    cur = db.execute(
        "INSERT INTO comodos (obra_id, nome, ordem) VALUES (?,?,?)",
        (obra_id, nome, ordem))
    db.commit()
    return jsonify({"id": cur.lastrowid, "nome": nome})


@app.route("/comodo/<int:comodo_id>/renomear", methods=["POST"])
def renomear_comodo(comodo_id):
    nome = (request.form.get("nome") or "").strip()
    if not nome:
        return jsonify({"erro": "Nome inválido"}), 400
    db = get_db()
    db.execute("UPDATE comodos SET nome=? WHERE id=?", (nome, comodo_id))
    db.commit()
    return jsonify({"ok": True, "nome": nome})


@app.route("/comodo/<int:comodo_id>/excluir", methods=["POST"])
def excluir_comodo(comodo_id):
    db = get_db()
    fotos = db.execute("SELECT arquivo FROM fotos WHERE comodo_id=?",
                       (comodo_id,)).fetchall()
    for f in fotos:
        try:
            os.remove(foto_abs_path(f["arquivo"]))
        except OSError:
            pass
    db.execute("DELETE FROM comodos WHERE id=?", (comodo_id,))
    db.commit()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# API — Fotos
# ---------------------------------------------------------------------------
@app.route("/comodo/<int:comodo_id>/fotos", methods=["POST"])
def upload_foto(comodo_id):
    db = get_db()
    comodo = db.execute("SELECT * FROM comodos WHERE id=?",
                        (comodo_id,)).fetchone()
    if comodo is None:
        return jsonify({"erro": "Cômodo não encontrado"}), 404

    file = request.files.get("foto")
    if file is None or file.filename == "":
        return jsonify({"erro": "Nenhum arquivo enviado"}), 400

    descricao = (request.form.get("descricao") or "").strip()
    # Já inicia a legenda com o nome do cômodo, no modelo "Sala - ".
    if not descricao:
        descricao = f"{comodo['nome']} - "
    # Caminho relativo guardado SEMPRE com "/" (compatível com URL e Windows).
    rel_dir = f"{comodo['obra_id']}/{comodo_id}"
    abs_dir = os.path.join(UPLOAD_DIR, str(comodo["obra_id"]), str(comodo_id))
    os.makedirs(abs_dir, exist_ok=True)
    nome_arquivo = f"{uuid.uuid4().hex}.jpg"
    rel_path = f"{rel_dir}/{nome_arquivo}"

    try:
        processar_imagem(file, os.path.join(abs_dir, nome_arquivo))
    except Exception as e:  # noqa: BLE001
        return jsonify({"erro": f"Falha ao processar imagem: {e}"}), 400

    ordem = db.execute(
        "SELECT COALESCE(MAX(ordem),0)+1 AS o FROM fotos WHERE comodo_id=?",
        (comodo_id,)).fetchone()["o"]
    cur = db.execute(
        """INSERT INTO fotos (comodo_id, arquivo, descricao, ordem, criado_em)
           VALUES (?,?,?,?,?)""",
        (comodo_id, rel_path, descricao, ordem, datetime.now().isoformat()))
    db.commit()
    return jsonify({
        "id": cur.lastrowid,
        "url": url_for("servir_foto", filename=rel_path),
        "descricao": descricao,
    })


@app.route("/foto/<int:foto_id>/descricao", methods=["POST"])
def atualizar_descricao(foto_id):
    descricao = (request.form.get("descricao") or "").strip()
    db = get_db()
    db.execute("UPDATE fotos SET descricao=? WHERE id=?", (descricao, foto_id))
    db.commit()
    return jsonify({"ok": True})


@app.route("/foto/<int:foto_id>/excluir", methods=["POST"])
def excluir_foto(foto_id):
    db = get_db()
    foto = db.execute("SELECT * FROM fotos WHERE id=?", (foto_id,)).fetchone()
    if foto is None:
        return jsonify({"erro": "Foto não encontrada"}), 404
    try:
        os.remove(foto_abs_path(foto["arquivo"]))
    except OSError:
        pass
    db.execute("DELETE FROM fotos WHERE id=?", (foto_id,))
    db.commit()
    return jsonify({"ok": True})


@app.route("/uploads/<path:filename>")
def servir_foto(filename):
    return send_from_directory(UPLOAD_DIR, filename)


# ---------------------------------------------------------------------------
# Geração de relatório (.pptx) e download das fotos (.zip)
# ---------------------------------------------------------------------------
@app.route("/obra/<int:obra_id>/relatorio.pptx")
def baixar_relatorio(obra_id):
    obra = obra_or_404(obra_id)
    label = periodo_label(request.args.get("mes"), request.args.get("ano"))

    comodos = []
    for grupo in comodos_com_fotos(obra_id):
        fotos = [{"path": foto_abs_path(f["arquivo"]),
                  "descricao": f["descricao"]} for f in grupo["fotos"]]
        if fotos:
            comodos.append({"nome": grupo["comodo"]["nome"], "fotos": fotos})

    out = io.BytesIO()
    tmp_path = os.path.join(DATA_DIR, f"_relatorio_{uuid.uuid4().hex}.pptx")
    gerar_relatorio(TEMPLATE_PATH, tmp_path,
                    {"nome": obra["nome"], "endereco": obra["endereco"]},
                    label, comodos)
    with open(tmp_path, "rb") as fh:
        out.write(fh.read())
    os.remove(tmp_path)
    out.seek(0)

    nome_arq = f"Relatorio_{slugify(obra['nome'])}_{slugify(label)}.pptx"
    return send_file(
        out, as_attachment=True, download_name=nome_arq,
        mimetype=("application/vnd.openxmlformats-officedocument"
                  ".presentationml.presentation"))


@app.route("/obra/<int:obra_id>/fotos.zip")
def baixar_fotos_zip(obra_id):
    obra = obra_or_404(obra_id)
    buffer = io.BytesIO()
    obra_slug = slugify(obra["nome"], "obra")
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for grupo in comodos_com_fotos(obra_id):
            comodo_slug = slugify(grupo["comodo"]["nome"], "comodo")
            for i, f in enumerate(grupo["fotos"], start=1):
                src = foto_abs_path(f["arquivo"])
                if not os.path.exists(src):
                    continue
                desc = slugify(f["descricao"], "")[:40]
                base = f"{i:02d}_{desc}" if desc else f"{i:02d}"
                arcname = f"{obra_slug}/{comodo_slug}/{base}.jpg"
                zf.write(src, arcname)
    buffer.seek(0)
    return send_file(buffer, as_attachment=True,
                     download_name=f"Fotos_{obra_slug}.zip",
                     mimetype="application/zip")


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
