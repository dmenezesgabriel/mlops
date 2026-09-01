#!/usr/bin/env bash
set -euo pipefail

# REPO_PATH must be a path identical on host and container so sagemaker local
# mode job/serving containers (spawned by the host docker daemon) can mount
# source_dir/container_root. compose passes SAGEMAKER_LOCAL_REPO_PATH=${PWD}.
REPO_PATH="${SAGEMAKER_LOCAL_REPO_PATH:-/workspace}"

if [ ! -f /opt/jupyterlab/bin/jupyter ]; then
    uv venv /opt/jupyterlab
fi

uv pip install --python /opt/jupyterlab/bin/python -r /opt/jupyterlab-requirements.txt

cd "$REPO_PATH"
uv sync --all-packages --dev --extra notebooks
uv run ipython kernel install --user --env VIRTUAL_ENV /opt/mlops-venv --name=mlops
uv run python -c "import json, pathlib; p = pathlib.Path.home() / '.local/share/jupyter/kernels/mlops/kernel.json'; d = json.loads(p.read_text()); d.setdefault('metadata', {})['debugger'] = True; p.write_text(json.dumps(d, indent=1))"

uv run python -c "
import json, pathlib
for p in [
    pathlib.Path('/opt/mlops-venv/share/jupyter/kernels/python3/kernel.json'),
    pathlib.Path('/opt/jupyterlab/share/jupyter/kernels/python3/kernel.json'),
]:
    if p.exists():
        d = json.loads(p.read_text())
        d['argv'] = ['/opt/mlops-venv/bin/python' if a == 'python' else a for a in d['argv']]
        p.write_text(json.dumps(d, indent=1))
"

exec /opt/jupyterlab/bin/jupyter lab \
    --ip=0.0.0.0 \
    --port=8888 \
    --no-browser \
    --ServerApp.root_dir="$REPO_PATH/projects" \
    --IdentityProvider.token="${JUPYTER_TOKEN:-}"
