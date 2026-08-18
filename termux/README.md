# Termux Setup

Run the MLOps JupyterLab environment on Android using [proot-distro](https://github.com/termux/proot-distro). No root, no Docker daemon, no kernel modules.

## Prerequisites

- Android 10 or newer
- [Termux](https://f-droid.org/en/packages/com.termux/) installed from **F-Droid** (not Google Play — the Play version is outdated)
- Device and desktop on the same local network (WiFi)

## Setup

Run each command inside Termux, one at a time.

### Install packages

```sh
pkg update -y && pkg upgrade -y
pkg install -y proot-distro openssh curl git
```

### SSH

```sh
ssh-keygen -A
```

Set a password:

```sh
passwd
```

Ensure password auth is enabled:

```sh
grep -q "^PasswordAuthentication yes" "$PREFIX/etc/ssh/sshd_config" || echo "PasswordAuthentication yes" >> "$PREFIX/etc/ssh/sshd_config"
```

Start sshd:

```sh
sshd
```

Find your connection info:

```sh
echo "username: $(whoami)"
echo "ip: $(ip route get 1 | awk '{print $7; exit}')"
echo "port: 8022"
```

From your desktop:

```sh
ssh -p 8022 <username>@<device-ip>
```

### GitHub CLI

Download and install `gh`:

```sh
GH_VERSION=$(curl -s https://api.github.com/repos/cli/cli/releases/latest | grep '"tag_name"' | cut -d '"' -f 4 | tr -d 'v') && \
curl -sL "https://github.com/cli/cli/releases/download/v${GH_VERSION}/gh_${GH_VERSION}_linux_arm64.tar.gz" | tar xz -C /tmp && \
cp "/tmp/gh_${GH_VERSION}_linux_arm64/bin/gh" "$PREFIX/bin/" && \
chmod +x "$PREFIX/bin/gh" && \
rm -rf "/tmp/gh_${GH_VERSION}_linux_arm64"
```

Authenticate:

```sh
gh auth login
```

### Clone and run

```sh
gh repo clone <your-org>/<your-repo>
cd <your-repo>/termux
./build.sh
```

`build.sh` builds the proot-distro image and installs it. On the first run it downloads the base image and installs all dependencies — this takes ~10-15 minutes. Subsequent builds reuse the layer cache.

### Set API keys

Export your AI provider keys before running. Only the providers you use need a key:

```sh
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-..."
export OPENROUTER_API_KEY="sk-or-..."
```

To persist keys across sessions, add them to `~/.bashrc` or `~/.zshrc` in Termux.

### Start JupyterLab

```sh
./run.sh
```

Open `http://<device-ip>:8888` in your browser.

## Keeping sshd alive

Termux is an Android app — Android can kill it when backgrounded.

**Wakelock** (quick fix): Swipe down on the Termux notification and tap "Acquire wakelock".

**Termux:Boot** (recommended): Install [Termux:Boot](https://f-droid.org/en/packages/com.termux.boot/) from F-Droid, then:

```sh
mkdir -p ~/.termux/boot
cat > ~/.termux/boot/start-sshd.sh << 'EOF'
#!/data/data/com.termux/files/usr/bin/sh
termux-wake-lock
sshd
EOF
chmod +x ~/.termux/boot/start-sshd.sh
```

## Building the image

```sh
./build.sh
```

This runs `proot-distro build` which pulls the base image (`ghcr.io/astral-sh/uv:python3.12-trixie-slim` for arm64) and executes each Dockerfile instruction under proot. No Docker daemon required. After building, it automatically removes any previous install and installs the fresh image.

### Changes from the root Dockerfile

| Change | Reason |
|---|---|
| Removed `RUN --mount=type=cache` | BuildKit-only feature, rejected by proot-distro |
| Added `gcc` build step for `skip_getifaddrs.c` | Android SELinux blocks `getifaddrs()` — libzmq (used by Jupyter kernels) crashes without this stub |
| `COPY docker/` → `COPY termux/entrypoint.sh` | Uses the modified entrypoint with `LD_PRELOAD` |

Build time is ~10-15 minutes on a modern phone. Subsequent builds are faster thanks to proot-distro's layer cache.

## Running the container

```sh
./run.sh
```

This runs `proot-distro run` which:

- Starts the container with the entrypoint (builds the JupyterLab venv, syncs the monorepo, launches JupyterLab)
- Bind-mounts the project root as `/workspace`
- Passes API keys from your environment (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `OPENROUTER_API_KEY`, `GH_TOKEN`, `GITHUB_TOKEN`)

JupyterLab starts on `http://0.0.0.0:8888` — accessible from any device on your network.

### Manage sessions

```sh
# List running containers
proot-distro ps

# Stop a session
proot-distro kill <container-name>

# Rebuild from scratch (wipes all data inside the container)
proot-distro reset mlops-jupyterlab
```

## Troubleshooting

### Jupyter kernels fail to start (`Permission denied`)

This is the `getifaddrs` bug on Android 13+. The `LD_PRELOAD=/opt/skip_getifaddrs.so` in the entrypoint handles it. If you still see this:

```sh
# Inside the container, verify the stub is loaded
LD_PRELOAD=/opt/skip_getifaddrs.so python -c "import psutil; print(psutil.net_if_addrs())"
```

### Port 8888 already in use

```sh
# Find what's using it
lsof -i :8888

# Kill it or use a different port in run.sh (--env JUPYTER_PORT=8889)
```

### `proot-distro` command not found

```sh
pkg install proot-distro
```

### Build fails on `npm install`

npm sometimes runs out of memory on low-RAM devices. Retry — the layer cache means it won't restart from scratch.

### Container has no network inside

Proot shares the host network stack. If DNS doesn't resolve:

```sh
# Inside the container, check resolv.conf
cat /etc/resolv.conf

# If empty, set it manually
echo "nameserver 8.8.8.8" > /etc/resolv.conf
```

### SSH password auth fails

Open `$PREFIX/etc/ssh/sshd_config` and ensure:

```
PasswordAuthentication yes
ChallengeResponseAuthentication no
UsePAM yes
```

Restart sshd: `pkill sshd && sshd`.

### Debugging sshd

```sh
pgrep -l sshd       # check if running
pkill sshd && sshd  # restart
sshd -De            # verbose foreground mode
```
