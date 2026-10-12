# ADR-0002 — `athena` runs as its own container + its own port

- Status: Accepted (user decision)
- Date: 2026-09-19

## Context

Deployment options for the emulator: (a) extend the moto server to also serve
Athena ops, or (b) run an independent service on its own port. moto's Athena
dispatch is coupled to moto's core (`research_repos/moto/moto/core/responses.py:462-464`
parses `X-Amz-Target`; `moto/athena/urls.py:3` binds athena URL bases), and
moto serves S3/Glue/STS on port 5000 in this repo's `docker-compose.yml`.
Athena-local does **not** reuse moto internals (ADR-0008), so colocating inside
the moto process would force us to fork moto.

Clients can already split endpoints cleanly:
- awswrangler reads `athena_endpoint_url` at
  `research_repos/aws-sdk-pandas/awswrangler/_utils.py:259-260` (resolution
  `:255-280`);
- boto3/botocore honor per-service `AWS_ENDPOINT_URL_ATHENA`;
- terraform-provider-aws honors `AWS_ENDPOINT_URL_ATHENA` (AWS SDK Go v2
  custom endpoints).

## Decision

- `athena` = its own container, own published port **5001**, running uvicorn
  on `athena_local.main:app`, added to `docker-compose.yml` on `mlops_net`.
- `trino` = its own container; moto keeps serving S3/Glue/STS on port 5000.
- Only Athena traffic is routed to `:5001`. S3/Glue traffic from clients
  continues to moto `:5000` as today.

## Consequences

- Clean lifecycle: restarting `athena`/`trino` never disturbs S3/Glue data.
- We own dispatch/errors entirely (ADR-0008) with zero moto coupling.
- The two extra consume of memory/ports is accepted for parity.
- In-memory state (ADR-0003) dies with the `athena` container — documented.