#!/usr/bin/env bash
# Writes site=true|false to $GITHUB_OUTPUT for the CI and Deploy Pages
# workflows so site jobs only run when a push could change site/build.
#
# The classification is conservative: a path is site-inert only when it is
# proven unable to reach `make build-site` output. Anything unlisted,
# unresolvable (shallow clone, rewritten history, first push) or an event
# this script does not classify all resolve to site=true — doubt rebuilds.
#
# Keep the ignore list in sync with the site inputs: site/**, the
# collections referenced by site/site.yaml (projects/nyc_taxi_demand_forecasting,
# projects/telco_customer_churn, projects/california_house_pricing,
# projects/electricity_price_streaming, projects/wine_quality_classification),
# libs/** (ssg + plugins + anything they import), Makefile, scripts/**,
# pyproject.toml, uv.lock, .github/**.
set -euo pipefail

event="${1:?usage: detect-site-inputs.sh <event> <before-sha> <base-ref> [head]}"
before="${2:-}"
base_ref="${3:-}"
head="${4:-HEAD}"

emit() { echo "site=$1" >> "${GITHUB_OUTPUT:?GITHUB_OUTPUT is not set}"; }

case "$event" in
    push)
        # Zero/missing before-sha means a brand-new ref — nothing to diff.
        if [ -z "$before" ] || [ "$before" = "0000000000000000000000000000000000000000" ]; then
            emit true
            exit 0
        fi
        base="$before"
        ;;
    pull_request)
        if [ -z "$base_ref" ]; then
            emit true
            exit 0
        fi
        git fetch --quiet --depth=1 origin "$base_ref"
        base="FETCH_HEAD"
        ;;
    *)
        # workflow_dispatch and any future trigger stay conservative.
        emit true
        exit 0
        ;;
esac

if ! git rev-parse --verify --quiet "$base^{commit}" >/dev/null; then
    emit true
    exit 0
fi

changed="$(git diff --name-only "$base" "$head")"
if [ -z "$changed" ]; then
    emit false
    exit 0
fi

while IFS= read -r file; do
    [ -z "$file" ] && continue
    case "$file" in
        # Contributor docs and local-agent state never reach site/build.
        docs/* | .devin/* | .claude/* | .agents/* | .spike-* | AGENTS.md | CLAUDE.md | README.md | LICENSE | .gitignore | .gitattributes | .dockerignore | docker-compose*.yml | mlruns/* | research_repos/* | termux/* | videos/*)
            ;;
        projects/*)
            # Only the collections wired in site/site.yaml feed the site;
            # the other projects are gated code but not site inputs.
            case "$file" in
                projects/nyc_taxi_demand_forecasting/* | \
                projects/telco_customer_churn/* | \
                projects/california_house_pricing/* | \
                projects/electricity_price_streaming/* | \
                projects/wine_quality_classification/*) emit true; exit 0 ;;
                *) ;;
            esac
            ;;
        *)
            emit true
            exit 0
            ;;
    esac
done <<<"$changed"

emit false
