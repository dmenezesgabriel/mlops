# AU-11 — diagrams audit (2026-10-03)

MA-5 step 1 (first audit of the milestone). Target: `libs/diagrams` — 408 LOC /
340 SLOC per radon raw (`mingrammer_renderer.py` 94, `loader.py` 72,
`diagram_definition.py` 50, `cli.py` 47, `logging.py` 29, VOs 18, ports+inits
30); 16 tests / 399 test LOC in one `tests/unit/` tree mirroring the src layout.
Gates baseline: 16 tests pass in 0.16 s, pyright strict 0 errors, radon cc
clean, bandit/vulture silent, `pytest --cov` TOTAL 88% (floor 75) — no
editable-dep pollution possible (zero workspace deps); own-module coverage is
the honest 54–97% spread below. Stale `tests/__pycache__/test_{builder,cli,
domain_and_loader}.pyc` = remnants of the pre-Clean-Architecture flat test
tree (see `9edcea4 refactor(diagrams)`).

Environment fact driving measurement choices: the `diagrams` (mingrammer)
extra is **not installed** (`[diagrams]` optional dep, pyproject:10-13) —
`render()` is measured via a `sys.modules`-injected fake `diagrams` module
capturing the `filename=` kwarg, node instantiations, and `>>` edge calls;
everything before the graphviz boundary is exact. `diagrams` internally shells
out to the `dot` binary — a system dep declared only in `libs/diagrams/
Dockerfile` (`apt-get install graphviz`), invisible to pyproject.

Production surface: root `Makefile:145-152` `diagrams-render` → docker
`mlops-diagrams-prod` → `diagrams-cli mlops_lifecycle --definitions-dir
/app/definition --output-dir /app/output` on `diagrams/definition/
mlops_lifecycle.yaml` (the only definition in the repo — 10 nodes, 4 clusters,
10 connections, exercises every loader path incl. `graph_attr`/`node_attr`).

## Surface inventory

| Module | SLOC | Public symbols | Entry |
|---|---|---|---|
| `infrastructure/cli.py` | 47 | `main`★, `_parse_arguments` | console script `diagrams-cli` (pyproject:16) |
| `infrastructure/loader.py` | 72 | `load_from_file`, `load_from_yaml_string`; privates `_parse_nodes`, `_parse_clusters`, `_parse_connections`, `_parse_graph_attr` | ← cli `main()` |
| `infrastructure/mingrammer_renderer.py` | 94 | `MingrammerDiagramRenderer` (`render`; privates `_check_dependencies`, `_resolve_node_class`, `_instantiate_nodes`, `_instantiate_clusters`, `_draw_connections`) | ← cli `main()` |
| `infrastructure/logging.py` | 29 | `StructuredFormatter` (`format`), `setup_structured_logging` | ← cli `main()`; **zero emitters** |
| `domain/entities/diagram_definition.py` | 50 | `DiagramDefinition` (`_validate`, `_validate_connections`) | ← loader |
| `domain/value_objects/diagram_{node,cluster,connection}.py` | 18 | `DiagramNode`, `DiagramCluster`, `DiagramConnection` (frozen) | ← loader/domain |
| `application/ports/diagram_renderer.py` | 9 | `DiagramRendererPort` Protocol | **zero consumers** |
| `__init__`s (root/domain/ports) | 21 | `__version__`, 5 re-exports | — |

## Callgraph

```
diagrams-cli main()                                   [cli.py:32]
  ├─ setup_structured_logging()                       [logging.py:28]
  │   └─ root.addHandler(StreamHandler) EVERY call    [:29-32]
  │       ↳ P3: 3 calls → 3 handlers; 0 emitters in src
  ├─ _parse_arguments ← sys.argv                      [cli.py:12-29]
  │   diagram_id positional + --definitions-dir/--output-dir
  ├─ yaml_path = defs_dir / f"{diagram_id}.yaml"      [:35-41]
  │   ↳ diagram_id UNVALIDATED join (read-side suspect);
  │     .exists() → .yml fallback → FileNotFoundError
  │     (yml-fallback arm untested; TOCTOU benign —
  │      read_text failure → except Exception below)
  ├─ load_from_file → read_text →                     [loader.py:39-41]
  │   load_from_yaml_string                           [:13]
  │   ├─ yaml.safe_load → cast(object) →              [:14-19]
  │   │   isinstance(dict) else ValueError (:16 uncovered)
  │   ├─ _parse_nodes/_parse_clusters/                [:44-75]
  │   │   _parse_connections: str() coercion on every
  │   │   field; missing keys → KeyError (P2); non-list
  │   │   → TypeError; label UNCOERCED (P9)
  │   ├─ _parse_graph_attr: dict-checked (else        [:78-92]
  │   │   ValueError, :87 uncovered); str(k):str(v)
  │   │   coercion → {1:,'1':} collision (P2)
  │   └─ DiagramDefinition(...)                       [:27-36]
  │       └─ _validate → _validate_connections        [definition:34-58]
  │           ↳ valid_directions {TB,BT,LR,RL};
  │             all_identifiers is a SET → dup ids
  │             ACCEPTED (P1); from_node arm :50 uncov
  ├─ MingrammerDiagramRenderer().render(def, out)     [cli.py:47-48]
  │   └─ render                                       [renderer:83]
  │       ├─ _check_dependencies                      [:9-20]
  │       │   import_module("diagrams") → named       (:17-20 uncovered)
  │       │   ImportError listing [diagrams] extra
  │       ├─ Path(out)/filename → parent.mkdir        [:87-88]
  │       │   ↳ P5: "../escape" reaches graphviz write;
  │         "/abs" → mkdir PermissionError — filename
  │         UNVALIDATED (def-file input)
  │       ├─ with Diagram(name, filename=str(target), [:90-98]
  │       │   direction, show=False, outformat="png",
  │       │   graph_attr, node_attr)                  (uncovered :90-98)
  │       ├─ _instantiate_nodes: resolve+cls(label)   [:44-49]
  │       │   per node → instances[id]                (uncovered;
  │       │   dup id → last wins, P6)
  │       ├─ _instantiate_clusters: with Cluster(     [:51-63]
  │       │   graph_attr={margin:20,fontsize:13}) —
  │       │   pinned by margin test
  │       ├─ _draw_connections: instances[from]>>     [:65-81]
  │       │   Edge(label)|>>instances[to]             (uncovered;
  │       │   falsy label → unlabeled, P9)
  │       └─ return f"{target}.png"                   [:104]
  │   _resolve_node_class(type): split "." <2→raise   [:22-42]
  │       import_module("diagrams."+parts[:-1]) →
  │       getattr(module, parts[-1]) — bounded to
  │       diagrams.* (raise arms :25/:33-34/:39 uncov;
  │       2-part custom.X resolves, P7)
  └─ except Exception → "Error: {e}" + exit(1)        [cli.py:49-51]
      ↳ clean one-line stderr for ALL error classes
        (KeyError "'name'" loses context — no key/path)
```

Dead-looking: `DiagramRendererPort` — 0 consumers repo-wide (grep-verified;
`cli.py:47` instantiates `MingrammerDiagramRenderer` directly; vulture-silent
because Protocol). `StructuredFormatter`/`setup_structured_logging` — wired in
`main()` but no module ever calls `logging.getLogger`/`logger.*` — configured
machinery with zero emitters.

## Boundary table

| Boundary | Where | Faked as | Test |
|---|---|---|---|
| `yaml.safe_load` definition file | loader.py:14 | real yaml strings | test_loader.py (5 tests) |
| fs read `read_text` | loader.py:40 | — (`load_from_file` mocked at cli:10; `Path.exists` patched GLOBALLY) | test_cli.py:12; **loader.py:40-41 uncovered** |
| `importlib.import_module` `diagrams`+`diagrams.*` | renderer:11,32 | `importlib.import_module` stdlib symbol patched GLOBALLY via MagicMock (not a named fake) | test_mingrammer:30,45,65 |
| graphviz `dot` subprocess (inside optional `diagrams` dep) | renderer:90-98 ctx | none — dep absent; Dockerfile installs it | **none — `render` never run end-to-end** |
| fs write `mkdir`+png | renderer:87-88 | tmp dirs (audit probes only) | none |
| `sys.argv`/exit | cli.py:29,51 | `sys.argv` patched globally | test_cli.py:14,47 |
| logging handler → stdout | logging.py:29 | — | **no logging tests; format:8-25 uncovered** |

## Dimension findings

| Dim | Suspect / measured | Evidence | Disposition |
|---|---|---|---|
| D8/D1 | **`filename` unvalidated at the output join**: `filename: "../escape"` → `render` passes `/tmp/…/../escape` as graphviz filename (writes outside `--output-dir`); `filename: "/abs/override"` → `mkdir(parents=True)` on `/abs` → PermissionError mid-render. Author-committed-config boundary (G-04/G-34/G-45 precedent → S3, not S1). CLI `diagram_id` has the same unvalidated join on the read side — no demonstrated harm (user reads own files) → suspect below | P5 | **G-117 S3** |
| D1 | **Duplicate node identifiers silently accepted**: `nodes: [{id:a,…},{id:a,…}]` passes `_validate` (set-based `all_identifiers`); renderer instantiates both, `instances["a"]` keeps only the second — edge resolves `second→second`, first node orphaned-but-rendered. G-33 overwrite class | P1+P6 | **G-118 S3** |
| D1 | **Malformed definition shapes leak `KeyError`/`TypeError`**: missing `name`/`filename`/`id`/`label`/`type`/`from`/`to` → `KeyError('name')`; `nodes: 42` → `TypeError: 'int' object is not iterable`; `nodes: "abc"` → `TypeError: string indices…`; cli prints `Error: 'name'` — key named but no file/expected-shape context. G-22/G-88 class | P2 ×4 | **G-119 S3** |
| D1 | **`str()` coercion of loaded values incl. key collisions**: `name: 42`→`'42'`; `id: 1`/`label: 0`/`type`/`from`/`to` coerced; `graph_attr {1: x, '1': y}`→`{'1':'y'}` last-wins; YAML-1.1 `on:`/`true:` keys → `'True'`. G-06/G-16/G-44/G-97 class | P2 ×3 | **G-120 S3** |
| D3/D1 | **`connection.label` is the only unvalidated field**: `label: 42` → `Edge(label=42)` — int through a `str \| None` declared field (annotation lies at runtime); `label: 0`/`label: ""` falsy → silently unlabeled edge (`if connection.label:` renderer:74) while `label: "0"` renders | P9 | **G-121 S3** |
| D4/D6 | **Logging machinery dead + handler pileup**: zero `getLogger`/emit call sites in `src/` — `StructuredFormatter`+`setup_structured_logging` configure a logger nothing writes to (G-25 dead-machinery class); `setup_structured_logging` `addHandler` per call → 3 calls → 3 handlers (duplicate lines + retention if ever used; tests DO call `main()` repeatedly) | grep + P3 | **G-122 S3** |
| D4 | **`DiagramRendererPort` has zero consumers**: Protocol + `ports/__init__` re-export, no injection seam — `cli.py:47` news up the concrete renderer; test patches the cli-attribute directly. G-09/G-25/G-113 delete-or-document class; vulture-silent (Protocol methods under min-confidence 80) | grep | **G-123 S3** |
| D9/D10 | **Assertion-weak suite + invisible surfaces**: renderer own-cov 54% (`render`:87-104, `_instantiate_nodes`:47-49, `_draw_connections`:71-81, raise arms :25/:33-34/:39, dep-check :17-20 all uncovered — only `_resolve_node_class` happy path + `_instantiate_clusters` margin pinned); logging 65% (`format` :8-25 — the whole body); loader :16/:87/:40-41; definition :50. Mutants: M1 `str()`-drop on `document["name"]` SURVIVED (coercion unasserted), M2 cluster-id-merge drop SURVIVED (no test connects to a cluster node); M3/M4/M5 killed. `.yml` fallback arm untested. Named-fake rule violated: `importlib.import_module`, `Path.exists`, `sys.argv` all patched GLOBALLY — inline MagicMock stubs, not named fakes (ADR-0005). No `features/`/bdd — `diagrams-cli` user-facing surface unmapped → AX-2 | cov + mutation run | **G-124 S4** |
| D8 | `diagram_id` CLI arg joined unvalidated (`cli.py:36`) — `../x` reads outside `--definitions-dir`; read-side only, parses-then-dies, user reads own files | reading | suspect, no row |
| D8/D1 | `filename: "x.png"` → output `x.png.png` (`f"{target}.png"` :104) — consistent, ugly | reading | suspect, no row |
| D8 | `type: "a.__class__"`-shaped exotic attrs resolve (`getattr` on real `diagrams.*` modules → weird instantiation, bounded — fails at `>>`) | reading | suspect, no row |
| D1 | `--output-dir ~/x` creates literal `./~/x` (Path never expands `~`); `mkdir` runs before the Diagram ctx (dirs left on later failure) | reading | suspect, no row |
| D8 | root `Makefile:147` `chmod 777 diagrams/output` — world-writable dir on host; dev-machine boundary (docker root-user workaround) | reading | suspect, no row |
| D5 | `data` local var in loader:14 (repo naming rule); `DiagramDefinition` mutable public attrs + `graph_attr or {}` keeps caller's dict by reference | reading | suspect, no row |
| D1 | TOCTOU `exists()`→`read_text` — deletion between → FileNotFoundError → already clean via `except Exception` | reading | suspect, no row |
| D4 | extras allowlist in `StructuredFormatter` drops `extra={"custom": x}` silently (G-03 shape) — LATENT while nothing emits; if machinery survives triage, revisit | probe | suspect, no row |
| D6 | `instances` dict is per-render — no retention; the only shared state is logger handlers (in G-122) | P3 | suspect, no row |
| D8 | `dot` binary required at render — declared only in Dockerfile; host `[diagrams]` install without graphviz → graphviz ExecutableNotFound wrapped clean by `except Exception` | reading | suspect, no row |
| D3 | `tuple[Any,Any,Any]`/`dict[str,Any]`/`cast(object, safe_load)` + `cast(dict[str,Any], …)` post-isinstance — honest dynamic-import boundary shapes; `_parse_graph_attr` cast post-isinstance honest | reading | clean |
| D2 | `_resolve_node_class` `import_module` per node measured 1.51 µs/call cached (n=10⁴) — no asymptotic issue; validation O(n), edges O(1)/dict | timeit | clean |
| D7 | Single-threaded by construction: one-shot CLI, no async/threads; `diagrams` ctx serial. Only shared state = logger handlers (G-122) | construction | clean |
| D1 | Direction/frozen VOs/`except Exception`→one-line stderr/argparse rc=2 — all verified correct; `.yaml`→`.yml` fallback works (untested, in G-124) | probes | clean |

## Measurements

- **Coverage**: `pytest --cov` TOTAL 88% over 323 stmts (floor 75). Per-module:
  renderer 54% (miss :17-20,:25,:33-34,:39,:47-49,:71-81,:87-104), logging 65%
  (:8-25), loader 87% (:16,:40-41,:87), definition 96% (:50), cli 97% (:55);
  VOs/ports/inits 100%; tests counted at 100% (no `[tool.coverage.run]` —
  denominator includes tests, matches sibling `source=["src","tests"]` shape).
- **P1 dup ids**: `DiagramDefinition(nodes=(a,a), connections=(a→a))` →
  accepted, `len(d.nodes)==2`.
- **P5 traversal**: `filename="../escape"` → `render` passes
  `/tmp/tmpX/../escape` as graphviz `filename=`; `filename="/abs/override"` →
  `PermissionError: [Errno 13] '/abs'` at renderer:88 `mkdir`.
- **P6 dup render**: instantiated `['first','second']`; instances dict binds
  `a→second`; edge resolves `second→second` (captured `>>` calls).
- **P2 loader shapes**: missing `name` → `KeyError: 'name'`; missing node `id`
  → `KeyError: 'id'`; `nodes: 42` → `TypeError: 'int' object is not iterable`;
  `nodes: "abc"` → `TypeError: string indices must be integers`;
  `label: 42` → `d.connections[0].label == 42` (int);
  `name: 42` → `'42'`; `graph_attr {1:x,'1':y}` → `{'1':'y'}`.
- **P9 edge label**: `label: 42` → `Edge(label=42)` int captured.
- **P3 handlers**: `len(handlers)` 0→3 across 3 `setup_structured_logging()`
  calls; grep: zero `getLogger`/`logger.` call sites in `src/`.
- **Extras probe**: `extra={"diagram_id":"d1","custom_field":"lost"}` → output
  JSON has `diagram_id`, `custom_field` absent — silent drop.
- **D2 timeit**: `_resolve_node_class` ×10⁴ → 1.51 µs/call (sys.modules-cached
  import).
- **P7**: `type: "custom.Custom"` (2-part) resolves correctly — constrains
  `len(parts)<2` mutants.
- **Mutation run** (manual flips on copytree, suite = 16 tests): SURVIVED —
  M1 `str(document["name"])`→`document["name"]`, M2 drop
  `all_identifiers.update(cluster ids)`; KILLED — M3 `from_node not in`→`in`,
  M4 `LR`→`LL` in valid set, M5 drop second `exists()` check (.yml fallback is
  pinned by the happy-path test, not a dedicated case). **2/5 survived**;
  uncovered-line mutants (renderer :71-104, logging :8-25, loader :16/:87)
  survive trivially by coverage.
- **Baseline gates** (all clean at HEAD): pyright strict 0 errors, ruff clean,
  radon cc no C+, vulture@80 silent, bandit -ll silent, xenon clean.

## Gaps promoted

| Gap ID | Severity | One-line |
|---|---|---|
| G-117 | S3 | `filename` unvalidated at `Path(output)/filename` — `../escape` writes outside output dir, `/abs` crashes mkdir |
| G-118 | S3 | duplicate node identifiers accepted → `instances` overwrite, orphan node, edges bind last |
| G-119 | S3 | malformed definition shapes leak `KeyError`/`TypeError` without key/path context |
| G-120 | S3 | `str()` coercion on all loaded fields incl. `{1:,'1':}` attr-map key collision (G-06 class) |
| G-121 | S3 | `connection.label` unvalidated — int through `str\|None`; falsy `0`/`""` → silently unlabeled |
| G-122 | S3 | logging machinery has zero emitters + `setup` piles a handler per call |
| G-123 | S3 | `DiagramRendererPort` zero consumers — speculative port (G-09 class) |
| G-124 | S4 | renderer 54%/logging 65% own-cov; M1+M2 mutants survived; global patching (no named fakes); no bdd surface → AX-2 |

Session note: backlog item accurate as written — `diagrams-cli` + dynamic
`diagrams.*` import surface made D8 mandatory and productive (G-117). No
S1/S2 → nothing preempts AU-12; all eight rows batch into the MA-5
remediation step. One process note: an early mutation-harness draft
symlinked into the live tree and wrote `loader.py:28` before crashing —
restored via `git checkout`, re-run on `shutil.copytree`; `git diff` verified
clean. Next: **AU-12** `libs/videos` domain+application (~1400 LOC).
