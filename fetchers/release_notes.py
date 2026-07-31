"""Databricks release notes fetcher.

docs.databricks.com has no RSS for release notes, and the index page is
client-rendered — but it ships a server-rendered sidebar nav linking to every
historical entry, as /aws/en/release-notes/product/{year}/{month}#{slug}.
We parse that for titles, then additionally fetch each *recent* month's own
page (confirmed to contain a real paragraph of body text under each heading,
not just a title) to pull a genuine summary instead of a generated one-liner.
Older months are left with the generated fallback to avoid re-fetching dozens
of month pages every day for entries that will age out of retention anyway.

Each enriched entry's body starts with its own exact publish date (e.g.
"July 26, 2026") — we parse that out for a precise `published` date instead
of approximating to end-of-month, and strip it from the summary text (it was
otherwise showing up as a redundant one-line "teaser" that was just the date
again). Only entries we couldn't enrich (older months, or a failed fetch)
fall back to the end-of-month approximation, tagged "approx-date" so the UI
renders those as e.g. "July 2026" rather than a false-precision exact day.
"""

import calendar
import html
import re
from datetime import date

import requests

from .common import html_to_summary_text, make_item

_MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
_MONTHS = {name.lower(): i + 1 for i, name in enumerate(_MONTH_NAMES)}

_LINK_RE = re.compile(
    r'<a[^>]*href=["\']?(/aws/en/release-notes/product/(\d{4})/([a-z]+)#([a-z0-9-]+))["\']?[^>]*>(.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)
_H2_RE = re.compile(r'<h2[^>]*\bid=["\']?([a-z0-9-]+)["\']?[^>]*>.*?</h2>', re.IGNORECASE | re.DOTALL)
_LEADING_DATE_RE = re.compile(r"^([A-Za-z]+) (\d{1,2}), (\d{4})\s*\n+")

RECENT_MONTHS_TO_ENRICH = 4
_HEADERS = {"User-Agent": "databricks-updates-feed/1.0"}


def _clean_text(raw: str) -> str:
    text = re.sub(r"<!--.*?-->", "", raw, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).strip()


def _recent_year_months(today: date, count: int):
    year, month = today.year, today.month
    result = []
    for _ in range(count):
        result.append((year, month))
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return set(result)


def _fetch_month_bodies(base_url: str, year: int, month_num: int):
    """Fetch one month's page; return ({slug: body_text}, {slug: exact_iso_date})
    for each heading — the exact date is parsed from the body's own leading
    date line and stripped out of the returned body text."""
    month_name = _MONTH_NAMES[month_num - 1].lower()
    url = f"{base_url}/aws/en/release-notes/product/{year}/{month_name}"
    resp = requests.get(url, timeout=30, headers=_HEADERS)
    resp.raise_for_status()
    text = resp.text

    headings = list(_H2_RE.finditer(text))
    bodies = {}
    exact_dates = {}
    for i, m in enumerate(headings):
        slug = m.group(1)
        start = m.end()
        end = headings[i + 1].start() if i + 1 < len(headings) else start + 3000
        body = html_to_summary_text(text[start:end])

        date_match = _LEADING_DATE_RE.match(body)
        if date_match:
            month_name_found, day, year_found = date_match.groups()
            month_num_found = _MONTHS.get(month_name_found.lower())
            if month_num_found:
                exact_dates[slug] = f"{year_found}-{month_num_found:02d}-{int(day):02d}"
            body = body[date_match.end():]

        bodies[slug] = body
    return bodies, exact_dates


def fetch(index_url: str, base_url: str) -> list:
    resp = requests.get(index_url, timeout=30, headers=_HEADERS)
    resp.raise_for_status()

    raw_entries = []
    seen_urls = set()
    for href, year, month_name, slug, raw_text in _LINK_RE.findall(resp.text):
        month_num = _MONTHS.get(month_name.lower())
        if not month_num:
            continue
        full_url = base_url + href
        if full_url in seen_urls:
            continue
        seen_urls.add(full_url)

        title = _clean_text(raw_text)
        if not title:
            continue
        raw_entries.append({
            "year": int(year), "month_num": month_num, "slug": slug,
            "title": title, "url": full_url,
        })

    recent = _recent_year_months(date.today(), RECENT_MONTHS_TO_ENRICH)
    bodies_by_month = {}
    exact_dates_by_month = {}
    for (year, month_num) in {(e["year"], e["month_num"]) for e in raw_entries} & recent:
        try:
            bodies, exact_dates = _fetch_month_bodies(base_url, year, month_num)
        except Exception as exc:  # noqa: BLE001 - a slow/broken month page shouldn't kill the run
            print(f"[release_notes] failed to enrich {year}-{month_num:02d}: {exc}")
            bodies, exact_dates = {}, {}
        bodies_by_month[(year, month_num)] = bodies
        exact_dates_by_month[(year, month_num)] = exact_dates

    items = []
    for e in raw_entries:
        key = (e["year"], e["month_num"])
        month_label = _MONTH_NAMES[e["month_num"] - 1]

        body = bodies_by_month.get(key, {}).get(e["slug"], "")
        summary = body or f"Databricks platform update — {month_label} {e['year']}."

        exact_date = exact_dates_by_month.get(key, {}).get(e["slug"])
        if exact_date:
            published, tags = exact_date, []
        else:
            last_day = calendar.monthrange(e["year"], e["month_num"])[1]
            published = f"{e['year']}-{e['month_num']:02d}-{last_day:02d}"
            tags = ["approx-date"]

        items.append(make_item(
            source="release_notes",
            source_label="Release Notes",
            title=e["title"],
            url=e["url"],
            published=published,
            summary=summary,
            tags=tags,
        ))
    return items
