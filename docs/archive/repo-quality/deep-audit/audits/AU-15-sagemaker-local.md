# AU-15 — sagemaker-local audit (2026-10-04)

MA-6 first item. Target: `libs/sagemaker-local` — **619 LOC** in 4 modules
(`config.py` 123, `session.py` 140, `patches.py` 317, `images.py` 39 —
backlog holds) + empty `__init__.py`, plus image assets `docker/serve_app.py`
(137, flask+joblib hosting runtime baked into the image) and `docker/serve`
(37, gunicorn entry). Test suite: 57 tests / 901 LOC / 8 files, AAA-shaped,
24.4 s. Gates baseline: pyright strict 0 on `src`, ruff clean, radon cc clean,
xenon clean, deptry clean, vulture/bandit clean on `src`. `pytest --cov`
TOTAL 91% over 785 stmts — **no editable-dep pollution** (`.venv` outside
rootdir): `src/` files 100/94/92% (patches 94%, session 92%), `docker/
serve_app.py` 60% (28 miss), floor 75. Consumers are notebooks only:
`config_from_env()` + `make_local_session`/`make_local_pipeline_session` in
`projects/sagemaker_*/notebooks/*.ipynb`; `cleanup_stale_serving_containers()`
in all 4 `batch_transform.ipynb`. No Python-module consumers.

SDK baseline verified against installed `sagemaker==2.257.1`: patch seams
match — `_SageMakerContainer._compose(self, detached=False)` (image.py:787,
called at :230/:307/:363 always after `_generate_compose_file` writes the
YAML — correct seam), `_get_compose_cmd_prefix` is `@staticmethod` (image.py:139),
`get_docker_host` imported by name into `utils`/`entities`/`local_session`
(all 3 sites patched), `LocalSession.__init__` takes `sagemaker_config`
(local_session.py:655), `LocalSession.config` setter validates against
`SAGEMAKER_PYTHON_SDK_LOCAL_MODE_CONFIG_SCHEMA` and propagates to
`sagemaker_runtime_client.config` (measured: `serving_port=9999` reaches the
runtime client).

## Surface inventory

| Module | SLOC | Public symbols | Entry |
|---|---|---|---|
| `config.py` | 123 | `LocalModeConfig` (frozen dataclass), `config_from_env`, `MOTO_ACCOUNT_ID`, `DEFAULT_ROLE_ARN` | ★ `config_from_env` (notebooks) |
| `session.py` | 140 | `make_local_session`, `make_local_pipeline_session` | ★ notebook session factories |
| `patches.py` | 317 | `inject_network`, `harden_service`, `tolerant_compose_cmd_prefix`, `apply_compose_patches`, `resolve_gateway_from_routes`, `apply_docker_host_patch`, `cleanup_stopped_containers`, `cleanup_stale_serving_containers`, `reset_all` | ★ `cleanup_*` (notebooks), patch installers via factories |
| `images.py` | 39 | `dockerfile_dir`, `build_image` | ★ `build_image` (Makefile/integ) |
| `docker/serve_app.py` | 137 | flask `app`, `create_app`, `model_fn/input_fn/predict_fn/output_fn` defaults | ★ `serve` cmd → `/ping` `/execution-parameters` `/invocations` |
| `docker/serve` | 37 | gunicorn `main` (workers=1, timeout=60) | ★ container entry |

## Callgraph

```
config_from_env() [config.py:88] ★
  ├─ _env(name) → os.environ["SAGEMAKER_LOCAL_*"]   [:84]
  ├─ missing-check → ValueError                     [:103-111]
  └─ LocalModeConfig(...) → __post_init__           [:62]
      └─ _validate_endpoint + bucket/port guards    [:74-81,:64-71]

make_local_session(cfg) [session.py:26] ★  (pipeline variant :55 — same preamble)
  ├─ apply_compose_patches(cfg)                     [patches.py:110]
  │   ├─ guard `_original_compose is not None` → return   [:113]
  │   ├─ captures SDK originals + installs:         [:117-134]
  │   │   patched_compose(self, detached=False)     [:122]
  │   │   ├─ _original_compose(self, detached) → cmd
  │   │   ├─ path = cmd[cmd.index("-f")+1]          [:125]
  │   │   └─ _rewrite_compose_file(path, cfg)       [:138]
  │   │       ├─ yaml.safe_load → dict               [:139]
  │   │       ├─ inject_network(compose, network)    [:48] per-service setdefault
  │   │       ├─ harden_service(service) ∀services   [:64,:144] → label on EVERY svc
  │   │       └─ yaml.dump rewrite                   [:146]
  │   └─ patched_prefix → tolerant_compose_cmd_prefix [:79]
  │       ├─ check_output(["docker","compose","version"]) [:93]  (CalledProcessError only)
  │       └─ shutil.which("docker-compose")         [:102]
  ├─ apply_docker_host_patch(force=False)           [patches.py:195]
  │   ├─ _running_inside_container → /.dockerenv    [:183]
  │   └─ installs gateway_getter at 3 import sites  [:221-227]
  │       └─ _gateway_from_proc → /proc/net/route   [:174]
  │           → resolve_gateway_from_routes         [:152]
  │           → fallback() = SDK get_docker_host    [:212,:219]
  ├─ _boto_session(cfg) → boto3.Session             [:86]
  ├─ _s3_client → client("s3", endpoint_url=…)      [:94-97]
  ├─ _ensure_bucket → head_bucket / create_bucket   [:100-125]
  ├─ LocalSession(..., sagemaker_config=OPT_OUT)    [:45]
  │   └─ SDK ctor → load_local_mode_config(~/.sagemaker/config.yaml)
  │       → config setter → runtime client
  └─ _apply_local_mode_config → session.config =    [:128]
      {local:{serving_port, local_code, container_root?}}

build_image(tag) [images.py:21] ★
  └─ _run_subprocess(["docker","build","-t",tag,"."], cwd=dockerfile_dir(), no timeout)

cleanup_stopped_containers()  [:262] → _list(status="exited") → _remove_containers
cleanup_stale_serving_containers() [:275] → _list(None) → _remove_containers ★
  _list → docker container ls -a --filter label=sagemaker.local=true  [:231]
  _remove → docker rm -f *ids (check=False) → returns len(ids)        [:249]

reset_all() [:292] → restores _compose + _get_compose_cmd_prefix (as plain fn) [:298-302]
                   → restores get_docker_host at 3 sites                       [:305-316]

serve_app (gunicorn workers=1 → single-threaded by construction):
  GET /ping → "" 200                            [:101]
  GET /execution-parameters → {MultiRecord,6MB} [:106]
  POST /invocations [:123]
    → _resolve("input_fn", default) [:46] → _load_inference_module
      (importlib from /opt/ml/code/$SAGEMAKER_PROGRAM) [:30]
    → _model_instance → _resolve("model_fn", joblib.load) [:93,:53]
    → _resolve("predict_fn", model.predict) [:67]
    → _resolve("output_fn", default) — csv via np.array2string [:83]
```

## Boundary table

| Boundary | Where | Faked as | Test |
|---|---|---|---|
| docker CLI (`compose version`, `container ls`, `rm`, `build`) | patches.py:93,243,253; images.py:28 | `FakeRunner` + monkeypatched `check_output`/`which` | test_patches, test_images |
| `/proc/net/route`, `/.dockerenv` | patches.py:38-39,176,184 | `tmp_path` constants monkeypatch | `fake_host_env` fixture |
| compose file read/write | patches.py:125,139,146 | `tmp_path` via fake original `_compose` | `compose_project` fixture |
| boto3 → S3/STS endpoint | session.py:44,87-97 | `_FakeS3Client` / `LiveMotoServer` (real moto) | test_session / test_session_moto |
| sagemaker SDK private API | patches.py:117-118,208-225,296-316 | real SDK + `reset_all` fixture | test_patches |
| env vars `SAGEMAKER_LOCAL_*` | config.py:84-85 | `monkeypatch.setenv` | test_config |
| ambient SDK config (`~/.sagemaker/`, `*_CONFIG_OVERRIDE` env, user-config-dir files) | SDK ctors via session.py:45,76 | **none — leaks in (P5)** | none |
| flask request/app, `joblib.load`, `np.load` | serve_app.py:54,63,124-133 | `app.test_client`, real joblib | test_serve_app_fallback (fallback+exec-params only; request path untested) |
| gunicorn | docker/serve:31 | — | none (image-only) |

## Dimension findings

| Dim | Suspect / measured | Evidence | Disposition |
|---|---|---|---|
| D1 | **`cleanup_stale_serving_containers` force-kills running job containers** — `harden_service` stamps `sagemaker.local=true` on *every* generated service (patches.py:70-76 via :144, all train/serve/process compose files); `_list(…, None)` has no status filter and `rm -f` runs on all ids (:231-259,:275-289). Real-docker probe: `docker run -d --label sagemaker.local=true alpine sleep 600` → `cleanup_stale_serving_containers()` returned 1, running container gone. Name/docstring promise "serving containers"; live call sites in all 4 `batch_transform.ipynb` run it at notebook start — one running notebook kills a sibling's in-flight job | real docker rm -f | **G-171 S1** |
| D1 | **`reset_all` does not restore the staticmethod** — captures `cls._get_compose_cmd_prefix` (staticmethod auto-unwraps to function on access) and re-assigns via plain `setattr` (:117-118,:300-302). Probe: `inspect.getattr_static` pre-patch = `staticmethod`, post-reset = `function`; `instance._get_compose_cmd_prefix()` → `TypeError: takes 0 positional arguments but 1 was given`. Latent today: SDK's only call site is class-level (image.py:102) — "reversible via reset_all" (docstring :3) is false for descriptor shape | getattr_static + TypeError | **G-172 S3** |
| D1 | **`tolerant_compose_cmd_prefix` FileNotFoundError hole** — catches only `CalledProcessError` (:93-99); docker CLI absent → raw `FileNotFoundError` escapes, `docker-compose` fallback (:102) and named `ImportError` (:104) unreachable. Probe: `check_output`→FNF + `which`→"/usr/bin/docker-compose" → `FileNotFoundError` (expected `["docker-compose"]`) | probe | **G-173 S3** |
| D1 | **`_remove_containers` reports success on failure** — `check=False` + returncode ignored → returns `len(ids)` regardless (:252-259). Probe: runner rc=1 stderr="denied" → returns 2 | probe | **G-174 S3** |
| D1/D8 | **`make_local_pipeline_session` is not hermetic** — `LocalPipelineSession.__init__` has no `sagemaker_config` param (pipeline_context.py:251-288) → ctor runs `load_sagemaker_config` on ambient files; post-init `sagemaker_config=` (:81) bypasses `validate_sagemaker_config`. Probe: `SAGEMAKER_USER_CONFIG_OVERRIDE` yaml with `Session.DefaultS3ObjectKeyPrefix` → `default_bucket_prefix == 'leaked-prefix'` (LocalSession with explicit config → `None` — hermetic); malformed ambient yaml → ctor `ValidationError` crash; `p.sagemaker_config = {'BogusKey':123}` accepted vs ctor raises | env probe ×3 | **G-175 S3** |
| D1 | **`LocalModeConfig` accepts what its consumers reject** — `_validate_endpoint` slices `url[len("http://"):]` regardless of scheme (:74-81): `"https://"` (no host) → `url[7:]="/"` truthy → accepted. `serving_port` guarded `<=0` only (:68) → 70000/99999 accepted → docker publish fails later. `bucket` checked non-empty only (:64) → `bucket="x"` accepted, then live `create_bucket` → `InvalidBucketName` (integration test `test_sts_caller_identity_routes_to_moto` uses exactly this and is **red today**). `network=""` silently disables injection (`inject_compose_network and cfg.network`, patches.py:141) | probes + red integ test | **G-176 S3** |
| D1/D5 | **`config_from_env` docstring overstates the mapping** — "Recognized variables mirror the dataclass fields upper-cased" (:89-93) but `aws_access_key_id`/`aws_secret_access_key`/`inject_compose_network`/`harden_containers` have no env mapping (:113-122). Probe: `SAGEMAKER_LOCAL_INJECT_COMPOSE_NETWORK=false` + `HARDEN_CONTAINERS=false` + `AWS_ACCESS_KEY_ID=envkey` → config still `True/True/'test'`. `SERVING_PORT=abc` → bare `invalid literal for int()` without the variable name (:119) | env probe | **G-177 S3** |
| D1 | **Compose-shape drift fails with decontextualized builtins** — `_rewrite_compose_file`/`inject_network`/`harden_service`/`patched_compose` assume SDK dict shapes (:57-61,:71-76,:125,:139-148). Probes ×6: services-as-list → `AttributeError 'list' object has no attribute 'values'`; service `networks` list-form → `… 'setdefault'`; `labels` str → `… 'setdefault'`; non-dict compose → `… 'get'`; empty file → `NoneType .get`; services:null → `NoneType .values`; cmd without `-f` → `ValueError '-f' is not in list` — all escaping mid-`fit()` with no file/config context | probe table | **G-178 S3** |
| D1 | **`resolve_gateway_from_routes` raises on malformed lines** — `int(gateway_hex[i:i+2],16)` (:169-170): `ZZZZ`/`01`/`NOTHEX!!` → `ValueError` escapes through `gateway_getter` into the patched SDK call instead of skipping the line (:165-170). Harm bounded: `/proc/net/route` is kernel-generated | probe | **G-179 S3** |
| D1 | **First config wins, silently** — `apply_compose_patches` returns early when applied (:113-114); second `make_local_session` with a different `network` silently keeps the first cfg. Probe: apply(net-a) then apply(net-b) → only the first "installed" log; no warning. Behavior enshrined by test_patches.py:153-161 but nothing tells the caller its cfg was dropped | caplog probe | **G-180 S3** |
| D1 | **`output_fn_default` CSV body is not CSV** — `np.array2string(arr, separator=",")` (:83-87) emits `b'[1.,2.]'` (bracketed); 40-elem array → line-wrapped `b'[ 0.,1.,…\n 18.,…]'`. SageMaker's CSV contract is bare `1,2\n`-shaped rows. `Accept: text/csv` through `/invocations` produces unparseable-by-contract output | bytes probe | **G-181 S3** |
| D9/D10 | **Test depth** — shadow-copy mutation battery **18/24 killed, 6 survived**: `url[len("http://"):]` slice (M1 — the G-176 hole is unasserted), `or "us-east-1"` region default (M3), `else 8080` port default (M4), `check=False→True` (M11 — G-174's arm), `!= "us-east-1"→==` LocationConstraint arm (M20 — covered but unasserted; mutant sends AWS-invalid constraint on the DEFAULT region), `labels` isinstance-guard deletion (M27 — arm :72-74 uncovered). Uncovered: patches.py :72-74 (list-labels), :165 (short-line skip), :177-179 (OSError arm), :203 (apply-twice), :219 (docker-host fallback); session.py :97 (`_s3_client` body — always monkeypatched), :114 (exists-arm), :119 (non-404/403 raise), :122-124; `serve_app.py` whole request path (28 stmts — `invocations`/`_model_instance`/`input_fn`/`output_fn`/`ping`/`create_app` at 60%). `test_session.py` installs real SDK patches with **no `reset_all`** (only `test_patches.py` has the fixture — pollution is order-dependent, currently lands last alphabetically). `integration` marker unregistered → PytestUnknownMarkWarning ×2; `match=""` parametrize arm is vacuous (PytestWarning); **integration suite is deselected by `test`/`coverage` recipes and currently RED** (`test_sts_caller_identity_routes_to_moto` — bucket `"x"` → InvalidBucketName). No `features/` → surfaces `config_from_env`/`make_local_*`/`cleanup_*`/`build_image`/serve endpoints unmapped → AX-2. Floor 75 vs own-src ~95% | battery + cov + live integ run | **G-182 S4** |
| D3 | **`type: ignore[arg-type]` ×2 uncommented** — config.py:115-116 silence the narrowing the `missing` check guarantees; restructuring (`if endpoint is None … raise`) would make it honest. `cast(list[str], labels)` at patches.py:72 follows an isinstance guard (needed — `Any` doesn't narrow element type); `cast(Callable,…)` :212 names the true SDK signature — honest | pyright + reading | folded into G-176 |
| D3 | **`docker/` assets escape `bandit`/`vulture`** — Makefile :30-31 scan `src` only; `docker/moto/Makefile` scans its out-of-src file explicitly (`bandit glue_overlay.py`, `vulture glue_overlay.py tests`). Manual `bandit docker/` + `vulture docker` → clean today (latent hole, not a live finding). `[tool.vulture] ignore_names` lists test-side names (`compose_project`, `fake_host_env`, `detached`) that the src-only scan can never flag — stale config | recipes + manual scans | **G-183 S3** |
| D3/D5 | **No `py.typed`** — all 12 sibling libs ship the marker (G-168 precedent); pyright-strict package is invisible to consumers' type checking | find | **G-184 S3** |
| D1 | `apply_*`/`reset_all` globals are check-then-act (:113,:202,:294) — a thread landing between the `is None` check and the capture could store a *patched* fn as "original" → `reset_all` leaves the patch installed (irreversible). Stress: 16 threads × 400 apply/reset cycles (6400) → zero corruptions, clean post-state | stress (no hit) | suspect, no row |
| D1 | `_apply_local_mode_config` replaces `session.config` wholesale (:140) — drops keys `load_local_mode_config()` may have loaded (`region_name`, `container_config`) and would clobber SDK's `disable_local_code`→False (:773) — we never pass that flag today | reading | suspect, no row |
| D1 | Studio path: `is_studio` hosts emit `network_mode: "sagemaker"` (image.py:856) — injected `networks` dict + `network_mode` are mutually exclusive in compose → invalid file on Studio hosts (narrow) | SDK reading | suspect, no row |
| D1 | `assert _original_compose is not None` (:123) — `python -O` strips it → `NoneType` call later; `build_image` FNF asymmetry (`docker` absent → raw `FileNotFoundError`, not the documented `RuntimeError`) + no timeout (unbounded hang) | reading | suspects, no row |
| D4 | `image_tag`/`role_arn` fields unconsumed inside the lib — read by notebooks (`image_uri=cfg.image_tag`, `role=cfg.role_arn`) — config-bag by design | grep | clean |
| D2 | all paths O(services)/O(route-lines)/O(ids) — bounded inputs, no repeated normalization | op-count | clean |
| D6 | `_original_*` globals = 4 bounded refs; fixtures scoped; no accumulation | construction | clean |
| D7 | serve_app globals (`model`, `model_loaded`, `inference_module`) — gunicorn `workers: 1` sync worker → single-threaded by construction | construction | clean |
| D8 | `yaml.safe_load` ✓; all subprocess calls argv lists (no shell) — `tag` is caller-supplied argv (author boundary); `np.load(allow_pickle=False)` ✓; `joblib.load` = pickle-family on the user's own model artifact (documented trust boundary); `SAGEMAKER_PROGRAM` env → path inside own container | surface | clean |
| D1 obs | upstream `_compose` aliases `self.compose_cmd_prefix` then `.extend`s it (image.py:790-803) — repeat `_compose` calls accumulate args; our `index("-f")` stays correct (path constant per container). SDK-side, out of scope — noted for the record | SDK reading | observation |

## Measurements

- **Coverage**: 57 tests, `-m "not integration"`; TOTAL 91% / 785 stmts, no
  editable-dep pollution. `patches.py` 149 stmts 9 miss (94%):
  72-74,165,177-179,203,219. `session.py` 48 stmts 4 miss (92%):
  97,114,119,122. `serve_app.py` 70 stmts 28 miss (60%). Floor: 75
  (`Makefile:18`) vs own-src ~95%.
- **P1 restore fidelity**: `getattr_static` pre `staticmethod` → post-reset
  `function`; instance call → `TypeError` (0-arg fn bound with self).
- **P2 FNF hole**: `check_output`→`FileNotFoundError` + `which`→path →
  raw `FileNotFoundError` escaped (expected `['docker-compose']`).
- **P3 false count**: `rm` rc=1 → `_remove_containers` returns 2.
- **P4 blast radius (real docker)**: `docker run -d --label
  sagemaker.local=true alpine sleep 600` → `cleanup_stale_serving_containers()`
  → `removed: 1`; `docker inspect` → no such object. Label applied to every
  compose service by `harden_service` (patches.py:70-76,144).
- **P5 ambient leak**: `SAGEMAKER_USER_CONFIG_OVERRIDE` yaml →
  `LocalPipelineSession.default_bucket_prefix == 'leaked-prefix'`;
  `LocalSession` (explicit config) → `None`. Malformed ambient yaml → ctor
  `ValidationError` (huge dump). `p.sagemaker_config = {'BogusKey':123}`
  accepted; ctor-path `LocalSession(sagemaker_config={'BogusKey':123})` →
  `ValidationError 'SchemaVersion' is a required property`.
- **P6 validation**: `https://` accepted; `serving_port` 70000/99999 accepted;
  `SERVING_PORT=abc` → `invalid literal for int() with base 10: 'abc'`;
  env `INJECT_COMPOSE_NETWORK=false`/`HARDEN_CONTAINERS=false`/
  `AWS_ACCESS_KEY_ID=envkey` → ignored (True/True/'test').
- **P7 drift shapes**: services-as-list/networks-list/labels-str/non-dict/
  empty/services-null → `AttributeError` ×5 + `NoneType` ×1 inside
  `_rewrite_compose_file`; cmd missing `-f` → `ValueError '-f' is not in list`.
- **P8 first-cfg-wins**: apply(net-a)→apply(net-b): only first "installed"
  log line; no warning on the divergent second call.
- **P9 CSV body**: `output_fn_default(np.array([1.0,2.0]),"text/csv")` →
  `b'[1.,2.]'` (bracketed); 40-elem → `b'[ 0.,1.,…\n 18.,…]'` line-wrapped.
- **P10 thread stress**: 16 threads × 400 apply/reset → 0 double-wraps,
  post-state original. Race window provably exists (check-then-act at
  :113/:202/:294) — suspect only.
- **P11 gateway parse**: `ZZZZ`/`01`/`NOTHEX!!` gateway fields → `ValueError`
  escapes all three.
- **P12 `build_image`**: `_run_subprocess`→FNF → raw `FileNotFoundError`
  escapes (docstring contract is `RuntimeError`); no `timeout` kwarg (:28-33).
- **Positive check**: `make_local_session(serving_port=9999)` →
  `sagemaker_runtime_client.serving_port == 9999` — the post-init config
  setter propagates correctly (local_session.py:566-578,:790-791).
- **Integration suite live run**: `test_session_moto` → 2 pass, 1 FAIL —
  `bucket="x"` → `InvalidBucketName` on `create_bucket` (session.py:125);
  the suite is deselected by `make test`/`coverage` (-m "not integration") so
  the red state is invisible to `make quality`.
- **Mutation battery** (shadow-PYTHONPATH copy, real suite): 18/24 killed;
  survivors M1 (url slice `len("http://")`→`len("https://")`), M3 (`or
  "us-east-1"`→`"eu-west-1"`), M4 (`else 8080`→`9090`), M11 (`check=False`→
  `True`), M20 (`!=`→`==` on us-east-1 — sends AWS-invalid LocationConstraint
  on the default region, unasserted), M27 (labels isinstance-guard deletion —
  arm :72-74 uncovered).
- **Seed resolution**: README "patches.py signature drift" — seams verified
  against 2.257.1 (all signatures match); the drift hazard is real but its
  failure mode is G-178's decontextualized crash, not silent misbehavior.

## Gaps promoted

| Gap ID | Severity | One-line |
|---|---|---|
| G-171 | S1 | `cleanup_stale_serving_containers` rm -f's every `sagemaker.local=true` container incl. running training jobs — label is on every hardened service; real-docker demo removed a running container |
| G-172 | S3 | `reset_all` restores `_get_compose_cmd_prefix` as a plain function (was `staticmethod`) → post-reset instance call raises TypeError |
| G-173 | S3 | `tolerant_compose_cmd_prefix` misses `FileNotFoundError` → docker-CLI-absent hosts crash instead of `docker-compose` fallback / named ImportError |
| G-174 | S3 | `_remove_containers` `check=False` + rc ignored → returns `len(ids)` claiming removal on failure |
| G-175 | S3 | `make_local_pipeline_session` not hermetic: ambient `~/.sagemaker`/override-env config leaks `default_bucket_prefix`, malformed ambient file crashes ctor, post-init `sagemaker_config` skips validation |
| G-176 | S3 | `LocalModeConfig` accepts `https://` (no host), `serving_port`>65535, `bucket` names S3 rejects ("x" → live `InvalidBucketName`), `network=""` silently disables injection; `type: ignore` ×2 uncommented |
| G-177 | S3 | `config_from_env` docstring claims field-mirroring but 4 fields unmapped (aws creds, inject, harden — env silently ignored); `int()` error lacks var name |
| G-178 | S3 | compose-patch assumes SDK dict shapes + `-f` flag → 7 malformed/drift shapes escape as raw `AttributeError`/`ValueError` mid-`fit()` without file context |
| G-179 | S3 | `resolve_gateway_from_routes` raises `ValueError` on malformed hex instead of skipping the line (bounded: kernel-generated input) |
| G-180 | S3 | `apply_compose_patches` first-config-wins silently — later divergent cfg dropped with no warning |
| G-181 | S3 | `serve_app.output_fn_default` CSV emits bracketed, line-wrapped `np.array2string` — not the SageMaker CSV contract |
| G-182 | S4 | 6/24 mutants survived; serve_app request path + 9 src lines uncovered; integration suite red + deselected + unregistered marker; `test_session.py` leaks SDK patches; `match=""` vacuous; no `features/` → AX-2; floor 75 vs ~95% |
| G-183 | S3 | `docker/` escapes `bandit`/`vulture` (src-scoped recipes; `docker/moto` scans its file explicitly); `vulture` `ignore_names` lists test names the scan never sees |
| G-184 | S3 | package ships no `py.typed` — all 12 sibling libs do; strict-typed API invisible to consumer pyright |
