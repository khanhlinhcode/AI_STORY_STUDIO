from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from studio_api.core.errors import ErrorCode, StudioError
from studio_api.modules.characters.models import Character, CharacterRevision
from studio_api.modules.models_hub.models import ModelDeployment

REQUIRED_BIBLE_FIELDS = {"species", "palette", "outfit", "eyes", "style", "rights"}


def validate_bible(data: dict[str, Any]) -> None:
    missing = sorted(REQUIRED_BIBLE_FIELDS - data.keys())
    if missing:
        raise StudioError(
            ErrorCode.POLICY_REJECTED,
            "Character Bible is incomplete",
            details={"missing": missing},
        )


async def create_character(
    db: AsyncSession, project_id: UUID, name: str, bible_data: dict[str, Any]
) -> Character:
    validate_bible(bible_data)
    character = Character(project_id=project_id, name=name, character_bible=bible_data)
    db.add(character)
    await db.flush()
    db.add(
        CharacterRevision(
            character_id=character.id,
            version=1,
            character_bible=bible_data,
            approved_look={},
        )
    )
    await db.commit()
    await db.refresh(character)
    return character


def get_prompt_constraints(character: Character) -> str:
    bible = character.character_bible
    return (
        f"consistent character: {bible.get('species')} named {character.name}, "
        f"{bible.get('palette')} palette, {bible.get('outfit')}, {bible.get('eyes')} eyes, "
        f"{bible.get('style')} style; identity and outfit must not change"
    )


async def update_character(
    db: AsyncSession, character: Character, data: dict[str, Any]
) -> Character:
    merged = {**character.character_bible, **data}
    validate_bible(merged)
    character.version += 1
    character.character_bible = merged
    db.add(
        CharacterRevision(
            character_id=character.id,
            version=character.version,
            character_bible=merged,
            approved_look=character.approved_look,
        )
    )
    await db.commit()
    await db.refresh(character)
    return character


async def link_lora_model(db: AsyncSession, character: Character, deployment_id: UUID) -> Character:
    deployment = await db.scalar(
        select(ModelDeployment).where(
            ModelDeployment.id == deployment_id,
            ModelDeployment.is_active.is_(True),
        )
    )
    if deployment is None:
        raise StudioError(
            ErrorCode.POLICY_REJECTED, "Only an active approved deployment can be linked"
        )
    character.lora_model_id = deployment.id
    await db.commit()
    await db.refresh(character)
    return character
