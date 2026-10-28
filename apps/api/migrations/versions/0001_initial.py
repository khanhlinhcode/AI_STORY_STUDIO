"""Initial schema at revision 0001 (before timezone/source migrations).

Revision ID: 0001
Revises: None
Create Date: 2026-10-27
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_models",
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("model_family", sa.String(120), nullable=False),
        sa.Column("variant", sa.String(120), nullable=False),
        sa.Column("checkpoint_hash", sa.String(128), nullable=False),
        sa.Column("license_id", sa.String(120), nullable=False),
        sa.Column("approved", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_unique_constraint(
        "uq_ai_models_provider", "ai_models", ["provider", "checkpoint_hash"]
    )

    op.create_table(
        "audit_events",
        sa.Column("workspace_id", sa.Uuid(), nullable=True),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(120), nullable=False),
        sa.Column("subject_type", sa.String(64), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=False),
        sa.Column("before_hash", sa.String(64), nullable=True),
        sa.Column("after_hash", sa.String(64), nullable=True),
        sa.Column("trace_id", sa.String(64), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_events_subject_id", "audit_events", ["subject_id"], unique=False)
    op.create_index("ix_audit_events_workspace_id", "audit_events", ["workspace_id"], unique=False)

    op.create_table(
        "outbox_events",
        sa.Column("event_type", sa.String(120), nullable=False),
        sa.Column("aggregate_id", sa.Uuid(), nullable=False),
        sa.Column("schema_version", sa.String(16), nullable=False),
        sa.Column("message_id", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_unique_constraint("uq_outbox_events_message_id", "outbox_events", ["message_id"])
    op.create_index(
        "ix_outbox_events_aggregate_id", "outbox_events", ["aggregate_id"], unique=False
    )
    op.create_index(
        "ix_outbox_status_created", "outbox_events", ["status", "created_at"], unique=False
    )

    op.create_table(
        "users",
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(120), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "model_deployments",
        sa.Column(
            "model_id",
            sa.Uuid(),
            sa.ForeignKey(
                "ai_models.id", name="fk_model_deployments_model_id_ai_models", ondelete="CASCADE"
            ),
            nullable=False,
        ),
        sa.Column("alias", sa.String(32), nullable=False),
        sa.Column("adapter_id", sa.String(120), nullable=False),
        sa.Column(
            "approved_by",
            sa.Uuid(),
            sa.ForeignKey(
                "users.id", name="fk_model_deployments_approved_by_users", ondelete="SET NULL"
            ),
            nullable=True,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_unique_constraint(
        "uq_model_deployments_model_id", "model_deployments", ["model_id", "alias"]
    )
    op.create_index(
        "ix_model_deployments_model_id", "model_deployments", ["model_id"], unique=False
    )

    op.create_table(
        "workspaces",
        sa.Column("slug", sa.String(80), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column(
            "owner_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", name="fk_workspaces_owner_id_users", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("settings", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_workspaces_owner_id", "workspaces", ["owner_id"], unique=False)
    op.create_index("ix_workspaces_slug", "workspaces", ["slug"], unique=True)

    op.create_table(
        "assets",
        sa.Column(
            "workspace_id",
            sa.Uuid(),
            sa.ForeignKey(
                "workspaces.id", name="fk_assets_workspace_id_workspaces", ondelete="CASCADE"
            ),
            nullable=False,
        ),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("mime_type", sa.String(120), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("storage_key", sa.String(1024), nullable=False),
        sa.Column("rights_declaration", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_unique_constraint("uq_assets_storage_key", "assets", ["storage_key"])
    op.create_unique_constraint("uq_assets_workspace_id", "assets", ["workspace_id", "sha256"])
    op.create_index("ix_assets_sha256", "assets", ["sha256"], unique=False)
    op.create_index("ix_assets_workspace_id", "assets", ["workspace_id"], unique=False)

    op.create_table(
        "memberships",
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", name="fk_memberships_user_id_users", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "workspace_id",
            sa.Uuid(),
            sa.ForeignKey(
                "workspaces.id", name="fk_memberships_workspace_id_workspaces", ondelete="CASCADE"
            ),
            nullable=False,
        ),
        sa.Column("role", sa.String(24), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_unique_constraint(
        "uq_memberships_user_id", "memberships", ["user_id", "workspace_id"]
    )
    op.create_index("ix_memberships_user_id", "memberships", ["user_id"], unique=False)
    op.create_index("ix_memberships_workspace_id", "memberships", ["workspace_id"], unique=False)

    op.create_table(
        "projects",
        sa.Column(
            "workspace_id",
            sa.Uuid(),
            sa.ForeignKey(
                "workspaces.id", name="fk_projects_workspace_id_workspaces", ondelete="CASCADE"
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("locale", sa.String(16), nullable=False),
        sa.Column("audience", sa.String(80), nullable=False),
        sa.Column("style_profile", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_projects_workspace_id", "projects", ["workspace_id"], unique=False)
    op.create_index(
        "ix_projects_workspace_status", "projects", ["workspace_id", "status"], unique=False
    )

    op.create_table(
        "asset_dependencies",
        sa.Column(
            "output_asset_id",
            sa.Uuid(),
            sa.ForeignKey(
                "assets.id", name="fk_asset_dependencies_output_asset_id_assets", ondelete="CASCADE"
            ),
            nullable=False,
        ),
        sa.Column(
            "input_asset_id",
            sa.Uuid(),
            sa.ForeignKey(
                "assets.id", name="fk_asset_dependencies_input_asset_id_assets", ondelete="RESTRICT"
            ),
            nullable=False,
        ),
        sa.Column("dependency_type", sa.String(64), nullable=False),
        sa.Column("transform_run_id", sa.String(200), nullable=True),
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_unique_constraint(
        "uq_asset_dependencies_output_asset_id",
        "asset_dependencies",
        ["output_asset_id", "input_asset_id", "dependency_type"],
    )
    op.create_index(
        "ix_asset_dependencies_input_asset_id",
        "asset_dependencies",
        ["input_asset_id"],
        unique=False,
    )
    op.create_index(
        "ix_asset_dependencies_output_asset_id",
        "asset_dependencies",
        ["output_asset_id"],
        unique=False,
    )

    op.create_table(
        "automation_batches",
        sa.Column(
            "workspace_id",
            sa.Uuid(),
            sa.ForeignKey(
                "workspaces.id",
                name="fk_automation_batches_workspace_id_workspaces",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey(
                "projects.id", name="fk_automation_batches_project_id_projects", ondelete="CASCADE"
            ),
            nullable=False,
        ),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("topics", sa.JSON(), nullable=False),
        sa.Column("job_ids", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_automation_batches_project_id", "automation_batches", ["project_id"], unique=False
    )
    op.create_index(
        "ix_automation_batches_workspace_id", "automation_batches", ["workspace_id"], unique=False
    )

    op.create_table(
        "characters",
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey(
                "projects.id", name="fk_characters_project_id_projects", ondelete="CASCADE"
            ),
            nullable=False,
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("character_bible", sa.JSON(), nullable=False),
        sa.Column("voice_profile_id", sa.String(200), nullable=True),
        sa.Column("approved_look", sa.JSON(), nullable=False),
        sa.Column(
            "lora_model_id",
            sa.Uuid(),
            sa.ForeignKey(
                "model_deployments.id",
                name="fk_characters_lora_model_id_model_deployments",
                ondelete="SET NULL",
            ),
            nullable=True,
        ),
        sa.Column("consent_verified", sa.Boolean(), nullable=False),
        sa.Column("is_approved", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_unique_constraint("uq_characters_project_id", "characters", ["project_id", "name"])
    op.create_index("ix_characters_project_id", "characters", ["project_id"], unique=False)

    op.create_table(
        "episodes",
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey(
                "projects.id", name="fk_episodes_project_id_projects", ondelete="CASCADE"
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("topic", sa.String(500), nullable=False),
        sa.Column("duration_goal_ms", sa.Integer(), nullable=False),
        sa.Column("aspect_ratio", sa.String(8), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("execution_mode", sa.String(16), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_episodes_project_id", "episodes", ["project_id"], unique=False)
    op.create_index(
        "ix_episodes_project_status", "episodes", ["project_id", "status"], unique=False
    )

    op.create_table(
        "character_revisions",
        sa.Column(
            "character_id",
            sa.Uuid(),
            sa.ForeignKey(
                "characters.id",
                name="fk_character_revisions_character_id_characters",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("character_bible", sa.JSON(), nullable=False),
        sa.Column("approved_look", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_unique_constraint(
        "uq_character_revisions_character_id", "character_revisions", ["character_id", "version"]
    )
    op.create_index(
        "ix_character_revisions_character_id", "character_revisions", ["character_id"], unique=False
    )

    op.create_table(
        "exports",
        sa.Column(
            "episode_id",
            sa.Uuid(),
            sa.ForeignKey("episodes.id", name="fk_exports_episode_id_episodes", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("episode_revision", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("manifest", sa.JSON(), nullable=False),
        sa.Column("validation", sa.JSON(), nullable=False),
        sa.Column(
            "approved_by",
            sa.Uuid(),
            sa.ForeignKey("users.id", name="fk_exports_approved_by_users", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_exports_episode_id", "exports", ["episode_id"], unique=False)

    op.create_table(
        "production_jobs",
        sa.Column(
            "workspace_id",
            sa.Uuid(),
            sa.ForeignKey(
                "workspaces.id",
                name="fk_production_jobs_workspace_id_workspaces",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "episode_id",
            sa.Uuid(),
            sa.ForeignKey(
                "episodes.id", name="fk_production_jobs_episode_id_episodes", ondelete="CASCADE"
            ),
            nullable=False,
        ),
        sa.Column(
            "requested_by",
            sa.Uuid(),
            sa.ForeignKey(
                "users.id", name="fk_production_jobs_requested_by_users", ondelete="SET NULL"
            ),
            nullable=True,
        ),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("execution_mode", sa.String(16), nullable=False),
        sa.Column("job_kind", sa.String(24), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("lease_expires_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("snapshot_revision", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_unique_constraint(
        "uq_production_jobs_workspace_id", "production_jobs", ["workspace_id", "idempotency_key"]
    )
    op.create_index(
        "ix_jobs_status_priority_created",
        "production_jobs",
        ["status", "priority", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_production_jobs_episode_id", "production_jobs", ["episode_id"], unique=False
    )
    op.create_index(
        "ix_production_jobs_workspace_id", "production_jobs", ["workspace_id"], unique=False
    )

    op.create_table(
        "review_tasks",
        sa.Column(
            "episode_id",
            sa.Uuid(),
            sa.ForeignKey(
                "episodes.id", name="fk_review_tasks_episode_id_episodes", ondelete="CASCADE"
            ),
            nullable=False,
        ),
        sa.Column(
            "reviewer_id",
            sa.Uuid(),
            sa.ForeignKey(
                "users.id", name="fk_review_tasks_reviewer_id_users", ondelete="RESTRICT"
            ),
            nullable=False,
        ),
        sa.Column("episode_revision", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_review_tasks_episode_id", "review_tasks", ["episode_id"], unique=False)

    op.create_table(
        "scenes",
        sa.Column(
            "episode_id",
            sa.Uuid(),
            sa.ForeignKey("episodes.id", name="fk_scenes_episode_id_episodes", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("synopsis", sa.Text(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("current_revision_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_scenes_episode_id", "scenes", ["episode_id"], unique=False)
    op.create_index(
        "ix_scenes_episode_order", "scenes", ["episode_id", "order_index"], unique=False
    )

    op.create_table(
        "script_revisions",
        sa.Column(
            "episode_id",
            sa.Uuid(),
            sa.ForeignKey(
                "episodes.id", name="fk_script_revisions_episode_id_episodes", ondelete="CASCADE"
            ),
            nullable=False,
        ),
        sa.Column("structured_json", sa.JSON(), nullable=False),
        sa.Column("schema_version", sa.String(16), nullable=False),
        sa.Column(
            "parent_id",
            sa.Uuid(),
            sa.ForeignKey(
                "script_revisions.id",
                name="fk_script_revisions_parent_id_script_revisions",
                ondelete="SET NULL",
            ),
            nullable=True,
        ),
        sa.Column("is_approved", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_script_revisions_episode_id", "script_revisions", ["episode_id"], unique=False
    )

    op.create_table(
        "eval_runs",
        sa.Column(
            "job_id",
            sa.Uuid(),
            sa.ForeignKey(
                "production_jobs.id",
                name="fk_eval_runs_job_id_production_jobs",
                ondelete="SET NULL",
            ),
            nullable=True,
        ),
        sa.Column("model_ref", sa.String(255), nullable=False),
        sa.Column("dataset_ref", sa.String(255), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("report", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_eval_runs_job_id", "eval_runs", ["job_id"], unique=False)

    op.create_table(
        "review_decisions",
        sa.Column(
            "task_id",
            sa.Uuid(),
            sa.ForeignKey(
                "review_tasks.id",
                name="fk_review_decisions_task_id_review_tasks",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "reviewer_id",
            sa.Uuid(),
            sa.ForeignKey(
                "users.id", name="fk_review_decisions_reviewer_id_users", ondelete="RESTRICT"
            ),
            nullable=False,
        ),
        sa.Column("verdict", sa.String(16), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("rubric_scores", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_unique_constraint("uq_review_decisions_task_id", "review_decisions", ["task_id"])

    op.create_table(
        "scene_revisions",
        sa.Column(
            "scene_id",
            sa.Uuid(),
            sa.ForeignKey(
                "scenes.id", name="fk_scene_revisions_scene_id_scenes", ondelete="CASCADE"
            ),
            nullable=False,
        ),
        sa.Column(
            "script_revision_id",
            sa.Uuid(),
            sa.ForeignKey(
                "script_revisions.id",
                name="fk_scene_revisions_script_revision_id_script_revisions",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("negative_prompt", sa.Text(), nullable=False),
        sa.Column("camera", sa.JSON(), nullable=False),
        sa.Column("image_desc", sa.Text(), nullable=False),
        sa.Column("narration", sa.Text(), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=False),
        sa.Column("approval_state", sa.String(24), nullable=False),
        sa.Column(
            "parent_id",
            sa.Uuid(),
            sa.ForeignKey(
                "scene_revisions.id",
                name="fk_scene_revisions_parent_id_scene_revisions",
                ondelete="SET NULL",
            ),
            nullable=True,
        ),
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_scene_revisions_scene_id", "scene_revisions", ["scene_id"], unique=False)
    op.create_index(
        "ix_scene_revisions_script_revision_id",
        "scene_revisions",
        ["script_revision_id"],
        unique=False,
    )

    op.create_table(
        "job_steps",
        sa.Column(
            "job_id",
            sa.Uuid(),
            sa.ForeignKey(
                "production_jobs.id", name="fk_job_steps_job_id_production_jobs", ondelete="CASCADE"
            ),
            nullable=False,
        ),
        sa.Column(
            "scene_revision_id",
            sa.Uuid(),
            sa.ForeignKey(
                "scene_revisions.id",
                name="fk_job_steps_scene_revision_id_scene_revisions",
                ondelete="SET NULL",
            ),
            nullable=True,
        ),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("lease_expires_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column(
            "output_manifest_id",
            sa.Uuid(),
            sa.ForeignKey(
                "assets.id", name="fk_job_steps_output_manifest_id_assets", ondelete="SET NULL"
            ),
            nullable=True,
        ),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_unique_constraint(
        "uq_job_steps_job_id", "job_steps", ["job_id", "scene_revision_id", "kind"]
    )
    op.create_index("ix_job_steps_job_id", "job_steps", ["job_id"], unique=False)
    op.create_index("ix_job_steps_job_status", "job_steps", ["job_id", "status"], unique=False)


def downgrade() -> None:
    op.drop_table("job_steps")
    op.drop_table("scene_revisions")
    op.drop_table("review_decisions")
    op.drop_table("eval_runs")
    op.drop_table("script_revisions")
    op.drop_table("scenes")
    op.drop_table("review_tasks")
    op.drop_table("production_jobs")
    op.drop_table("exports")
    op.drop_table("character_revisions")
    op.drop_table("episodes")
    op.drop_table("characters")
    op.drop_table("automation_batches")
    op.drop_table("asset_dependencies")
    op.drop_table("projects")
    op.drop_table("memberships")
    op.drop_table("assets")
    op.drop_table("workspaces")
    op.drop_table("model_deployments")
    op.drop_table("users")
    op.drop_table("outbox_events")
    op.drop_table("audit_events")
    op.drop_table("ai_models")
