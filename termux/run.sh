#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKSPACE="$(dirname "$SCRIPT_DIR")"

echo "Starting JupyterLab..."
echo "Access at http://$(ip route get 1 2>/dev/null | awk '{print $7; exit}'):8888"

exec proot-distro run mlops-jupyterlab \
  --bind "$WORKSPACE":/workspace \
  --env JUPYTER_TOKEN="" \
  --env ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}" \
  --env OPENAI_API_KEY="${OPENAI_API_KEY:-}" \
  --env GH_TOKEN="${GH_TOKEN:-}" \
  --env GITHUB_TOKEN="${GITHUB_TOKEN:-}" \
  --env OPENROUTER_API_KEY="${OPENROUTER_API_KEY:-}"
