# --- ZenNotes web bundle build ---
# Builds the Vite/PWA web client; the static bundle is later embedded into the
# Go server binary. Runs on the native build platform (no QEMU needed).
FROM node:22-alpine AS zennotes-web
ARG ZENNOTES_REPO_URL=https://github.com/ZenNotes/zennotes.git
ARG ZENNOTES_REPO_REF=1e3a6f104c2c9a39a7cc6c5243387e3d21957fe2
RUN apk add --no-cache git
WORKDIR /src
RUN git init . && \
    git remote add origin "$ZENNOTES_REPO_URL" && \
    git fetch --depth 1 origin "$ZENNOTES_REPO_REF" && \
    git checkout FETCH_HEAD
RUN npm ci --no-audit --no-fund --loglevel=error
RUN npm run build --workspace @zennotes/web

# --- ZenNotes server build ---
# Pure-Go static binary (CGO off) with the web bundle embedded via go:embed.
FROM golang:1.22-alpine AS zennotes-server
ARG ZENNOTES_REPO_URL=https://github.com/ZenNotes/zennotes.git
ARG ZENNOTES_REPO_REF=1e3a6f104c2c9a39a7cc6c5243387e3d21957fe2
RUN apk add --no-cache git
WORKDIR /src
RUN git init . && \
    git remote add origin "$ZENNOTES_REPO_URL" && \
    git fetch --depth 1 origin "$ZENNOTES_REPO_REF" && \
    git checkout FETCH_HEAD
WORKDIR /src/apps/server
RUN go mod download
COPY --from=zennotes-web /src/apps/web/dist/ /src/apps/server/web/dist/
ENV CGO_ENABLED=0 GOOS=linux GOFLAGS=-trimpath
RUN go build -ldflags="-s -w" -o /out/zennotes-server ./cmd/zennotes-server

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

ARG TASK_MANAGER_REPO_URL=https://github.com/Adictya/taskwarrior-task-management-skill.git
ARG TASK_MANAGER_REPO_REF=29bcf556d6fcbd1c584b323f96e703de4da2362a

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl ca-certificates git gh nodejs npm taskwarrior && \
    rm -rf /var/lib/apt/lists/*

RUN npm install -g @google/gemini-cli

ENV HOME=/data \
    HERMES_HOME=/data/.hermes \
    UV_HTTP_TIMEOUT=120 \
    UV_CONCURRENT_DOWNLOADS=4

ADD https://api.github.com/repos/Adictya/hermes-agent/commits/custom /tmp/hermes-agent-latest-commit.json
RUN git clone --depth 1 --branch custom https://github.com/Adictya/hermes-agent.git /tmp/hermes-agent && \
    cd /tmp/hermes-agent && \
    uv pip install --system --no-cache -e ".[all]"

COPY requirements.txt /app/requirements.txt
RUN uv pip install --system --no-cache -r /app/requirements.txt

RUN git init /opt/taskwrrior-task-manager && \
    git -C /opt/taskwrrior-task-manager remote add origin "$TASK_MANAGER_REPO_URL" && \
    git -C /opt/taskwrrior-task-manager fetch --depth 1 origin "$TASK_MANAGER_REPO_REF" && \
    git -C /opt/taskwrrior-task-manager checkout FETCH_HEAD && \
    rm -rf /opt/taskwrrior-task-manager/.git

RUN mkdir -p /data/.hermes

COPY server.py /app/server.py
COPY proxy.py /app/proxy.py
COPY templates/ /app/templates/
COPY start.sh /app/start.sh
COPY task-agent /usr/local/bin/task-agent
COPY --from=zennotes-server /out/zennotes-server /usr/local/bin/zennotes-server
RUN chmod +x /app/start.sh
RUN chmod +x /usr/local/bin/task-agent
RUN chmod +x /usr/local/bin/zennotes-server

CMD ["/app/start.sh"]
