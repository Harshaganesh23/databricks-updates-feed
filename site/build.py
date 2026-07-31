"""Build the static dashboard: copies the HTML shell, writes data.json, generates feed.xml."""

import json
import os
import shutil
from datetime import datetime, timezone
from email.utils import format_datetime
from xml.etree import ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(ROOT, "data", "updates.json")
ARCHIVE_SRC_DIR = os.path.join(ROOT, "data", "archive")
SITE_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(ROOT, "dist")
ARCHIVE_DIST_DIR = os.path.join(DIST_DIR, "archive")

SITE_URL = os.environ.get("SITE_URL", "https://example.github.io/databricks-updates-feed/")
FEED_ITEM_LIMIT = 100


def load_items():
    if not os.path.exists(DATA_PATH):
        return []
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def write_data_json(items, generated_at):
    payload = {"generated_at": generated_at, "items": items}
    with open(os.path.join(DIST_DIR, "data.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def sort_key(item):
    return item.get("published") or item.get("first_seen") or ""


def build_feed_xml(items, generated_at):
    rss = ET.Element("rss", {"version": "2.0"})
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = "Databricks Updates"
    ET.SubElement(channel, "link").text = SITE_URL
    ET.SubElement(channel, "description").text = "Aggregated Databricks blog posts, release notes, and GitHub releases."
    ET.SubElement(channel, "lastBuildDate").text = format_datetime(datetime.fromisoformat(generated_at))

    ordered = sorted(items, key=sort_key, reverse=True)[:FEED_ITEM_LIMIT]
    for item in ordered:
        entry = ET.SubElement(channel, "item")
        ET.SubElement(entry, "title").text = f"[{item['source_label']}] {item['title']}"
        ET.SubElement(entry, "link").text = item["url"]
        ET.SubElement(entry, "guid").text = item["url"]
        if item.get("summary"):
            ET.SubElement(entry, "description").text = item["summary"]
        date_str = item.get("published") or item.get("first_seen")
        if date_str:
            try:
                dt = datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
                ET.SubElement(entry, "pubDate").text = format_datetime(dt)
            except ValueError:
                pass

    tree = ET.ElementTree(rss)
    ET.indent(tree, space="  ")
    tree.write(os.path.join(DIST_DIR, "feed.xml"), encoding="utf-8", xml_declaration=True)


def copy_archive():
    if os.path.isdir(ARCHIVE_DIST_DIR):
        shutil.rmtree(ARCHIVE_DIST_DIR)
    if os.path.isdir(ARCHIVE_SRC_DIR):
        shutil.copytree(ARCHIVE_SRC_DIR, ARCHIVE_DIST_DIR)
    else:
        os.makedirs(ARCHIVE_DIST_DIR, exist_ok=True)
        with open(os.path.join(ARCHIVE_DIST_DIR, "index.json"), "w", encoding="utf-8") as f:
            f.write("[]\n")


def main():
    os.makedirs(DIST_DIR, exist_ok=True)
    shutil.copyfile(os.path.join(SITE_DIR, "index.html"), os.path.join(DIST_DIR, "index.html"))

    items = load_items()
    generated_at = datetime.now(timezone.utc).isoformat()

    write_data_json(items, generated_at)
    build_feed_xml(items, generated_at)
    copy_archive()

    print(f"Built dashboard with {len(items)} live items into {DIST_DIR} (archive copied alongside)")


if __name__ == "__main__":
    main()
