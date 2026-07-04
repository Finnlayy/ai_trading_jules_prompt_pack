"""Async RSS news aggregator for MSN Finance and Yahoo Finance.

Uses httpx + xml.etree.ElementTree to avoid feedparser dependency.
"""
from __future__ import annotations

from app.core.utils import strip_html, iso_from_pubdate

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

import httpx

DEFAULT_TIMEOUT = 15.0

# Feeds we monitor
# NOTE: MSN Finance and Yahoo Finance RSS feeds are deprecated (return 404).
# We use reliable alternatives: BBC Business (general finance) and CoinDesk (crypto).
BBC_BUSINESS_RSS = "https://feeds.bbci.co.uk/news/business/rss.xml"
COINDESK_RSS = "https://www.coindesk.com/arc/outboundfeeds/rss/"


@dataclass(frozen=True)
class NewsItem:
    source: str
    title: str
    link: str
    published: str
    summary: str = ""
    fetched_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def _parse_rss(xml_bytes: bytes, source_label: str) -> List[NewsItem]:
    """Parse RSS/Atom XML into NewsItem list."""
    items: List[NewsItem] = []
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return items

    # Handle RSS 2.0
    channel = root.find("channel")
    if channel is not None:
        for entry in channel.findall("item"):
            title = (entry.findtext("title") or "").strip()
            link = (entry.findtext("link") or "").strip()
            pub = (entry.findtext("pubDate") or entry.findtext("pubdate") or "").strip()
            desc = (entry.findtext("description") or "").strip()
            if title:
                items.append(
                    NewsItem(
                        source=source_label,
                        title=title,
                        link=link,
                        published=iso_from_pubdate(pub),
                        summary=strip_html(desc)[:300],
                    )
                )
        return items

    # Handle Atom
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    for entry in root.findall("atom:entry", ns):
        title = (entry.findtext("atom:title", "", ns) or "").strip()
        link_elem = entry.find("atom:link", ns)
        link = link_elem.get("href", "") if link_elem is not None else ""
        pub = (
            entry.findtext("atom:published", "", ns)
            or entry.findtext("atom:updated", "", ns)
            or ""
        ).strip()
        desc = (entry.findtext("atom:summary", "", ns) or entry.findtext("atom:content", "", ns) or "").strip()
        if title:
            items.append(
                NewsItem(
                    source=source_label,
                    title=title,
                    link=link,
                    published=iso_from_pubdate(pub),
                    summary=strip_html(desc)[:300],
                )
            )
    return items


class NewsAggregator:
    """Fetches and caches news from MSN Finance and Yahoo Finance RSS feeds."""

    def __init__(self, max_items: int = 50) -> None:
        self.max_items = max_items
        self._cache: List[NewsItem] = []
        self._last_fetch: Optional[datetime] = None
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, follow_redirects=True)
        return self._client

    async def fetch(self, source: str = "all") -> List[NewsItem]:
        """Fetch news items. source can be 'msn', 'yahoo', or 'all'."""
        client = await self._get_client()
        all_items: List[NewsItem] = []
        errors: List[str] = []

        async def _fetch_one(url: str, label: str) -> None:
            try:
                response = await client.get(url)
                response.raise_for_status()
                items = _parse_rss(response.content, label)
                all_items.extend(items)
            except Exception as e:
                errors.append(f"{label}: {e}")

        tasks = []
        if source in ("all", "bbc"):
            tasks.append(_fetch_one(BBC_BUSINESS_RSS, "BBC Business"))
        if source in ("all", "coindesk"):
            tasks.append(_fetch_one(COINDESK_RSS, "CoinDesk"))

        for t in tasks:
            await t

        # Sort by published date desc, truncate
        all_items.sort(key=lambda x: x.published, reverse=True)
        self._cache = all_items[: self.max_items]
        self._last_fetch = datetime.now(timezone.utc)
        return self._cache

    def get_cached(self) -> List[NewsItem]:
        return self._cache

    def last_fetch_iso(self) -> Optional[str]:
        return self._last_fetch.isoformat() if self._last_fetch else None

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()


# Global singleton
news_aggregator_instance = NewsAggregator()
