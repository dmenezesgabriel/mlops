# E2E verification sweep — 2026-10-05

End-to-end smoke of the shipped fixes' real surfaces: full apps, real
containers, notebooks executed via nbclient inside the compose stack, human-level
checks on the outputs. Ephemeral working document — findings live in `gaps.md`,
work items in `backlog.md`.

## Environment

- Docker 29.8.0, host ufw active. Compose stack rebuilt this session:
  `mlops-moto-1`, `mlops-trino-1`, `mlops-athena-1` (all healthy),
  `mlops-jupyterlab-1` on external `mlops_net` (recreated — it had vanished).
- Images built: `mlops-jupyterlab`, `athena-local`, `mlops-diagrams-prod`,
  `mlops-manim-prod`, `sagemaker-scikit-learn:{train,inference}`.
- Disk: root fs hit 100% mid-build; `docker builder prune` freed ~17 GB.

## Verified working end-to-end

| Surface | How exercised | Result |
|---|---|---|
| AF-80 labels on real containers | notebook train + transform runs inside jupyterlab | train container carries `sagemaker.local=true` + `role=job`; transform container carries `role=serve` — both stamped by `harden_service` on the SDK's `command` marker |
| sagemaker-local pipeline | `batch_transform.ipynb` via nbclient in jupyterlab kernel (`/opt/mlops-venv`) | `EXECUTED OK in 38s` with serving path reachable (see G-187): cleanup → fit (train container exit 0) → transform (inference container, gunicorn real requests) → **20 predictions** in `data/output/x_test.csv.out` |
| diagrams | `mlops-diagrams-prod` container render | real 68 KB `mlops_lifecycle.png` — clusters, LR layout, feedback edge correct |
| ssg build | `uv run ssg build --config site/site.manual.yaml` (manual mode — transformers absent on host) | 24 pages (12 en + 12 pt-BR); translated title, `highlight-token` spans, KaTeX on 6 pages, ipynb→table render all present in real output |
| ssg preview + reload | `ssg preview` server + edit probe | serves `MLOps Lab` on :8000 after initial build; doc edit → watcher rebuild → new content served; marker removed cleanly after |
| jupyterlab stack | `docker compose up` + entrypoint `uv sync` | venv provisioned at `/opt/mlops-venv` (sagemaker 2.257.1, nbclient, ipykernel); moto/Athena/Trino endpoints all answer |
| CLI named-error boundary (AF-72 class) | `videos bogus-quality` / missing transformers on ssg | clean one-line stderr + rc=1, no traceback — the error boundary does its job on real failures |

## New defects found by this sweep (all in `gaps.md`)

- **G-185** (S1) — `videos-linter` IndexError under cv2 5.0.0:
  `convexityDefects` now returns `(N,4)`; `d[0][3]` assumed `(N,1,4)`. All 9
  bias-variance scenes rendered, validation killed the produce. → AF-87.
- **G-186** (S3) — `make render-video` could never build: root `.dockerignore`
  re-includes only athena-local sources. → AF-88, **shipped** this session
  (`libs/videos/Dockerfile.dockerignore`).
- **G-187** (S1) — in-container serving unreachable via gateway: Docker's
  same-bridge DNAT exclusion + host INPUT drops mlops_net→gateway traffic.
  `transform()`/`deploy()` hang in `_wait_for_serving_container` on this stack.
  The AF-80 `role=serve` label is what makes the fix possible (resolve the
  labelled container's network IP). → AF-89.
- **G-188** (S3) — trino's host publish owns 8080, collides with
  `serving_port`. First transform run died at `Bind failed`. → AF-90.
- **G-189** (S3) — `mlops_net` is `external: true` yet the only
  `docker network create mlops_net` instruction lives in
  `libs/athena-local/README.md`; cold `docker compose up` fails with the
  cryptic "declared as external, but could not be found". → AF-91.
- **G-190** (S3) — the "offline" stack isn't: `fetch_california_housing`
  downloads `cal_housing_py3.pkz` from figshare into `~/scikit_learn_data`
  at first notebook run; a fresh volume + no internet fails mid-cell. → AF-91.

## Surfaces still not covered

- `training.ipynb` / `pipeline.ipynb` (only `batch_transform.ipynb` executed).
- `deploy()`/predictor surface (same G-187 path as transform).
- `athena-local` parity notebook + `ml_specialization` notebooks.
- `ssg` preview on the transformers path (manual mode only — host has no
  transformers; the fallback chain is untested).
- `nyc_taxi` full pipeline run (moto + trino + athena up, not exercised).
