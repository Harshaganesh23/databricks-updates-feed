"""LinkedIn fetcher — optional, best-effort.

LinkedIn has no public API for reading an arbitrary company page's post feed.
This fetcher only consumes a user-supplied RSS bridge URL (e.g. an RSS.app
export pointed at the Databricks company page). If unset, it skips cleanly —
the rest of the pipeline never depends on this source.
"""

from datetime import datetime, timezone

import feedparser

from .common import html_to_summary_text, make_item


def fetch(bridge_feed_url: str) -> list:
    if not bridge_feed_url:
        return []

    parsed = feedparser.parse(bridge_feed_url)
    items = []
    for entry in parsed.entries:
        published = None
        if getattr(entry, "published_parsed", None):
            published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc).date().isoformat()

        items.append(make_item(
            source="linkedin",
            source_label="LinkedIn",
            title=entry.title,
            url=entry.link,
            published=published,
            summary=html_to_summary_text(getattr(entry, "summary", "")),
        ))
    return items
