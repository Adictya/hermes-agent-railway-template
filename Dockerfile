FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

ARG TASK_MANAGER_REPO_URL=https://github.com/Adictya/taskwarrior-task-management-skill.git
ARG TASK_MANAGER_REPO_REF=29bcf556d6fcbd1c584b323f96e703de4da2362a

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl ca-certificates ffmpeg git nodejs taskwarrior && \
    rm -rf /var/lib/apt/lists/*

RUN git clone --depth 1 https://github.com/NousResearch/hermes-agent.git /tmp/hermes-agent && \
    cd /tmp/hermes-agent && \
    uv pip install --system --no-cache -e ".[all]" && \
    rm -rf /tmp/hermes-agent/.git

RUN git init /opt/taskwrrior-task-manager && \
    git -C /opt/taskwrrior-task-manager remote add origin "$TASK_MANAGER_REPO_URL" && \
    git -C /opt/taskwrrior-task-manager fetch --depth 1 origin "$TASK_MANAGER_REPO_REF" && \
    git -C /opt/taskwrrior-task-manager checkout FETCH_HEAD && \
    rm -rf /opt/taskwrrior-task-manager/.git

RUN mkdir -p /data/.hermes

COPY start.sh /app/start.sh
COPY task-agent /usr/local/bin/task-agent
RUN chmod +x /app/start.sh
RUN chmod +x /usr/local/bin/task-agent

ENV HOME=/data
ENV HERMES_HOME=/data/.hermes

CMD ["/app/start.sh"]
