# ADR-0014 — container images: pinned bases, minimal runtime, platform-mandated users

- Status: Accepted (user decision)
- Date: 2026-10-18

## Context

The repo builds 14 images from 14 Dockerfiles and runs 9 third-party service
images through 5 compose files. Only one of them follows a written standard
today: the Athena emulator pins every stage by digest
(`docker/athena/Dockerfile:3,5,16`), installs a lock with
`pip --require-hashes` (`:14,25`), drops to `USER 10001:10001` (`:31`) and
declares an image `HEALTHCHECK` (`:33`) — documented at
`docs/architecture/athena-local.md:208-216`. Every other Dockerfile picks its
base by mutable tag, installs unlocked with `pip`, and runs as whatever user
the base ships. No decision records whether that standard should spread, so
each new Dockerfile re-decides it.

The images are not one class:

- **Our own services and task images** — `athena`, `jupyterlab` (root
  `Dockerfile`), `videos` (`libs/videos/Dockerfile`), `diagrams`
  (`libs/diagrams/Dockerfile`). We own the runtime, so privilege dropping,
  locking and base pinning are open choices.
- **SageMaker train/inference images** — `libs/sagemaker-local/docker/Dockerfile`
  plus four project pairs. The platform owns the contract: "SageMaker AI
  expects all containers to run with root users. Create your container so that
  it uses only root users. When SageMaker AI runs your container, users that do
  not have root-level access can cause permissions issues", model artifacts are
  copied to a read-only `/opt/ml/model`, and "You can't use the `tini`
  initializer as your entry point" (AWS, *Custom Inference Code with Hosting
  Services*). Copying Athena's `USER` here would break the contract.
- **Third-party service images in compose** — moto, Trino, Kafka, Flink. We do
  not build them; we choose the reference pin and the resource cap.

The host is shared (AGENTS "Host resources"): an idle emulator stack can
commit memory it never uses, which is why Trino already carries a 4 GiB cap
(`docker-compose.yml:42-48`) and the streaming stack pins all three JVMs.

## Decision

1. **Pin every base reference by digest.** Each `FROM` and compose `image:`
   carries `name:tag@sha256:<manifest-list digest>`, keeping the readable tag
   before the `@`. Docker build best practices: a tag "may resolve to a
   different underlying version", while by pinning the digest "you're
   guaranteed to always use the same image version, even if a publisher
   replaces the tag with a new image". Because that also "opt[s] out of
   automated security fixes", base images are bumped by Dependabot with
   `package-ecosystem: docker`, which the same page recommends.
2. **Multi-stage only when a build toolchain is needed.** Compilers and build
   caches stay in a builder stage; a stage is added only when a measurement
   shows the toolchain is present and unused at runtime.
3. **Non-root `USER` with an explicit UID/GID for our own services.** Docker's
   `USER` guidance: "If a service can run without privileges, use `USER`", with
   an explicit UID/GID because image-time UID assignment is non-deterministic.
   **SageMaker images are exempt and stay root** for the platform reason quoted
   above; each carries an inline comment citing that requirement so the
   exemption is not re-litigated.
4. **Python dependencies come from a lock with hashes.** Where a lockfile
   exists, export it and install with `pip --require-hashes` — the Athena
   pattern. The SageMaker images keep their explicit direct pins and move to a
   hashed export of the same workspace lock. `uv` itself is copied from the
   pinned `ghcr.io/astral-sh/uv` image rather than installed from PyPI during
   the build (uv docs: "install uv by copying the binary from the official
   distroless Docker image"; "best practice to pin to a specific uv version",
   and a digest "is considered best practice in environments that require
   reproducible builds").
5. **Runtime installs are non-editable.** uv's editable default is a
   development mode; the runtime image installs the package non-editable so it
   does not depend on the source tree (uv docs, "Non-editable installs").
6. **OCI annotations on every built image.** One `LABEL` block sets
   `org.opencontainers.image.title`, `.source`, `.revision` and `.licenses`
   (OCI image-spec annotations), so `docker inspect` ties a running image to a
   commit and a licence.
7. **A Dockerfile `HEALTHCHECK` only where the image is a long-lived service
   without a platform check.** SageMaker's `GET /ping` is the platform health
   contract, so those images declare none; compose services that need ordered
   startup declare the check in compose.
8. **Exec-form `CMD`/`ENTRYPOINT`, and `init: true` only when the entrypoint
   does not `exec` its server.** Docker's best practices: the exec form
   "enables it to receive signals like `SIGTERM` and `SIGKILL`". An init wrapper
   is never a blanket default, and never on a SageMaker image (quoted above).
9. **Every compose service carries a measured `deploy.resources.limits.memory`.**
   JVM heaps are pinned to fit inside the cap (`KAFKA_HEAP_OPTS`, Flink
   `*.memory.process.size`), following the Trino/Kafka/Flink precedent.
10. **Distroless and musl bases are rejected by default.** The serving images
    link the glibc OpenMP runtime and the SageMaker toolkit assumes glibc;
    Alpine would force source builds. Revisit only for an image measured to
    carry neither.

## Consequences

- Rebuilds are reproducible for a given commit; a base bump becomes an
  explicit, reviewable PR instead of a silent tag move.
- The 13 unpinned `FROM` lines and 9 compose `image:` references are migrated
  one image family per session, each verified by a build plus the family's
  existing tests.
- Two things stop being treated as defects: SageMaker images running as root
  (platform contract) and the Athena image as the reference for everything
  else.
- Size and CVE work that needs measurement first — removing `build-essential`
  from the training images, the `libgomp1` variance between project images — is
  recorded as suspects and acted on only once measured.
- `termux/Dockerfile` builds a proot rootfs, not a container-runtime image; it
  follows these rules only where they apply.
