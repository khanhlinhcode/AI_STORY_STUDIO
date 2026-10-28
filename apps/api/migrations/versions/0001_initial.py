"""Initial modular-monolith schema.

Revision ID: 0001
Revises: None
Create Date: 2026-10-27
"""

from alembic import op

import studio_api.models  # noqa: F401
from studio_api.core.db import Base

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind(), checkfirst=True)
