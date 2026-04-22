FROM nvidia/cuda:12.1.1-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv curl bash && \
    ln -sf /usr/bin/python3 /usr/bin/python && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip3 install --no-cache-dir --upgrade pip && \
    pip3 install --no-cache-dir -r requirements.txt && \
    python3 -m spacy download en_core_web_sm

COPY . .

# Entrypoint runs alembic upgrade head (idempotent, seeds tracked companies
# on first boot) before delegating to the process defined by the service.
# Strip CRLF first so Windows clones don't break bash parsing.
RUN sed -i 's/\r$//' /app/docker-entrypoint.sh && \
    chmod +x /app/docker-entrypoint.sh

EXPOSE 8000

# Explicit `bash` avoids needing the executable bit to survive a host
# bind-mount (./backend:/app in docker-compose will shadow the +x we set
# at build time on some platforms).
ENTRYPOINT ["bash", "/app/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
