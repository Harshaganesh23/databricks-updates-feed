"""Orchestrator: run every fetcher, merge results into data/updates.json.

Each fetcher is isolated in its own try/except so one broken source (most
likely the LinkedIn bridge) never stops the others from updating.
"""

import os
import sys
from datetime import datetime, timezone

import yaml

from fetchers import blog, github_releases, linkedin_bridge, release_notes
from fetchers.common import (
    archive_items, load_existing, load_seen_ids, merge, save, save_seen_ids,
    write_archive_index,
)

ROOT = os.path.dirname(__file__)
DATA_PATH = os.path.join(ROOT, "data", "updates.json")
ARCHIVE_DIR = os.path.join(ROOT, "data", "archive")
SEEN_IDS_PATH = os.path.join(ROOT, "data", "seen_ids.json")
CONFIG_PATH = os.path.join(ROOT, "config.yml")


def run_fetcher(name, fn, *args):
    try:
        items = fn(*args)
        print(f"[{name}] fetched {len(items)} items")
        return items
    except Exception as exc:  # noqa: BLE001 - a broken source must not kill the run
        print(f"[{name}] FAILED: {exc}", file=sys.stderr)
        return []


def main():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    fresh = []
    fresh += run_fetcher("blog", blog.fetch, config["blog"]["feed_url"])
    fresh += run_fetcher(
        "github_releases", github_releases.fetch,
        config["github_releases"]["repos"], config["github_releases"].get("auto_discover_orgs", []),
    )
    fresh += run_fetcher(
        "release_notes", release_notes.fetch,
        config["release_notes"]["index_url"], config["release_notes"]["base_url"],
    )
    fresh += run_fetcher("linkedin", linkedin_bridge.fetch, config["linkedin"].get("bridge_feed_url", ""))

    existing = load_existing(DATA_PATH)
    seen_ids = load_seen_ids(SEEN_IDS_PATH)
    today_iso = datetime.now(timezone.utc).date().isoformat()

    live, to_archive = merge(
        existing, fresh, seen_ids, today_iso,
        max_items=config["retention"]["max_items"],
        max_age_days=config["retention"]["max_age_days"],
    )

    save(DATA_PATH, live)
    save_seen_ids(SEEN_IDS_PATH, seen_ids)
    newly_archived = archive_items(ARCHIVE_DIR, to_archive)
    write_archive_index(ARCHIVE_DIR)

    print(
        f"Store now has {len(live)} live items ({len(live) - len(existing)} net new). "
        f"{len(to_archive)} items are outside the live window ({newly_archived} newly archived)."
    )


if __name__ == "__main__":
    main()
