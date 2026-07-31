"""Shared helpers: normalized item schema, storage, and merge/dedupe logic."""

import hashlib
import html
import json
import os
import re
from datetime import datetime, timedelta, timezone

_TAG_LI_OPEN = re.compile(r"<li[^>]*>", re.IGNORECASE)
_TAG_BREAK = re.compile(r"</p>|<br\s*/?>|</li>|</h[1-6]>", re.IGNORECASE)
_TAG_ANY = re.compile(r"<[^>]+>")
_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_BLANK_RUN = re.compile(r"\n{3,}")
_SPACE_RUN = re.compile(r"[ \t]+")


def html_to_summary_text(raw_html: str, max_chars: int = 1800) -> str:
    """Turn a chunk of (possibly untrusted) source HTML into safe, readable
    plain text: list items become "- " bullet lines, paragraph/line breaks
    become newlines, everything else is stripped. Output is plain text only
    (no tags survive), so it's safe to render with textContent client-side."""
    if not raw_html:
        return ""

    text = _COMMENT.sub("", raw_html)
    text = _TAG_LI_OPEN.sub("\n- ", text)
    text = _TAG_BREAK.sub("\n", text)
    text = _TAG_ANY.sub("", text)
    text = html.unescape(text)
    text = _SPACE_RUN.sub(" ", text)
    text = "\n".join(line.strip() for line in text.split("\n"))
    text = _BLANK_RUN.sub("\n\n", text).strip()

    if len(text) > max_chars:
        cut = text.rfind("\n", 0, max_chars)
        if cut < max_chars * 0.4:
            cut = text.rfind(" ", 0, max_chars)
        if cut <= 0:
            cut = max_chars
        text = text[:cut].rstrip() + "…"

    return text


def make_id(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]


# Categories mirror Databricks' own live top-level product navigation
# (databricks.com mega-menu, verified 2026-07-29 — not an invented taxonomy),
# one entry per nav item: AI Assistant, Application Development, Artificial
# Intelligence, Business Intelligence, Customer Data Platform, Database, Data
# Engineering, Data Warehousing, Governance, Security, Sharing, and Platform
# Overview (their own catch-all descriptor, used here as the fallback for
# anything that doesn't map to a specific product pillar — e.g. generic
# runtime/cluster/serverless-compute updates, which they don't market as a
# distinct pillar either).
#
# Ordered so more specific categories are checked before general ones when a
# title/summary happens to match keywords from more than one bucket — e.g.
# "Genie Agent" (Business Intelligence) is checked before the bare "agent"
# keyword (Artificial Intelligence) would otherwise catch it.
#
# Keywords are matched with a *leading* word boundary only (see categorize()),
# not substring containment — short stems like "rag" or "git" would otherwise
# false-positive inside unrelated words ("storage", "digit"). The leading-only
# boundary still lets intentional prefixes match naturally, e.g. "autoscal"
# inside "autoscaling", or "fine-tun" inside "fine-tuning".
CATEGORIES = [
    ("AI Assistant", [
        "genie code", "ai assistant", "agentic coworker",
    ]),
    ("Business Intelligence", [
        "dashboard", "ai/bi", "genie one", "genie agent", "genie space",
        "lakeview", "metric view", "sql alert", "visualization",
    ]),
    ("Data Warehousing", [
        "sql warehouse", "dbsql", "databricks sql", "serverless sql",
        "statement timeout", "query federation", "warehouse",
    ]),
    ("Governance", [
        "unity catalog", "rbac", "role-based access", "access control", "audit",
        "permission", "credential", "secrets", "governed tags", "governance hub",
        "data classification", "volumes", "catalog", "token",
    ]),
    ("Security", [
        "security profile", "encryption", "private link", "ingress control",
        "compliance",
    ]),
    ("Sharing", [
        "delta sharing", "clean room", "data sharing",
    ]),
    ("Database", [
        "lakebase", "postgres",
    ]),
    ("Application Development", [
        "databricks apps", "appkit", "cli", "sdk", "notebook", "bundle",
        "dab", "rest api", "terraform", "git",
    ]),
    ("Artificial Intelligence", [
        "mlflow", "model serving", "foundation model",
        "ai_query", "ai_classify", "ai_extract", "ai_gen", "ai_forecast",
        "ai function", "llm", "claude", "gpt", "gemini", "glm", "inkling",
        "embedding", "vector search", "rag", "model catalog", "fine-tun",
        "copilot", "anthropic", "openai", "agentic", "agent",
    ]),
    ("Data Engineering", [
        "lakeflow", "pipeline", "streaming", "ingestion", "etl",
        "structured streaming", "cdc", "kafka", "zerobus",
        "declarative pipeline", "dlt", "delta live table", "auto loader",
        "connector", "orchestrat", "delta lake", "iceberg",
        "materialized view", "variant", "replace where", "checkpoint",
    ]),
    ("Customer Data Platform", [
        "customer data platform",
    ]),
]

_KEYWORD_PATTERNS = [
    (name, [re.compile(r"\b" + re.escape(kw), re.IGNORECASE) for kw in keywords])
    for name, keywords in CATEGORIES
]

# Shortcut classification for GitHub repos where the title text alone may not
# carry a clean topic keyword (e.g. terse build/version-bump titles).
REPO_CATEGORY_HINTS = {
    "apache/spark": "Data Engineering",
    "delta-io/delta": "Data Engineering",
    "mlflow/mlflow": "Artificial Intelligence",
    "databricks/databricks-sdk-py": "Application Development",
    "databricks/cli": "Application Development",
    "databrickslabs/dqx": "Governance",
}

FALLBACK_CATEGORY = "Platform Overview"


def categorize(title: str, summary: str = "", repo_hint: str | None = None) -> str:
    if repo_hint and repo_hint in REPO_CATEGORY_HINTS:
        return REPO_CATEGORY_HINTS[repo_hint]

    text = f"{title} {summary}"
    for name, patterns in _KEYWORD_PATTERNS:
        if any(p.search(text) for p in patterns):
            return name
    return FALLBACK_CATEGORY


def make_item(source: str, source_label: str, title: str, url: str,
              published: str | None, summary: str = "", tags: list | None = None,
              category_hint: str | None = None) -> dict:
    """Build a normalized item. `published` must be an ISO 8601 date/datetime string or None."""
    title = title.strip()
    summary = (summary or "").strip()
    return {
        "id": make_id(url),
        "source": source,
        "source_label": source_label,
        "title": title,
        "url": url,
        "published": published,
        "first_seen": None,  # filled in by merge() on first insert
        "summary": summary,
        "category": categorize(title, summary, repo_hint=category_hint),
        "tags": tags or [],
    }


def load_existing(path: str) -> list:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save(path: str, items: list) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2, ensure_ascii=False)
        f.write("\n")


def sort_key(item: dict):
    return item.get("published") or item.get("first_seen") or ""


def month_bucket(item: dict) -> str:
    key = sort_key(item)
    return key[:7] if key else "undated"  # "YYYY-MM"


def load_seen_ids(path: str) -> dict:
    """{id: first_seen_date} for every item ever encountered, live or
    archived — kept separately from the live store so that a source
    re-fetching its full history (release_notes.py fetches ~2000+ entries
    every run) doesn't make an already-archived item look "new" again and
    reset its first_seen to today."""
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_seen_ids(path: str, seen: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(seen, f, indent=2, ensure_ascii=False)
        f.write("\n")


def merge(existing: list, fresh: list, seen_ids: dict, today_iso: str,
          max_items: int, max_age_days: int):
    """Merge freshly fetched items into the existing live store.

    - Genuinely new items get first_seen = today_iso (and are recorded into
      seen_ids, mutated in place).
    - Items re-fetched after already being archived reuse their original
      first_seen from seen_ids, rather than resetting it.
    - Existing live items keep their original first_seen/published untouched.

    Returns (live, to_archive) — to_archive holds everything that falls
    outside the count/age retention window. Callers are expected to persist
    it via archive_items(), not discard it.
    """
    by_id = {item["id"]: item for item in existing}

    for item in fresh:
        if item["id"] in by_id:
            continue  # already live; its stored first_seen is already correct
        item["first_seen"] = seen_ids.get(item["id"], today_iso)
        seen_ids[item["id"]] = item["first_seen"]
        by_id[item["id"]] = item

    all_items = sorted(by_id.values(), key=sort_key, reverse=True)

    live = all_items
    if max_age_days:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=max_age_days)).date().isoformat()
        live = [i for i in live if sort_key(i) >= cutoff]
    if max_items:
        live = live[:max_items]

    live_ids = {i["id"] for i in live}
    to_archive = [i for i in all_items if i["id"] not in live_ids]

    return live, to_archive


def archive_items(archive_dir: str, items: list) -> int:
    """Append items into monthly archive files (data/archive/YYYY-MM.json),
    deduped by id. Returns how many were genuinely new to the archive."""
    if not items:
        return 0

    os.makedirs(archive_dir, exist_ok=True)
    by_month = {}
    for item in items:
        by_month.setdefault(month_bucket(item), []).append(item)

    new_count = 0
    for month, month_items in by_month.items():
        path = os.path.join(archive_dir, f"{month}.json")
        by_id = {i["id"]: i for i in load_existing(path)}
        for item in month_items:
            if item["id"] not in by_id:
                new_count += 1
            by_id[item["id"]] = item
        save(path, sorted(by_id.values(), key=sort_key, reverse=True))

    return new_count


def write_archive_index(archive_dir: str) -> None:
    """Small manifest of available archive months + counts, so the static
    frontend can list them without directory-listing support."""
    months = []
    if os.path.isdir(archive_dir):
        for fname in sorted(os.listdir(archive_dir), reverse=True):
            if fname == "index.json" or not fname.endswith(".json"):
                continue
            items = load_existing(os.path.join(archive_dir, fname))
            months.append({"month": fname[:-5], "count": len(items)})
    save(os.path.join(archive_dir, "index.json"), months)
