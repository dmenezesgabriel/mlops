#!/usr/bin/env bash
# Run a root Makefile gate for only the packages a commit touches.
#
# Pre-commit previously ran `make security` / `make maintainability` /
# `make dependencies` / `make complexity` over ALL 21 packages on every
# commit — several minutes of semgrep/xenon/deptry/radon per commit,
# duplicated per session, and red on pre-existing findings in packages the
# commit didn't touch. CI (`.github/workflows/ci.yml`) runs the same gates
# full-repo on every push, so the local hooks only need fast feedback on
# what actually changed:
#
#   - files under a package dir  -> that package's target (deduplicated)
#   - root tooling files
#     (Makefile, pyproject.toml, uv.lock, .pre-commit-config.yaml,
#     scripts/, .github/)       -> the target at the repo root (full loop)
#   - anything else (docs, …)   -> skipped; CI covers it
#
# A `flock` serializes same-repo hook runs so two sessions committing at
# once never double-scan the same package (shared host).
set -euo pipefail

target="${1:?usage: gate-changed.sh <security|maintainability|dependencies|complexity> [filenames...]}"
shift

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

exec 9>"${TMPDIR:-/tmp}/mlops-gate-${target}.lock"
flock 9

mapfile -t packages < <(
  git ls-files "libs/*/Makefile" "docker/moto/Makefile" "projects/*/Makefile" |
    sed -E 's#((libs|projects)/[^/]+|docker/moto)/Makefile#\1#'
)

infra_file() {
  case "$1" in
    Makefile | pyproject.toml | uv.lock | .pre-commit-config.yaml \
    | .github/* | scripts/*) return 0 ;;
    *) return 1 ;;
  esac
}

touches_infra=false
found=

for file in "$@"; do
  if infra_file "$file"; then
    touches_infra=true
    continue
  fi
  for dir in "${packages[@]}"; do
    case "$file" in
      "$dir"/*)
        found+="$dir"$'\n'
        break
        ;;
    esac
  done
done

if $touches_infra; then
  make "$target"
elif [[ -z "$found" ]]; then
  # Docs-only / non-package change: nothing local to scan; CI runs full gates.
  exit 0
else
  for dir in $(printf '%s' "$found" | sort -u); do
    make -C "$dir" "$target"
  done
fi