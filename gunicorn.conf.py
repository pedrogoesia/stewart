"""Configuração do Gunicorn (servidor de produção).

Workers "gthread": cada worker atende várias requisições ao mesmo tempo em
threads. O trabalho do portal é quase todo I/O (banco, OpenAI, disco), então
threads escalam bem mesmo com pouca CPU — com 2 workers × 16 threads o site
atende 32 requisições simultâneas, em vez de 2 do modo síncrono antigo (onde
duas chamadas de IA em paralelo travavam o site inteiro).

Ajustes por variável de ambiente, sem mexer no código:
  WEB_CONCURRENCY   → nº de processos (padrão 2; suba junto com o plano/CPU)
  GUNICORN_THREADS  → threads por processo (padrão 16)
"""

import os

bind = "0.0.0.0:" + os.environ.get("PORT", "10000")

worker_class = "gthread"
workers = int(os.environ.get("WEB_CONCURRENCY", "2"))
threads = int(os.environ.get("GUNICORN_THREADS", "16"))

# IA das atas pode levar até ~60s; margem folgada sem segurar thread para sempre.
timeout = 120
# Mantém conexões keep-alive um pouco mais (o Render fica atrás de proxy).
keepalive = 5

# Recicla cada worker de tempos em tempos: protege contra vazamento de memória
# em processos de vida longa. O jitter evita que todos reiniciem juntos.
max_requests = 1000
max_requests_jitter = 100

# Logs de acesso/erro no stdout/stderr (o Render coleta de lá).
accesslog = "-"
errorlog = "-"
