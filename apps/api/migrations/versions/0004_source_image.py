"""Store the NASA article's primary image for sourced preview videos.

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("source_stories")}
    if "image_url" not in columns:
        op.add_column("source_stories", sa.Column("image_url", sa.String(2000), nullable=True))


def downgrade() -> None:
    op.drop_column("source_stories", "image_url")
