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
RUN chmod +x /app/start.sh
RUN chmod +x /usr/local/bin/task-agent

CMD ["/app/start.sh"]
