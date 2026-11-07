"""Add admins access level and richer ticket statuses.

Revision ID: 002
Revises: 001
"""

from collections.abc import Sequence

from alembic import op

revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Postgres requires COMMIT between ADD VALUE for some versions; Alembic
    # runs in a transaction, so use IF NOT EXISTS and keep values additive.
    op.execute("ALTER TYPE access_level ADD VALUE IF NOT EXISTS 'admins'")
    op.execute("ALTER TYPE ticket_status ADD VALUE IF NOT EXISTS 'in_review'")
    op.execute("ALTER TYPE ticket_status ADD VALUE IF NOT EXISTS 'in_progress'")
    op.execute("ALTER TYPE ticket_status ADD VALUE IF NOT EXISTS 'answered'")


def downgrade() -> None:
    # Postgres cannot easily drop enum values; leave them in place.
    pass
