"""Import all ORM models so Alembic and tests see one metadata graph."""

from studio_api.modules.assets.models import Asset, AssetDependency
from studio_api.modules.characters.models import Character, CharacterRevision
from studio_api.modules.evaluation.models import EvalRun, ReviewDecision, ReviewTask
from studio_api.modules.exports.models import Export
from studio_api.modules.identity.models import Membership, User, Workspace
from studio_api.modules.models_hub.models import AIModel, ModelDeployment
from studio_api.modules.narrative.models import ScriptRevision
from studio_api.modules.projects.models import Episode, Project
from studio_api.modules.scenes.models import Scene, SceneRevision
from studio_api.modules.workflows.models import (
    AuditEvent,
    AutomationBatch,
    JobStep,
    OutboxEvent,
    ProductionJob,
    SourceStory,
)

__all__ = [
    "AIModel",
    "Asset",
    "AssetDependency",
    "AuditEvent",
    "AutomationBatch",
    "Character",
    "CharacterRevision",
    "Episode",
    "EvalRun",
    "Export",
    "JobStep",
    "Membership",
    "ModelDeployment",
    "OutboxEvent",
    "ProductionJob",
    "Project",
    "ReviewDecision",
    "ReviewTask",
    "Scene",
    "SceneRevision",
    "ScriptRevision",
    "SourceStory",
    "User",
    "Workspace",
]
