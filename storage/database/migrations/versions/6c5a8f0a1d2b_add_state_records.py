"""add state records

Revision ID: 6c5a8f0a1d2b
Revises: 0a9099bb02a1
Create Date: 2026-07-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from packages.shared_schemas.enums import StateStatus


# revision identifiers, used by Alembic.
revision: str = "6c5a8f0a1d2b"
down_revision: Union[str, Sequence[str], None] = "0a9099bb02a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    status_enum = sa.Enum(StateStatus, name="statestatus")
    status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "state_records",
        sa.Column("asset_id", sa.String(), nullable=False),
        sa.Column("filename", sa.String(), nullable=True),
        sa.Column("content_type", sa.String(), nullable=True),
        sa.Column("final_path", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("status", status_enum, nullable=False),
        sa.Column("correlation_id", sa.String(), nullable=True),
        sa.Column("findings", sa.JSON(), nullable=False),
        sa.Column("errors", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"]),
        sa.PrimaryKeyConstraint("asset_id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("state_records")
    sa.Enum(StateStatus, name="statestatus").drop(op.get_bind(), checkfirst=True)
