"""Funções utilitárias compartilhadas (imagens, nomes de arquivo, etc.)."""

import os
import re
import unicodedata
from datetime import datetime

from PIL import Image, ImageOps

from config import JPEG_QUALITY, MAX_IMG_SIDE, MESES, UPLOAD_DIR


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


def preview_rel(arquivo):
    """Caminho relativo da prévia da edição por IA (ainda não aplicada)."""
    return arquivo + ".preview.jpg"


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


def comodos_com_fotos(obra):
    grupos = []
    for c in sorted(obra.comodos, key=lambda c: (c.ordem, c.id)):
        fotos = sorted(c.fotos, key=lambda f: (f.ordem, f.id))
        grupos.append({"comodo": c, "fotos": fotos})
    return grupos


def remover_arquivos_da_obra(obra):
    for c in obra.comodos:
        for f in c.fotos:
            try:
                os.remove(foto_abs_path(f.arquivo))
            except OSError:
                pass


def destino_seguro(target):
    """Evita redirecionamento aberto: só aceita caminhos internos."""
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return None
