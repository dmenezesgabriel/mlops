# athena-local

Local AWS Athena emulator: an Apache Trino-backed service (dockerized, port
5001) with JSON-1.1 protocol parity for boto3, awswrangler, AWS CLI, and
terraform-provider-aws, co-located with moto for S3/Glue/STS. See
`docs/athena-emulator/architecture.md` for the building-block view and the
wire-protocol evidence index.

## Running with docker compose

The emulator joins the existing stack on the external `mlops_net` network:

```bash
docker network create mlops_net          # once, if the network doesn't exist
docker compose up -d moto trino athena
```

`athena` waits for `trino` to become healthy (`/v1/info`) before starting.
Once up:

- athena — `http://localhost:5001`; `GET /health` → `{"status": "ok"}`
- moto — `http://localhost:5000` (S3, Glue, STS)
- trino — `http://localhost:8080` (Hive connector → moto Glue, native S3 →
  moto S3)

The `jupyterlab` compose service is already wired: `AWS_ENDPOINT_URL` → moto
and `AWS_ENDPOINT_URL_ATHENA` → the emulator.

For development outside docker, run from this directory:

```bash
uv run uvicorn athena_local.main:app --port 5001
```

## Server configuration

| Variable | Default | Compose value |
|---|---|---|
| `ATHENA_LOCAL_TRINO_URL` | `http://localhost:8080` | `http://trino:8080` |
| `ATHENA_MOTO_ENDPOINT_URL` | `http://127.0.0.1:5000` | `http://moto:5000` |
| `ATHENA_LOCAL_MAX_CONCURRENT_QUERIES` | `4` | unset |
| `ATHENA_LOCAL_MAX_RETAINED_EXECUTIONS` | `10000` | unset |

`ATHENA_LOCAL_TRINO_URL` is where statements are submitted;
`ATHENA_MOTO_ENDPOINT_URL` backs Glue catalog reads and S3 result-artifact
writes. `ATHENA_LOCAL_MAX_CONCURRENT_QUERIES` bounds how many executions run
against Trino at once; extra executions stay QUEUED, like real Athena.
`ATHENA_LOCAL_MAX_RETAINED_EXECUTIONS` bounds how many finished executions
query history keeps: oldest terminal records evict first, and records also
expire 45 days after completion, matching Athena's documented query-history
retention.

## Pointing consumers at it

Only Athena traffic goes to `:5001`; S3/Glue calls stay on moto. Any static
credentials work (`test`/`test`, `AWS_DEFAULT_REGION=us-east-1`) — the
emulator does not authenticate, but the SDKs require the fields to sign
requests.

**boto3 / botocore**

```python
import boto3

athena = boto3.client("athena", endpoint_url="http://localhost:5001")
```

or export `AWS_ENDPOINT_URL_ATHENA=http://localhost:5001` — the per-service
variable overrides global `AWS_ENDPOINT_URL` for Athena only (ADR-0002), so
`AWS_ENDPOINT_URL=http://localhost:5000` can stay pointed at moto.

**awswrangler**

```python
import awswrangler as wr

wr.config.athena_endpoint_url = "http://localhost:5001"
```

or set `WR_ATHENA_ENDPOINT_URL` / `AWS_ENDPOINT_URL_ATHENA` in the
environment.

**AWS CLI**

```bash
aws athena list-work-groups --endpoint-url http://localhost:5001
```

or `AWS_ENDPOINT_URL_ATHENA`.

**terraform-provider-aws** (AWS SDK for Go v2 honors the same per-service
variable):

```bash
export AWS_ENDPOINT_URL_ATHENA=http://localhost:5001
export AWS_ENDPOINT_URL=http://localhost:5000   # S3/Glue → moto
```

## State and reset

Control-plane state is in-memory only (ADR-0003): workgroups, named queries,
prepared statements, data catalogs, and query executions are lost when the
`athena` container stops; the `primary` workgroup is re-seeded at boot.
Query result artifacts (`*.csv`/`*.txt`/manifests) are written to moto S3,
so they survive an `athena` restart — but moto itself is in-memory, so
restarting the whole stack resets everything. There is no reset HTTP API;
restart the container.

## Development

`make -C libs/athena-local quality` runs the full gate (ruff, pyright,
pytest + coverage, radon/xenon, deptry, bandit/vulture/semgrep). Integration
tests reach a running stack through `ATHENA_LOCAL_TEST_ENDPOINT` (the 70-op
parity loop) and `ATHENA_LOCAL_TRINO_URL` / `ATHENA_LOCAL_MOTO_ENDPOINT_URL`
(consumer-suite harness). Design decisions live in
`docs/athena-emulator/architecture.md` and `docs/athena-emulator/adr/`.
