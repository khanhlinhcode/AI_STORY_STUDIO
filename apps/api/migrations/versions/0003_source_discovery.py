"""Track fresh source articles and project autopilot setting.

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    project_columns = {column["name"] for column in inspector.get_columns("projects")}
    if "autopilot_enabled" not in project_columns:
        op.add_column(
            "projects",
            sa.Column(
                "autopilot_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )
    if not inspector.has_table("source_stories"):
        op.create_table(
            "source_stories",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column(
                "project_id",
                sa.Uuid(),
                sa.ForeignKey("projects.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "episode_id",
                sa.Uuid(),
                sa.ForeignKey("episodes.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "job_id",
                sa.Uuid(),
                sa.ForeignKey("production_jobs.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("source_hash", sa.String(64), nullable=False),
            sa.Column("source_url", sa.String(1000), nullable=False),
            sa.Column("feed_url", sa.String(1000), nullable=False),
            sa.Column("title", sa.String(300), nullable=False),
            sa.Column("summary", sa.Text(), nullable=False),
            sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("status", sa.String(24), nullable=False),
            sa.Column("model_snapshot", sa.JSON(), nullable=False),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.UniqueConstraint(
                "project_id", "source_hash", name="uq_source_stories_project_source"
            ),
        )
        op.create_index("ix_source_stories_project_id", "source_stories", ["project_id"])


def downgrade() -> None:
    op.drop_table("source_stories")
    op.drop_column("projects", "autopilot_enabled")
