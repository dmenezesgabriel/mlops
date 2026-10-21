# ADR-0015 — per-image dependency locks for the SageMaker image family

- Status: Accepted (user decision)
- Date: 2026-10-21
- Supersedes: ADR-0014 §4, only the sentence "The SageMaker images keep their
  explicit direct pins and move to a hashed export of the same workspace lock."

## Context

ADR-0014 §4 required the nine SageMaker images to install a hashed export of
the workspace `uv.lock`. Measured 2026-10-21, that export cannot reproduce
these images:

- `uv.lock` has no `xgboost`, `lightgbm`, `catboost` or `sagemaker-training`
  entry, because the workspace packages do not depend on them; the image
  stacks live only in the Dockerfiles.
- The workspace lock pins `numpy 2.4.6`, `flask 3.1.3` and `gunicorn 26.0.0`,
  while the images pin `numpy 1.26.4`, `flask 3.1.1` and `gunicorn 23.0.0`.
  Exporting the workspace would silently upgrade the image runtime.
- A per-package export (`uv export --package <project>`) contains only that
  project's dependencies, not the serving stack or the SageMaker toolkit, so
  it would need a synthetic package per image anyway.

The images are therefore a separate runtime contract from the library and
test environment. They still need transitive pins and hashes (G-343), because
the Dockerfiles pin only their direct requirements.

## Decision

1. Each image owns one checked-in pair under
   `libs/sagemaker-local/docker/requirements/`:
   `standard`, `california-train`, `california-inference`,
   `electricity-train`, `electricity-inference`, `telco-train`,
   `telco-inference`, `wine-train`, `wine-inference`.
   The `.in` file keeps the image's explicit direct versions; the `.txt` file
   is the generated transitive lock.
2. Locks are generated with
   `uv pip compile --generate-hashes --emit-build-options --python-version 3.12 --python-platform x86_64-manylinux_2_28`
   via `make -C libs/sagemaker-local lock-requirements`. The target is the
   only supported way to regenerate them, so the platform and Python version
   stay identical across the nine files.
3. Exactly two requirements are sdist-only on PyPI for CPython 3.12:
   `sagemaker-training==5.1.1` (a direct training requirement) and
   `inotify-simple==1.2.1` (its transitive dependency); both are absent from
   the inference images. Train and standard locks allow them with
   `--no-binary`; inference locks use `--only-binary :all:`. Because
   `--emit-build-options` writes those flags into the lock, `pip` enforces
   the policy instead of trusting a reviewer to spot a stray source build.
   pip applies build options in file order, so a trailing
   `--only-binary :all:` cancels the per-package exceptions; the train locks
   therefore keep only the two `--no-binary` lines, and their hash set is
   already wheel-only for every other package.
4. `sagemaker-training` builds a C extension, so `build-essential` stays in
   the training images. It is not in the inference images.
5. Images install with
   `python -m pip install --no-cache-dir --require-hashes --requirement <lock>`.
6. The build context stays `libs/sagemaker-local/docker`, the directory that
   already holds the shared `serve` assets and now the locks. No repo-root
   context is needed.
7. The base digest, OCI labels and root-user exemption from ADR-0014 apply
   unchanged.

## Consequences

- A direct pin change is a two-line diff: the `.in` edit and the regenerated
  `.txt`. A transitive change is a reviewable lock diff.
- The nine locks are independent, so a framework upgrade in one image cannot
  move another image's runtime.
- Hash checking covers the locked requirements, not the PEP 517 build
  requirements pip resolves to build `sagemaker-training` from its sdist.
  That residual gap is tracked as G-352 and is the reason the training
  images keep a compiler.
- `uv.lock` remains the workspace lock for libraries and tests. It is not an
  input to these images, and the two are allowed to pin different versions.
- Regeneration is manual; Dependabot's `docker` ecosystem bumps the image
  bases, while Python lock refreshes are a deliberate command. A stale lock
  is detected by `make -C libs/sagemaker-local lock-requirements` producing a
  diff.

## References

- ADR-0014 — container images: pinned bases, minimal runtime,
  platform-mandated users.
- `docs/audits/container-images-2026-10-18.md` — measured image audit.
- pip docs, "Hash-checking mode": `--require-hashes` requires every
  requirement to be pinned with `==` and hashed.
- uv docs, `uv pip compile`: `--generate-hashes`, `--emit-build-options`,
  `--python-platform`.
