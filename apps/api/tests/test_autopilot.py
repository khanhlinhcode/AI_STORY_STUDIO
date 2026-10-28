from __future__ import annotations

import io
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from uuid import UUID

import pytest
from httpx import AsyncClient
from PIL import Image
from workers.dispatcher.tasks import _reconcile_expired_leases

from studio_api.core.db import SessionFactory
from studio_api.modules.models.adapters.ollama import (
    _has_unsupported_geography,
    _has_unsupported_season,
    _has_unverified_long_time_claim,
    _source_factual_hints,
)
from studio_api.modules.models.adapters.source_image import nasa_source_card
from studio_api.modules.projects.models import Project
from studio_api.modules.workflows import automation_router
from studio_api.modules.workflows.autopilot import produce_source_story, reserve_latest_source
from studio_api.modules.workflows.models import SourceStory
from studio_api.modules.workflows.source_feed import SourceItem, parse_nasa_feed


def test_sourced_story_rejects_decade_claims_even_if_source_mentions_other_icebergs() -> None:
    story = {"scenes": [{"narration": "Nó đã đi qua hàng chục năm để đến đảo."}]}
    assert _has_unverified_long_time_claim(story)
    assert not _has_unverified_long_time_claim(
        {"scenes": [{"narration": "Nó đã đi hơn ba năm để đến đảo."}]}
    )


def test_sourced_story_rejects_season_inferred_from_antarctic_date() -> None:
    story = {"scenes": [{"narration": "Nó rời tảng băng mẹ vào mùa đông năm 2023."}]}
    assert _has_unsupported_season(story, "The iceberg broke from the shelf in January 2023.")
    assert not _has_unsupported_season(story, "The iceberg broke away in winter 2023.")


def test_sourced_story_rejects_arctic_and_reversed_route() -> None:
    source = (
        "Iceberg A-81 broke from an Antarctic ice shelf and headed north "
        "through the Weddell Sea toward South Georgia."
    )
    wrong = {
        "title": "Tảng băng đi về phía nam",
        "scenes": [{"narration": "Nó bắt đầu từ vùng Bắc Cực."}],
    }
    assert _has_unsupported_geography(wrong, source)
    assert _has_unsupported_geography(
        {"title": wrong["title"], "scenes": [{"narration": "Nó trôi trên biển."}]},
        source,
    )
    correct = {
        "title": "Tảng băng A-81 đi về phía bắc",
        "scenes": [{"narration": "Nó rời Nam Cực và trôi về phía bắc."}],
    }
    assert not _has_unsupported_geography(correct, source)
    hints = _source_factual_hints(
        {"title": "A-81 Reaches South Georgia", "summary": source}
    )
    assert any("Nam Cực" in hint for hint in hints)
    assert any("phía BẮC" in hint for hint in hints)


def test_nasa_feed_keeps_only_fresh_safe_earth_articles() -> None:
    now = datetime.now(UTC)
    recent = format_datetime(now - timedelta(hours=1))
    old = format_datetime(now - timedelta(days=14))
    def entry(title: str, path: str, date: str, description: str) -> str:
        return (
            f"<item><title>{title}</title>"
            f"<link>https://science.nasa.gov/{path}</link>"
            f"<pubDate>{date}</pubDate>"
            f"<description>{description}</description></item>"
        )

    leaves = entry(
        "Red Leaves from Space",
        "earth/earth-observatory/red-leaves/?tracking=1",
        recent,
        "&lt;p&gt;Satellites observe autumn leaves changing color across forests.&lt;/p&gt;",
    )
    wildfire = entry(
        "Wildfire destroys forest",
        "earth/earth-observatory/wildfire/",
        recent,
        "Dangerous fires spread through a forest.",
    )
    stale = entry(
        "Old leaves",
        "earth/earth-observatory/old-leaves/",
        old,
        "Satellites observed autumn leaves changing color across forests.",
    )
    spacecraft = entry(
        "Spacecraft",
        "photojournal/spacecraft/",
        recent,
        "Scientists inspect a large spacecraft in a clean room.",
    )
    xml = f"""<?xml version="1.0"?>
<rss version="2.0" xmlns:apod="https://science.nasa.gov/apod/"xmlns:media="http://search.yahoo.com/mrss/">
<channel>
{leaves}{wildfire}{stale}{spacecraft}
</channel></rss>"""
    items = parse_nasa_feed(xml.encode(), now)
    assert len(items) == 1
    assert items[0].title == "Red Leaves from Space"
    assert items[0].url == "https://science.nasa.gov/earth/earth-observatory/red-leaves/"


def test_nasa_feed_uses_article_facts_when_available() -> None:
    published = format_datetime(datetime.now(UTC) - timedelta(hours=1))
    xml = f"""<rss xmlns:content="http://purl.org/rss/1.0/modules/content/">
      <channel><item>
        <title>An Iceberg Near an Island</title>
        <link>https://science.nasa.gov/earth/earth-observatory/iceberg-island/</link>
        <pubDate>{published}</pubDate>
        <description><![CDATA[<p>A large iceberg approaches an island.</p>]]></description>
        <content:encoded><![CDATA[
          <img src="https://assets.science.nasa.gov/earth/iceberg.jpg?w=800&amp;h=500" />
          <p>A large iceberg called A-81 drifted north from Antarctica toward an island.</p>
          <p>Scientists used satellite images to follow the iceberg across the ocean.</p>
        ]]></content:encoded>
      </item></channel></rss>"""
    items = parse_nasa_feed(xml.encode())
    assert len(items) == 1
    assert "A-81 drifted north" in items[0].summary
    assert "Scientists used satellite images" in items[0].summary
    assert items[0].image_url == "https://assets.science.nasa.gov/earth/iceberg.jpg?w=800&h=500"


def test_nasa_photo_fills_both_video_aspects() -> None:
    original = io.BytesIO()
    Image.new("RGB", (1200, 800), (90, 140, 190)).save(original, format="JPEG")
    for width, height in [(360, 640), (640, 360)]:
        card = nasa_source_card(original.getvalue(), width, height)
        with Image.open(io.BytesIO(card)) as image:
            assert image.size == (width, height)
            assert image.getpixel((0, 0)) != (0, 0, 0)


@pytest.mark.asyncio
async def test_autopilot_reserves_source_and_queues_episode(
    client: AsyncClient, owner: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    project = await client.post(
        "/api/v1/projects", headers=owner, json={"title": "Autopilot Earth"}
    )
    assert project.status_code == 201
    project_id = project.json()["id"]
    item = SourceItem(
        title="Hunting Red Leaves with Satellites",
        summary="A NASA satellite observes autumn leaves changing color across forests.",
        url="https://science.nasa.gov/earth/earth-observatory/hunting-red-leaves/",
        published_at=datetime.now(UTC) - timedelta(hours=1),
    )

    async def mock_feed() -> list[SourceItem]:
        return [item]

    sent: list[str] = []
    monkeypatch.setattr(automation_router, "fetch_nasa_earth_items", mock_feed)
    monkeypatch.setattr(
        automation_router.celery_app,
        "send_task",
        lambda name, **kwargs: sent.append(name),
    )
    preview = await client.get(
        f"/api/v1/projects/{project_id}/autopilot/preview", headers=owner
    )
    assert preview.status_code == 200
    assert preview.json()[0]["already_used"] is False
    toggled = await client.patch(
        f"/api/v1/projects/{project_id}/autopilot",
        headers=owner,
        json={"enabled": True},
    )
    assert toggled.json()["enabled"] is True
    first = await client.post(f"/api/v1/projects/{project_id}/autopilot/run", headers=owner)
    second = await client.post(f"/api/v1/projects/{project_id}/autopilot/run", headers=owner)
    assert first.status_code == second.status_code == 202
    assert first.json()["source_id"] == second.json()["source_id"]
    assert first.json()["created"] is True
    assert second.json()["created"] is False
    assert sent == ["studio.produce_source_story"]
    source_id = UUID(first.json()["source_id"])
    async with SessionFactory() as db:
        produced = await produce_source_story(db, source_id)
        assert produced.job_id is not None
        assert produced.episode_id is not None
        assert produced.status == "queued"
        assert produced.model_snapshot["story_backend"] == "fake"
    sources = await client.get(
        f"/api/v1/projects/{project_id}/autopilot/sources", headers=owner
    )
    assert sources.status_code == 200
    assert sources.json()[0]["source_url"] == item.url
    assert sources.json()[0]["job_status"] == "queued"
    assert (
        await client.get(f"/api/v1/projects/{project_id}", headers=owner)
    ).json()["autopilot_enabled"] is True


@pytest.mark.asyncio
async def test_autopilot_recovers_interrupted_generation(
    client: AsyncClient, owner: dict[str, str]
) -> None:
    response = await client.post(
        "/api/v1/projects", headers=owner, json={"title": "Recovery test"}
    )
    project_id = UUID(response.json()["id"])
    old = SourceItem(
        title="An Old Iceberg",
        summary="An iceberg drifts slowly through Antarctic seas.",
        url="https://science.nasa.gov/earth/earth-observatory/old-iceberg/",
        published_at=datetime.now(UTC) - timedelta(days=1),
    )
    fresh = SourceItem(
        title="New Autumn Leaves",
        summary="Satellites watch a forest change color in autumn.",
        url="https://science.nasa.gov/earth/earth-observatory/new-leaves/",
        published_at=datetime.now(UTC) - timedelta(hours=1),
    )
    async with SessionFactory() as db:
        project = await db.get_one(Project, project_id)
        stale = SourceStory(
            project_id=project_id,
            source_hash=old.source_hash,
            source_url=old.url,
            feed_url=old.feed_url,
            title=old.title,
            summary=old.summary,
            published_at=old.published_at,
            status="generating",
            model_snapshot={},
            updated_at=datetime.now(UTC) - timedelta(minutes=21),
        )
        db.add(stale)
        await db.commit()
        selected, created = await reserve_latest_source(db, project, [fresh, old])
        await db.refresh(stale)
        assert created is True
        assert selected.source_hash == fresh.source_hash
        assert stale.status == "failed"


@pytest.mark.asyncio
async def test_reconciler_marks_abandoned_story_generation_failed(
    client: AsyncClient, owner: dict[str, str]
) -> None:
    response = await client.post(
        "/api/v1/projects", headers=owner, json={"title": "Reconciler test"}
    )
    project_id = UUID(response.json()["id"])
    item = SourceItem(
        title="Iceberg on the Move",
        summary="An iceberg moved north through Antarctic seas.",
        url="https://science.nasa.gov/earth/earth-observatory/iceberg-move/",
        published_at=datetime.now(UTC) - timedelta(days=1),
    )
    async with SessionFactory() as db:
        stale = SourceStory(
            project_id=project_id,
            source_hash=item.source_hash,
            source_url=item.url,
            feed_url=item.feed_url,
            title=item.title,
            summary=item.summary,
            published_at=item.published_at,
            status="generating",
            model_snapshot={},
            updated_at=datetime.now(UTC) - timedelta(minutes=21),
        )
        db.add(stale)
        await db.commit()
        await db.refresh(stale)
        source_id = stale.id
    assert await _reconcile_expired_leases() == 1
    async with SessionFactory() as db:
        recovered = await db.get_one(SourceStory, source_id)
        assert recovered.status == "failed"
        assert recovered.error_message is not None
        assert "retry" in recovered.error_message.lower()
