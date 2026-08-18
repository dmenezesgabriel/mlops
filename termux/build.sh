#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "Building mlops-jupyterlab image..."
proot-distro build -t mlops-jupyterlab -f "$SCRIPT_DIR/Dockerfile" "$PROJECT_ROOT"

echo "Installing mlops-jupyterlab..."
proot-distro remove mlops-jupyterlab 2>/dev/null || true
proot-distro install mlops-jupyterlab:latest

echo "Done. Run with: bash $(dirname "$0")/run.sh"
