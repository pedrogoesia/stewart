"""Funções utilitárias compartilhadas (imagens, nomes de arquivo, etc.)."""

import os
import re
import unicodedata
from datetime import datetime

from PIL import Image, ImageOps, UnidentifiedImageError
from werkzeug.utils import safe_join

from config import (ALLOWED_IMAGE_FORMATS, JPEG_QUALITY, MAX_IMAGE_PIXELS,
                    MAX_IMG_SIDE, MESES, UPLOAD_DIR)

Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS


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
    partes = (arquivo or "").replace("\\", "/").split("/")
    if not partes or any(p in ("", ".", "..") for p in partes):
        raise ValueError("Caminho de foto invalido.")
    caminho = safe_join(UPLOAD_DIR, *partes)
    if caminho is None:
        raise ValueError("Caminho de foto fora da pasta de uploads.")
    return caminho


def preview_rel(arquivo):
    """Caminho relativo da prévia da edição por IA (ainda não aplicada)."""
    return arquivo + ".preview.jpg"


def processar_imagem(file_storage, dest_path):
    """Corrige orientação (EXIF), redimensiona e salva como JPEG."""
    try:
        file_storage.stream.seek(0)
        img = Image.open(file_storage.stream)
        if img.format not in ALLOWED_IMAGE_FORMATS:
            raise ValueError("Formato de imagem nao permitido.")
    except UnidentifiedImageError as exc:
        raise ValueError("Arquivo enviado nao e uma imagem valida.") from exc
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
            except (OSError, ValueError):
                pass


def destino_seguro(target):
    """Evita redirecionamento aberto: só aceita caminhos internos."""
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return None
