"""Store workflow leases as timezone aware UTC timestamps.

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("production_jobs", "job_steps"):
        op.alter_column(
            table,
            "lease_expires_at",
            existing_type=sa.DateTime(timezone=False),
            type_=sa.DateTime(timezone=True),
            postgresql_using="lease_expires_at AT TIME ZONE 'UTC'",
        )


def downgrade() -> None:
    for table in ("production_jobs", "job_steps"):
        op.alter_column(
            table,
            "lease_expires_at",
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(timezone=False),
            postgresql_using="lease_expires_at AT TIME ZONE 'UTC'",
        )
