# SSG posts follow-ups — 2026-10-18

Scope: the four issues flagged while implementing SX-22 (`libs/ssg` dated-post
index + per-locale RSS feed) but deliberately left out of that item. A
divergence with a spec citation is registered in `docs/gaps.md`; anything that
turns out not to diverge is recorded below as a not-finding. Reading the code
settled all four — no build or site render was needed.

## Registered

| Gap | Finding |
|---|---|
| G-349 | `render_feed`'s `variant` parameter is dead — declared on the port, forwarded by the renderer, read by no template |
| G-350 | each published post's body and social card are rendered twice per build |

Both are owned by `docs/backlog.md` AF-186.

## Not findings

- **Feed `pubDate` hardcodes `GMT`** (`infrastructure/frontend/templates/feed.xml:15`,
  `date.strftime('%a, %d %b %Y %H:%M:%S GMT')`). RFC 822/1123 requires the zone
  to be a real offset, and the literal would be wrong on a non-UTC datetime —
  but `Page.__post_init__` coerces a naive date to UTC
  (`domain/entities/page.py:24-26`) and the config parser normalises every
  parsed date to UTC (`infrastructure/site_config_repository.py:621-636`), so
  `page.date` is always UTC-aware and the printed wall-clock *is* UTC. Not
  divergent; no fix.

## Homed elsewhere

- **The electricity Flink service can't run its job** — the stock `flink` image
  has no Python, so the mounted `flink_job` cannot execute. Registered as G-351
  in `docs/audits/container-images-2026-10-18.md` and owned by
  `docs/backlog.md` DK-6.

## Standards cited

- RSS 2.0 / RFC 822 date-time for `pubDate`
  (https://www.rssboard.org/rss-specification) — the reason the hardcoded zone
  needed checking.
