## Behavior

- State assumptions before implementing. If uncertain, ask — don't guess through it.
- If multiple interpretations exist, name them. Don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- Minimum code that solves the problem. No speculative features, no unrequested abstractions.
- Touch only what you must. Don't improve adjacent code that isn't broken.
- Match existing style even if you'd do it differently.
- Remove imports/vars/functions that YOUR changes made unused. Leave pre-existing dead code alone unless asked.
- If you write 200 lines and it could be 50, rewrite it first.

## Host resources

<!-- host-resources v1: a standard block, kept word-for-word identical wherever it is used. Limits specific to this repository go under "In this repository", below it. -->

This repository can share its host with other work, and hosts differ. Act on what you measure on the host in front of you, never on a core count, memory size or timing remembered from another run or written in a doc.

**Measure before every heavy command**: a test suite, a coverage or mutation run, a build, a browser, an emulator, a container.

```sh
nproc; cut -d' ' -f1-3 /proc/loadavg                # logical cores; 1, 5 and 15 min load
grep -E 'MemAvailable|SwapFree' /proc/meminfo       # memory a new process can still get
grep some /proc/pressure/cpu /proc/pressure/memory  # avg60: % of the last minute tasks stalled
findmnt -no FSTYPE -T "${TMPDIR:-/tmp}"             # tmpfs: the temp dir is RAM
```

These are Linux's commands; on another OS take the same four readings with its own tools.

- **Wait when the host is busy.** A 1 min load above `nproc` means more runnable tasks than cores, so one more job only lengthens every queue. A memory `some avg60` above zero on two readings a minute apart means tasks already stall for memory. Wait and measure again; if it stays that way, report the readings.
- **Fit the job to the memory.** Start a job only when its measured peak fits in `MemAvailable`. `/usr/bin/time -v <command>` prints `Maximum resident set size` for the largest single process of a run; multiply it by the number of workers.
- **Cap parallelism yourself.** A tool's `auto` worker count takes every logical core. Pass an explicit count of at most half of `nproc`: logical cores usually come two to a physical core, and the rest of the host needs the other half.
- **One heavy command at a time.** Queue the next one; never start two together.
- **Bound and contain every heavy command.** When the host has a job runner (`command -v devjob`), run through it: `devjob <command>`. Otherwise run `nice -n 10 timeout <limit> <command>`, so the job yields the CPU and cannot hang forever.
- **Stop what you start, in the step that finishes with it**: dev servers, browsers, emulators, daemons, containers, watchers. Then list what is left (`pgrep -af <name>`) and stop only processes this session started. One whose parent is alive and is not yours belongs to someone else.
- **Keep bulk off a RAM temp dir.** When the temp dir is `tmpfs`, every byte in it is memory until it is deleted. Installs, virtualenvs, downloaded binaries and large logs go to a path `findmnt -T <path>` shows on a disk filesystem, and you delete them when the task ends.
- **Re-run a failure alone before calling it a regression.** A timeout on a loaded host measures the neighbours. Measure again, run the test by itself, then judge.
- **Never relieve pressure by force.** Do not kill a process you did not start, raise a limit or switch off a cap to get a job through. Report the readings and wait.

### In this repository

- Heavy here: `make test`, `make coverage`, `make test-bdd`, `make test-e2e`, `make test-videos-docker`.
- The `docker-compose.yml` services keep running after the task that started them: Trino alone held 2 GB while idle (`docker stats`, 2026-10-10). `docker compose stop` when no task needs them.
- Semgrep runs `--config p/default --metrics off`: on this tree it runs the same 551 rules and reports the same 42 findings as `--config auto`, which refuses to run with metrics off (measured 2026-10-10). Keep both flags; `auto` sends the project's metrics to semgrep.dev.

## Code style

- Functions: 4-20 lines. Split if longer.
- Files: under 500 lines. Split by responsibility.
- One thing per function, one responsibility per module (SRP).
- Names: specific and unique. No abbreviations — write full words (`calculateVolume`, not `calcVol`). Avoid `data`, `handler`, `Manager`. Prefer names that return <5 grep hits in the codebase.
- Types: explicit. No `any`, no `Dict`, no untyped functions.
- No code duplication. Extract shared logic into a function/module.
- Early returns over nested ifs. Max 2 levels of indentation. No else keyword — invert the condition and return early.
- Exception messages must include the offending value and expected shape.

## Comments

- Keep your own comments. Don't strip them on refactor — they carry
  intent and provenance.
- Write WHY, not WHAT. Skip `// increment counter` above `i++`.
- Docstrings on public functions: intent + one usage example.
- Reference issue numbers / commit SHAs when a line exists because
  of a specific bug or upstream constraint.

## Tests

- Tests run with a single command: `<project-specific>`.
- Every new function gets a test. Bug fixes get a regression test.
- Mock external I/O (API, DB, filesystem) with named fake classes,
  not inline stubs.
- Tests must be F.I.R.S.T: fast, independent, repeatable,
  self-validating, timely.

## Dependencies

- Inject dependencies through constructor/parameter, not global/import.
- Wrap third-party libs behind a thin interface owned by this project.

## Structure

- Follow the framework's convention (Rails, Django, Next.js, etc.).
- Prefer small focused modules over god files.
- Predictable paths: controller/model/view, src/lib/test, etc.

## Formatting

- Use the language default formatter (`cargo fmt`, `gofmt`, `prettier`,
  `black`, `rubocop -A`). Don't discuss style beyond that.

## Logging

- Structured JSON when logging for debugging / observability.
- Plain text only for user-facing CLI output.
