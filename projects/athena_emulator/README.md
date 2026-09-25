# athena_emulator — parity validation notebooks

Tutorial-style runnable examples that drive common boto3 / awswrangler flows
against the compose Athena emulator stack — each feature gets explanatory
markdown plus a canonical usage cell displaying real output — and record a
measured `PASS`/`FAIL`/`GAP` per feature for gap discovery. They are not an
integration test suite: integrated consumer tests live in
`libs/athena-local/tests/`; the nbclient hook here only re-executes the
notebooks to regenerate evidence.

Stack (`docker-compose.yml`, network `mlops_net`): `athena` :5001 (emulator),
`trino` :8080 (query engine), `moto` :5000 (S3/Glue), `jupyterlab` :8888.

## Layout

- `notebooks/NN_*.ipynb` — one notebook per surface; committed executed
  outputs are the evidence
- `notebooks/_evidence.py` — shared evidence recorder
- `parity/NN_*.md` — per-notebook matrix fragments (generated)
- `PARITY.md` — consolidated matrix (generated; do not edit by hand)
- `tests/test_notebooks.py` — nbclient execution hook (`integration` marker,
  skips when the emulator is unreachable)

## Run

In the JupyterLab UI (<http://localhost:8888>, token disabled), or headless
from the host:

```bash
docker compose exec jupyterlab /opt/mlops-venv/bin/python \
  -m pytest projects/athena_emulator/tests -m integration
```

Against the published ports from the host:

```bash
uv run pytest projects/athena_emulator/tests -m integration
```

Endpoint env vars (`AWS_ENDPOINT_URL`, `AWS_ENDPOINT_URL_ATHENA`) resolve to
compose hosts in-container and fall back to localhost ports on the host, so
the same notebook runs in both places.
