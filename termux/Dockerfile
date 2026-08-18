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
        git \
        nodejs \
        npm \
        vim \
        zsh \
        gcc \
        libc6-dev \
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

# npm global install is skipped: proot's link2symlink emulation breaks
# npm's rename() syscall during cache operations. These AI tools are not
# required for JupyterLab. To add them later, run inside the container:
#   npm install --global opencode-ai @agentclientprotocol/claude-agent-acp

COPY termux/skip_getifaddrs.c /tmp/skip_getifaddrs.c
RUN gcc -shared -fPIC -o /opt/skip_getifaddrs.so /tmp/skip_getifaddrs.c \
    && rm /tmp/skip_getifaddrs.c \
    && apt-get purge -y --auto-remove gcc \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --depth 1 https://github.com/ohmyzsh/ohmyzsh.git /home/jupyter/.oh-my-zsh \
    && git clone --depth 1 https://github.com/zsh-users/zsh-autosuggestions /home/jupyter/.oh-my-zsh/custom/plugins/zsh-autosuggestions \
    && git clone --depth 1 https://github.com/zsh-users/zsh-syntax-highlighting /home/jupyter/.oh-my-zsh/custom/plugins/zsh-syntax-highlighting \
    && chown -R jupyter:jupyter /home/jupyter/.oh-my-zsh

COPY --chown=jupyter:jupyter docker/.zshrc /home/jupyter/.zshrc

RUN git config --system user.email "jupyter@localhost" \
    && git config --system user.name "Jupyter"

COPY docker/settings/ /home/jupyter/.config/jupyter/

RUN mkdir -p /opt/jupyterlab /opt/mlops-venv /tmp/pycache /tmp/uv-cache \
        /home/jupyter/.local/share/jupyter /home/jupyter/.local/share/uv \
    && chown -R jupyter:jupyter /opt/jupyterlab /opt/mlops-venv /tmp/pycache /tmp/uv-cache /home/jupyter/.local

COPY docker/jupyterlab-requirements.txt /opt/jupyterlab-requirements.txt

COPY --chown=jupyter:jupyter termux/entrypoint.sh /opt/entrypoint.sh
RUN chmod +x /opt/entrypoint.sh

USER jupyter

ENTRYPOINT ["/opt/entrypoint.sh"]
