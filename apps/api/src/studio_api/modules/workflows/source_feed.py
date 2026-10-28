"""Read a curated NASA Earth Observatory RSS feed without accepting arbitrary URLs."""

from __future__ import annotations

import hashlib
import html
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from urllib.parse import urlsplit, urlunsplit

import httpx

from studio_api.core.errors import ErrorCode, StudioError

NASA_EARTH_FEED = "https://science.nasa.gov/feed/earth-observatory/image-of-the-day"
CONTENT_NAMESPACE = "{http://purl.org/rss/1.0/modules/content/}encoded"
SOURCE_PREFIX = "https://science.nasa.gov/earth/earth-observatory/"
MAX_FEED_BYTES = 2_000_000
MAX_AGE_DAYS = 7
UNSUITABLE = re.compile(
    r"\b(?:death|killed|injur\w*|war|weapon\w*|wildfire\w*|fires?|"
    r"flood\w*|hurricane\w*|cyclone\w*|earthquake\w*|disaster\w*)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SourceItem:
    title: str
    summary: str
    url: str
    published_at: datetime
    image_url: str | None = None
    feed_url: str = NASA_EARTH_FEED

    @property
    def source_hash(self) -> str:
        return hashlib.sha256(self.url.encode()).hexdigest()


class _PlainText(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def _clean_summary(fragment: str) -> str:
    first_paragraph = fragment.split("</p>", 1)[0]
    parser = _PlainText()
    parser.feed(first_paragraph)
    return re.sub(r"\s+", " ", html.unescape(" ".join(parser.parts))).strip()[:800]


def _article_summary(node: ET.Element) -> str:
    content = node.findtext(CONTENT_NAMESPACE) or ""
    paragraphs = re.findall(r"<p\b[^>]*>(.*?)</p>", content, re.IGNORECASE | re.DOTALL)
    facts = [_clean_summary(paragraph) for paragraph in paragraphs[:5]]
    facts = [paragraph for paragraph in facts if len(paragraph) >= 40]
    if facts:
        return " ".join(facts[:3])[:1800]
    return _clean_summary(node.findtext("description") or "")


def _article_image(node: ET.Element) -> str | None:
    content = node.findtext(CONTENT_NAMESPACE) or ""
    match = re.search(r'<img\b[^>]*\bsrc="([^"]+)"', content, re.IGNORECASE)
    if match is None:
        return None
    url = html.unescape(match.group(1))
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.netloc != "assets.science.nasa.gov":
        return None
    return url


def parse_nasa_feed(data: bytes, now: datetime | None = None) -> list[SourceItem]:
    if len(data) > MAX_FEED_BYTES or b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise StudioError(ErrorCode.POLICY_REJECTED, "Invalid or oversized source feed")
    # NASA's feed currently omits a space between two namespace attributes.
    repaired = data.replace(b'"xmlns:media=', b'" xmlns:media=')
    try:
        root = ET.fromstring(repaired)
    except ET.ParseError as exc:
        raise StudioError(ErrorCode.MODEL_UNAVAILABLE, "Source feed is malformed") from exc
    current = now or datetime.now(UTC)
    items: list[SourceItem] = []
    for node in root.findall("./channel/item"):
        title = re.sub(r"\s+", " ", html.unescape(node.findtext("title") or "")).strip()[:300]
        summary = _article_summary(node)
        raw_url = (node.findtext("link") or "").strip()
        parsed = urlsplit(raw_url)
        url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
        if not url.startswith(SOURCE_PREFIX) or not title or len(summary) < 25:
            continue
        try:
            published = parsedate_to_datetime(node.findtext("pubDate") or "").astimezone(UTC)
        except (TypeError, ValueError):
            continue
        if published < current - timedelta(days=MAX_AGE_DAYS) or published > current + timedelta(
            hours=2
        ):
            continue
        if UNSUITABLE.search(f"{title} {summary}"):
            continue
        items.append(
            SourceItem(
                title=title,
                summary=summary,
                url=url,
                published_at=published,
                image_url=_article_image(node),
            )
        )
    return sorted(items, key=lambda item: item.published_at, reverse=True)


async def fetch_nasa_earth_items(client: httpx.AsyncClient | None = None) -> list[SourceItem]:
    async def fetch(selected: httpx.AsyncClient) -> list[SourceItem]:
        try:
            response = await selected.get(NASA_EARTH_FEED)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise StudioError(
                ErrorCode.MODEL_UNAVAILABLE, "NASA source feed is unavailable"
            ) from exc
        return parse_nasa_feed(response.content)

    if client is not None:
        return await fetch(client)
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as temporary:
        return await fetch(temporary)
