#!/usr/bin/env bash
# Inicia o sistema de relatórios da Stewart.
set -e
cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"

# Cria/ativa ambiente virtual e instala dependências na primeira execução.
if [ ! -d ".venv" ]; then
  echo "==> Criando ambiente virtual (.venv) e instalando dependências..."
  "$PYTHON" -m venv .venv
  ./.venv/bin/pip install --upgrade pip >/dev/null
  ./.venv/bin/pip install -r requirements.txt
fi

echo "==> Iniciando o servidor em http://0.0.0.0:${PORT:-5000}"
echo "    (acesse pelo computador ou pelo celular na mesma rede Wi-Fi)"
exec ./.venv/bin/python app.py
