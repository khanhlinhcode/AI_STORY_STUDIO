from __future__ import annotations

import difflib
import json
from typing import Any
from uuid import UUID, uuid4

from jsonschema import Draft202012Validator, RefResolver
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from studio_api.core.config import get_settings
from studio_api.core.contracts import schema_path
from studio_api.core.errors import ErrorCode, StudioError
from studio_api.modules.models.adapters.registry import get_adapter_registry
from studio_api.modules.narrative.models import ScriptRevision
from studio_api.modules.projects.models import Episode
from studio_api.modules.scenes.models import Scene, SceneRevision
from studio_api.modules.workflows.outbox import add_event


def _contract_validator() -> Draft202012Validator:
    directory = schema_path("episode_spec.v1.json").parent
    schema = json.loads((directory / "episode_spec.v1.json").read_text(encoding="utf-8"))
    scene = json.loads((directory / "scene_spec.v1.json").read_text(encoding="utf-8"))
    resolver = RefResolver.from_schema(
        schema, store={scene["$id"]: scene, "scene_spec.v1.json": scene}
    )
    return Draft202012Validator(schema, resolver=resolver)


def _ensure_child_safe(value: dict[str, Any]) -> None:
    body = json.dumps(value, ensure_ascii=False).casefold()
    matches = [word for word in get_settings().blocked_keywords_vi if word.casefold() in body]
    if matches:
        raise StudioError(
            ErrorCode.POLICY_REJECTED,
            "Nội dung không vượt qua bộ lọc an toàn trẻ em",
            details={"matched_count": len(matches)},
        )


async def generate_episode_script(
    db: AsyncSession,
    episode: Episode,
    topic: str,
    style: str,
    source_context: dict[str, str] | None = None,
) -> ScriptRevision:
    adapter = get_adapter_registry().get_story_adapter()
    generated = await adapter.generate_script(topic, style, source_context=source_context)
    _contract_validator().validate(generated)
    _ensure_child_safe(generated)

    previous = await db.scalar(
        select(ScriptRevision)
        .where(ScriptRevision.episode_id == episode.id)
        .order_by(ScriptRevision.created_at.desc())
        .limit(1)
    )
    clean = json.loads(json.dumps(generated))
    for scene in clean["scenes"]:
        scene["id"] = str(uuid4())
    revision = ScriptRevision(
        episode_id=episode.id,
        structured_json=clean,
        schema_version="1.0",
        parent_id=previous.id if previous else None,
        is_approved=episode.execution_mode == "automation",
    )
    db.add(revision)
    await db.flush()

    previous_scenes = list(
        await db.scalars(
            select(Scene).where(Scene.episode_id == episode.id, Scene.is_active.is_(True))
        )
    )
    for previous_scene in previous_scenes:
        previous_scene.is_active = False

    for order, item in enumerate(clean["scenes"]):
        scene = Scene(
            id=UUID(item["id"]),
            episode_id=episode.id,
            order_index=order,
            synopsis=item["narration"],
            duration_ms=item["duration_ms"],
        )
        db.add(scene)
        await db.flush()
        scene_revision = SceneRevision(
            scene_id=scene.id,
            script_revision_id=revision.id,
            prompt=item["image_desc"],
            image_desc=item["image_desc"],
            narration=item["narration"],
            seed=42 + order,
            camera={"movement": item["camera"]},
            approval_state="approved" if episode.execution_mode == "automation" else "pending",
        )
        db.add(scene_revision)
        await db.flush()
        scene.current_revision_id = scene_revision.id

    episode.title = clean["title"]
    episode.topic = topic
    episode.status = "script_ready"
    episode.revision += 1
    add_event(
        db,
        event_type="script.generated.v1",
        aggregate_id=episode.id,
        version=episode.revision,
        payload={"episode_id": episode.id, "script_revision_id": revision.id},
    )
    await db.commit()
    await db.refresh(revision)
    return revision


def get_script_diff(first: ScriptRevision, second: ScriptRevision) -> list[str]:
    a = json.dumps(first.structured_json, ensure_ascii=False, indent=2, sort_keys=True).splitlines()
    b = json.dumps(
        second.structured_json, ensure_ascii=False, indent=2, sort_keys=True
    ).splitlines()
    return list(difflib.unified_diff(a, b, fromfile=str(first.id), tofile=str(second.id)))


async def approve_script(db: AsyncSession, revision: ScriptRevision, episode: Episode) -> None:
    if episode.execution_mode != "studio":
        raise StudioError(ErrorCode.POLICY_REJECTED, "Automation scripts are approved by QC gates")
    latest = await db.scalar(
        select(ScriptRevision)
        .where(ScriptRevision.episode_id == episode.id)
        .order_by(ScriptRevision.created_at.desc())
        .limit(1)
    )
    if latest is None or latest.id != revision.id:
        raise StudioError(
            ErrorCode.ASSET_STALE, "Only the latest script can be approved", status_code=409
        )
    revision.is_approved = True
    await db.commit()
