"""Databricks blog fetcher — native RSS feed, enriched with each post's real
meta description (the RSS <description> is only a ~90-character teaser)."""

import re
from datetime import datetime, timezone

import feedparser
import requests

from .common import html_to_summary_text, make_item

_META_DESCRIPTION_RE = re.compile(
    r'<meta[^>]+name="description"[^>]+content="([^"]*)"|'
    r'<meta[^>]+content="([^"]*)"[^>]+name="description"',
    re.IGNORECASE,
)


def _fetch_real_summary(post_url: str, fallback: str) -> str:
    try:
        resp = requests.get(post_url, timeout=20, headers={"User-Agent": "databricks-updates-feed/1.0"})
        resp.raise_for_status()
        match = _META_DESCRIPTION_RE.search(resp.text)
        if match:
            content = match.group(1) or match.group(2)
            cleaned = html_to_summary_text(content)
            if cleaned:
                return cleaned
    except Exception:
        pass
    return html_to_summary_text(fallback)


def fetch(feed_url: str) -> list:
    parsed = feedparser.parse(feed_url)
    items = []
    for entry in parsed.entries:
        published = None
        if getattr(entry, "published_parsed", None):
            published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc).date().isoformat()

        tags = [t.term for t in getattr(entry, "tags", [])] if getattr(entry, "tags", None) else []
        summary = _fetch_real_summary(entry.link, getattr(entry, "summary", ""))

        items.append(make_item(
            source="databricks_blog",
            source_label="Databricks Blog",
            title=entry.title,
            url=entry.link,
            published=published,
            summary=summary,
            tags=tags,
        ))
    return items
