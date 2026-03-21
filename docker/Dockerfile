FROM node:22-bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl jq python3 python3-venv ripgrep fd-find openssh-client \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

RUN npm install -g @anthropic-ai/claude-code

RUN git config --system user.name "MaxWolf-01-agent" \
    && git config --system user.email "MaxWolf-01-agent@noreply" \
    && git config --system credential.helper '!f() { echo "password=$GH_TOKEN"; }; f'

# Use node user (uid 1000, matches host)
RUN usermod -d /home/agent -l agent node && mv /home/node /home/agent
USER agent
WORKDIR /work
ENV HOME=/home/agent
ENV CLAUDE_CONFIG_DIR=/home/agent/.claude

ENTRYPOINT ["claude", "--dangerously-skip-permissions"]
