"""Versioned help content; no connections to customer systems or mutable data."""
from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

CONTENT_ROOT = Path(__file__).with_name("help_content")


def folded(value: str) -> str:
    return "".join(char for char in unicodedata.normalize("NFKD", value.casefold()) if not unicodedata.combining(char))


def headings(body: str) -> list[dict]:
    result, used, fence = [], {}, None
    for line_number, line in enumerate(body.splitlines(), 1):
        marker = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if marker:
            if fence is None:
                fence = marker[1][0]
            elif marker[1][0] == fence:
                fence = None
            continue
        match = re.match(r"^(#{2,4})\s+(.+?)\s*#*\s*$", line) if fence is None else None
        if match:
            title = match[2]
            base = re.sub(r"[^a-z0-9]+", "-", folded(title)).strip("-") or "abschnitt"
            used[base] = used.get(base, 0) + 1
            anchor = base if used[base] == 1 else f"{base}-{used[base]}"
            result.append({"id": anchor, "title": title, "level": len(match[1]), "line": line_number})
    return result


@lru_cache(maxsize=1)
def library() -> dict:
    data = json.loads((CONTENT_ROOT / "catalog.json").read_text(encoding="utf-8"))
    articles = {}
    category_ids = {item["id"] for item in data["categories"]}
    for item in data["articles"]:
        slug = item["id"]
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug) or slug in articles:
            raise RuntimeError("Ungültige oder doppelte Hilfe-ID.")
        if item["category"] not in category_ids or item["audience"] not in {"all", "admin"}:
            raise RuntimeError("Ungültige Hilfe-Zuordnung.")
        body = (CONTENT_ROOT / f"{slug}.md").read_text(encoding="utf-8")
        articles[slug] = {**item, "body": body, "headings": headings(body)}
    for context in data["contexts"].values():
        article = articles[context["article"]]
        if context.get("anchor") and context["anchor"] not in {h["id"] for h in article["headings"]}:
            raise RuntimeError("Ein Hilfe-Verweis enthält einen unbekannten Abschnitt.")
    return {**data, "articles": articles}


def visible(article: dict, admin: bool) -> bool:
    return article["audience"] == "all" or admin


def metadata(article: dict) -> dict:
    return {key: article[key] for key in ("id", "title", "summary", "category", "audience", "keywords")}


def catalog(admin: bool, query: str = "") -> dict:
    data = library()
    terms = folded(query).split()
    rows = []
    for article in data["articles"].values():
        if not visible(article, admin):
            continue
        title, summary = folded(article["title"]), folded(article["summary"])
        keywords = folded(" ".join(article["keywords"]))
        text = " ".join((title, summary, keywords, folded(article["body"])))
        if not all(term in text for term in terms):
            continue
        score = sum(8 * (term in title) + 4 * (term in keywords) + 2 * (term in summary) for term in terms)
        rows.append((score, metadata(article)))
    if terms:
        rows.sort(key=lambda row: (-row[0], row[1]["title"]))
    categories = [item for item in data["categories"] if any(visible(a, admin) and a["category"] == item["id"] for a in data["articles"].values())]
    return {"content_version": data["content_version"], "categories": categories, "articles": [item for _, item in rows]}


def article(slug: str, admin: bool) -> dict | None:
    data = library()
    item = data["articles"].get(slug)
    if item is None or not visible(item, admin):
        return None
    related = [metadata(a) for a in data["articles"].values() if a["id"] != slug and a["category"] == item["category"] and visible(a, admin)]
    return {**metadata(item), "body": item["body"], "headings": item["headings"], "quick_steps": item["quick_steps"],
            "content_version": data["content_version"], "related": related}


def context(key: str, admin: bool) -> dict | None:
    data = library()
    entry = data["contexts"].get(key)
    if entry is None:
        return None
    item = data["articles"][entry["article"]]
    if not visible(item, admin):
        return None
    return {"id": key, "article_id": item["id"], "title": entry.get("title", item["title"]),
            "summary": entry.get("summary", item["summary"]), "steps": entry.get("steps", item["quick_steps"]),
            "anchor": entry.get("anchor"), "content_version": data["content_version"]}
