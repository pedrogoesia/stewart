"""Fluxo completo da ferramenta de relatórios, como o dono.

Upload de foto real (com redimensionamento), legenda, geração do .pptx a
partir do template oficial e download do .zip — o caminho feliz de ponta a
ponta que a equipe usa todo mês.
"""

import io
import os
import zipfile

from PIL import Image

from config import UPLOAD_DIR
from extensions import db
from models import Foto

from .conftest import login


def _png(largura, altura):
    buf = io.BytesIO()
    Image.new("RGB", (largura, altura), "gray").save(buf, format="PNG")
    buf.seek(0)
    return buf


def test_upload_redimensiona_e_salva(client, dados):
    login(client, "b@teste.com")
    comodo_id = dados["comodo"].id
    resp = client.post(f"/comodo/{comodo_id}/fotos",
                       data={"foto": (_png(3000, 1500), "grande.png")},
                       content_type="multipart/form-data")
    assert resp.status_code == 200
    corpo = resp.get_json()
    # Sem legenda enviada, inicia com o prefixo do cômodo.
    assert corpo["descricao"] == "Sala - "

    foto = db.session.get(Foto, corpo["id"])
    caminho = os.path.join(UPLOAD_DIR, foto.arquivo)
    assert os.path.exists(caminho)
    with Image.open(caminho) as img:
        assert img.format == "JPEG"          # sempre convertida para .jpg
        assert max(img.size) == 2000         # lado maior reduzido ao padrão
        assert img.size == (2000, 1000)      # proporção preservada


def test_atualizar_descricao_persiste(client, dados):
    login(client, "b@teste.com")
    foto_id = dados["foto"].id
    resp = client.post(f"/foto/{foto_id}/descricao",
                       data={"descricao": "Sala - pintura concluída"})
    assert resp.status_code == 200
    db.session.expire_all()
    assert db.session.get(Foto, foto_id).descricao == "Sala - pintura concluída"


def test_relatorio_pptx_e_gerado(client, dados):
    login(client, "b@teste.com")
    resp = client.get(f"/obra/{dados['obra'].id}/relatorio.pptx",
                      query_string={"mes": "7", "ano": "2026"})
    assert resp.status_code == 200
    assert resp.mimetype.endswith("presentation")
    assert resp.data[:2] == b"PK"            # .pptx é um zip OOXML válido
    assert len(resp.data) > 10_000           # template + capa + slide de fotos


def test_zip_traz_uma_pasta_por_comodo(client, dados):
    login(client, "b@teste.com")
    resp = client.get(f"/obra/{dados['obra'].id}/fotos.zip")
    assert resp.status_code == 200
    with zipfile.ZipFile(io.BytesIO(resp.data)) as zf:
        nomes = zf.namelist()
    assert len(nomes) == 1
    # Estrutura: <obra>/<comodo>/<nn>_<descricao>.jpg
    assert nomes[0] == "Obra_do_B/Sala/01_Sala_parede.jpg"
