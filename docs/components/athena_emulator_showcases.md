# athena_emulator showcases

`projects/athena_emulator/notebooks/` holds scenario-driven usage showcases
for the Athena emulator compose stack — one notebook per real-world consumer
flow (first query, analyst reads, lake ETL, backend service, platform admin,
table formats, ops scripting, IaC, operational limits). They are not a test
suite: integrated consumer tests live in `libs/athena-local/tests/`; the
nbclient hook in `projects/athena_emulator/tests/test_notebooks.py`
re-executes the notebooks to regenerate committed evidence.

## Notebook style contract

Every `notebooks/NN_*.ipynb` follows these rules; the contract is pinned by
`01_quickstart.ipynb` and later notebooks extend it, never diverge from it.

1. **Persona + goal intro.** The first markdown cell names who the notebook
   is for and what they accomplish by the end, plus which stack pieces it
   touches.
2. **≤3-line sections.** Each `##` section carries at most three lines of
   markdown, then one canonical usage cell — the committed output is the
   demonstration, not a screenshot of intent.
3. **Measured capabilities.** Every demonstrated feature calls
   `_evidence.record()`; the closing **Capabilities demonstrated** cell
   prints the matrix and `persist()`s `parity/<stem>.md`, which consolidates
   into `PARITY.md`. Detail cells carry measured facts (ids, shapes,
   latencies), never adjectives. Zero FAIL rows may be committed.
4. **Throwaway resources.** Bucket/database/workgroup names are run-scoped
   (`nbNN-…` / `nbNN_…`); a cleanup cell removes everything the run created —
   the stack's data is user data, never reset.
5. **Committed outputs.** The nbclient hook executes each notebook in place;
   the executed notebook is the committed evidence.
6. **Citations.** Notebook markdown may cite permanent docs
   (`docs/architecture/`, `docs/adr/`) only — never backlog, milestone, or
   PRD content.
