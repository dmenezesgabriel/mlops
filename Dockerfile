FROM ghcr.io/astral-sh/uv:python3.12-trixie-slim

ENV SHELL=/usr/bin/zsh \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPYCACHEPREFIX=/tmp/pycache \
    JUPYTER_PLATFORM_DIRS=1 \
    UV_CACHE_DIR=/tmp/uv-cache \
    UV_PROJECT_ENVIRONMENT=/opt/mlops-venv

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        docker-cli \
        docker-compose \
        git \
        nodejs \
        npm \
        procps \
        vim \
        zsh \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
        -o /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && printf 'deb [arch=%s signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main\n' "$(dpkg --print-architecture)" \
        > /etc/apt/sources.list.d/github-cli.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends gh \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --shell /usr/bin/zsh --uid 1000 jupyter

RUN --mount=type=cache,target=/root/.npm npm install --global \
        @agentclientprotocol/claude-agent-acp@0.68.0 \
        opencode-ai@1.18.18

RUN git clone --depth 1 https://github.com/ohmyzsh/ohmyzsh.git /home/jupyter/.oh-my-zsh \
    && git clone --depth 1 https://github.com/zsh-users/zsh-autosuggestions /home/jupyter/.oh-my-zsh/custom/plugins/zsh-autosuggestions \
    && git clone --depth 1 https://github.com/zsh-users/zsh-syntax-highlighting /home/jupyter/.oh-my-zsh/custom/plugins/zsh-syntax-highlighting \
    && chown -R jupyter:jupyter /home/jupyter/.oh-my-zsh

COPY --chown=jupyter:jupyter docker/.zshrc /home/jupyter/.zshrc

RUN git config --system user.email "jupyter@localhost" \
    && git config --system user.name "Jupyter"

COPY --chown=jupyter:jupyter docker/settings/ /home/jupyter/.config/jupyter/

RUN mkdir -p /opt/jupyterlab /opt/mlops-venv /tmp/pycache /tmp/uv-cache \
        /home/jupyter/.local/share/jupyter /home/jupyter/.local/share/uv \
    && chown -R jupyter:jupyter /opt/jupyterlab /opt/mlops-venv /tmp/pycache /tmp/uv-cache /home/jupyter/.local

COPY docker/jupyterlab-requirements.txt /opt/jupyterlab-requirements.txt

USER jupyter

COPY docker/entrypoint.sh /opt/entrypoint.sh

ENTRYPOINT ["/opt/entrypoint.sh"]
