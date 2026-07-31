"""GitHub releases fetcher.

Two sources of repos:
  1. `repos` in config.yml — a small hand-picked list, mainly for upstream OSS
     projects that live outside Databricks' own GitHub orgs (e.g. Spark is
     under apache/, not databricks/).
  2. `auto_discover_orgs` in config.yml — every non-archived, non-fork public
     repo under these orgs is tracked automatically. databrickslabs in
     particular is specifically "labs projects to accelerate use cases on
     Databricks," so the whole org is a good fit — a hand-picked subset of it
     will always miss newer/less-famous-but-still-relevant tools.

Releases themselves come from each repo's public releases.atom feed, which
needs no API token and isn't subject to the unauthenticated REST API's 60
requests/hour limit. Org *listing* does hit that REST API, but it's one call
(or a few, paginated) per run — negligible against the limit.
"""

import re

from datetime import datetime, timezone

import feedparser
import requests

from .common import html_to_summary_text, make_item

_TRAILER_LINE = re.compile(r"^(Co-authored-by|Signed-off-by|Reviewed-by):", re.IGNORECASE)
_HEADERS = {"User-Agent": "databricks-updates-feed/1.0", "Accept": "application/vnd.github+json"}


def _drop_commit_trailers(summary: str) -> str:
    """Strip git commit trailer lines (e.g. from squash-merged nightly builds)
    that occasionally end up as the entire release body — not real content."""
    kept = [line for line in summary.split("\n") if not _TRAILER_LINE.match(line.strip())]
    return "\n".join(kept).strip()


def discover_org_repos(org: str) -> list:
    """List every non-archived, non-fork public repo under a GitHub org."""
    repos = []
    page = 1
    while True:
        resp = requests.get(
            f"https://api.github.com/orgs/{org}/repos",
            params={"per_page": 100, "page": page, "type": "public"},
            headers=_HEADERS, timeout=30,
        )
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        repos.extend(r["full_name"] for r in batch if not r.get("archived") and not r.get("fork"))
        if len(batch) < 100:
            break
        page += 1
    return repos


def fetch(repos: list, auto_discover_orgs: list = None) -> list:
    all_repos = list(dict.fromkeys(repos))  # de-duped, order-preserving

    for org in auto_discover_orgs or []:
        try:
            discovered = discover_org_repos(org)
            print(f"[github_releases] auto-discovered {len(discovered)} repos under {org}")
            for repo in discovered:
                if repo not in all_repos:
                    all_repos.append(repo)
        except Exception as exc:  # noqa: BLE001 - a broken org listing shouldn't kill the run
            print(f"[github_releases] failed to auto-discover {org}: {exc}")

    items = []
    for repo in all_repos:
        feed_url = f"https://github.com/{repo}/releases.atom"
        parsed = feedparser.parse(feed_url)

        for entry in parsed.entries:
            published = None
            if getattr(entry, "updated_parsed", None):
                published = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc).date().isoformat()

            items.append(make_item(
                source="github_release",
                source_label=f"GitHub · {repo}",
                title=f"{repo}: {entry.title}",
                url=entry.link,
                published=published,
                summary=_drop_commit_trailers(html_to_summary_text(getattr(entry, "summary", ""))),
                tags=[repo],
                category_hint=repo,
            ))
    return items
