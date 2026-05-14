from __future__ import annotations

import html
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any

import httpx
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models import MarketEvent
from app.services.event_classifier import EventClassifier


DEFAULT_RSS_SOURCES = [
    {
        "source": "cbr_news",
        "url": "https://www.cbr.ru/rss/RssNews",
    },
    {
        "source": "cbr_events",
        "url": "https://www.cbr.ru/rss/eventrss",
    },
    {
        "source": "cbr_press",
        "url": "https://www.cbr.ru/rss/RssPress",
    },
]


@dataclass
class RSSItem:
    title: str
    description: str
    link: str | None
    published: str | None


async def fetch_rss_items(url: str, limit: int = 20) -> list[RSSItem]:
    async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as client:
        response = await client.get(url, headers={"User-Agent": "RussianMarketAIAnalyst/0.1"})
        response.raise_for_status()

    root = ET.fromstring(response.content)

    items = root.findall(".//item")
    if not items:
        items = root.findall(".//{http://www.w3.org/2005/Atom}entry")

    result: list[RSSItem] = []

    for item in items[:limit]:
        title = clean_text(find_text(item, ["title"]))
        description = clean_text(find_text(item, ["description", "summary", "content"]))
        link = clean_text(find_text(item, ["link"])) or None
        published = clean_text(find_text(item, ["pubDate", "published", "updated"])) or None

        atom_link = item.find("{http://www.w3.org/2005/Atom}link")
        if not link and atom_link is not None:
            link = atom_link.attrib.get("href")

        if not title and not description:
            continue

        result.append(
            RSSItem(
                title=title or "Без заголовка",
                description=description,
                link=link,
                published=published,
            )
        )

    return result


def find_text(element: ET.Element, names: list[str]) -> str:
    for name in names:
        child = element.find(name)
        if child is not None and child.text:
            return child.text

        child = element.find(f"{{http://www.w3.org/2005/Atom}}{name}")
        if child is not None and child.text:
            return child.text

    return ""


def clean_text(value: str | None) -> str:
    if not value:
        return ""

    value = html.unescape(value)
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


async def ingest_rss_feed(
    db: Session,
    url: str,
    source: str = "rss",
    limit: int = 20,
) -> dict[str, Any]:
    items = await fetch_rss_items(url=url, limit=limit)

    classifier = EventClassifier()

    inserted = 0
    duplicates = 0
    analyzed = 0
    errors: list[str] = []

    for item in items:
        existing = None

        if item.link:
            existing = db.scalar(select(MarketEvent).where(MarketEvent.url == item.link))

        if existing is None:
            existing = db.scalar(
                select(MarketEvent).where(
                    MarketEvent.source == source,
                    MarketEvent.title == item.title,
                )
            )

        if existing:
            duplicates += 1
            continue

        text = item.description or item.title
        full_text = f"{item.title}. {text}".strip()

        try:
            analysis = await classifier.analyze(full_text, title=item.title)
            analyzed += 1

            event = MarketEvent(
                title=item.title,
                text=full_text,
                source=source,
                url=item.link,
                importance=analysis.importance,
                impact=analysis.impact,
                affected_assets=",".join(analysis.affected_assets),
                reasoning=analysis.reasoning,
                raw_analysis=analysis.model_dump_json(ensure_ascii=False),
            )
            db.add(event)
            inserted += 1

        except Exception as exc:
            errors.append(f"{item.title}: {exc}")

    db.commit()

    return {
        "source": source,
        "url": url,
        "items_fetched": len(items),
        "inserted": inserted,
        "duplicates": duplicates,
        "analyzed": analyzed,
        "errors": errors,
    }


async def ingest_default_rss_sources(
    db: Session,
    limit_per_source: int = 10,
) -> dict[str, Any]:
    results = []

    for source in DEFAULT_RSS_SOURCES:
        result = await ingest_rss_feed(
            db=db,
            url=source["url"],
            source=source["source"],
            limit=limit_per_source,
        )
        results.append(result)

    return {
        "sources_count": len(DEFAULT_RSS_SOURCES),
        "results": results,
        "total_inserted": sum(item["inserted"] for item in results),
        "total_duplicates": sum(item["duplicates"] for item in results),
    }


def build_events_radar(
    db: Session,
    limit: int = 30,
    min_importance: int = 1,
    ticker: str | None = None,
) -> dict[str, Any]:
    events = db.scalars(
        select(MarketEvent)
        .order_by(desc(MarketEvent.created_at))
        .limit(300)
    ).all()

    rows: list[dict[str, Any]] = []

    for event in events:
        if event.source == "manual":
            continue

        analysis = parse_raw_analysis(event.raw_analysis)
        affected_assets = parse_assets(event.affected_assets)

        if event.importance is not None and event.importance < min_importance:
            continue

        if ticker:
            t = ticker.upper().strip()
            if t not in affected_assets:
                continue

        rows.append(
            {
                "id": event.id,
                "title": event.title,
                "source": event.source,
                "url": event.url,
                "created_at": event.created_at.isoformat() if event.created_at else None,
                "importance": event.importance,
                "impact": event.impact,
                "event_type": analysis.get("event_type", "other"),
                "affected_assets": affected_assets,
                "affected_sectors": analysis.get("affected_sectors", []),
                "time_horizon": analysis.get("time_horizon"),
                "confidence": analysis.get("confidence"),
                "reasoning": event.reasoning,
                "watch_next": analysis.get("watch_next", []),
            }
        )

    rows = sorted(
        rows,
        key=lambda item: (
            item["importance"] or 0,
            item["created_at"] or "",
        ),
        reverse=True,
    )[:limit]

    return {
        "events_count": len(rows),
        "min_importance": min_importance,
        "ticker_filter": ticker.upper().strip() if ticker else None,
        "top_events": rows,
        "summary": build_events_summary(rows),
        "by_event_type": aggregate_by(rows, "event_type"),
        "by_impact": aggregate_by(rows, "impact"),
        "by_asset": aggregate_assets(rows),
    }


def parse_raw_analysis(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}

    try:
        return json.loads(raw)
    except Exception:
        return {}


def parse_assets(value: str | None) -> list[str]:
    if not value:
        return []

    return [item.strip().upper() for item in value.split(",") if item.strip()]


def aggregate_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    result: dict[str, int] = {}

    for row in rows:
        value = row.get(key) or "unknown"
        result[value] = result.get(value, 0) + 1

    return dict(sorted(result.items(), key=lambda item: item[1], reverse=True))


def aggregate_assets(rows: list[dict[str, Any]]) -> dict[str, int]:
    result: dict[str, int] = {}

    for row in rows:
        for asset in row.get("affected_assets", []):
            result[asset] = result.get(asset, 0) + 1

    return dict(sorted(result.items(), key=lambda item: item[1], reverse=True))


def build_events_summary(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "Событий по заданным фильтрам не найдено."

    important = [item for item in rows if (item.get("importance") or 0) >= 8]

    if important:
        titles = "; ".join(item["title"] or "Без заголовка" for item in important[:3])
        return f"Найдены важные события: {titles}."

    top = rows[0]
    return f"Последнее значимое событие: {top.get('title') or 'Без заголовка'}."
