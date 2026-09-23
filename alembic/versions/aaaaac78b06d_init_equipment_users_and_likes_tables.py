"""init equipment, users and likes tables

Revision ID: aaaaac78b06d
Revises: 
Create Date: 2026-09-23 08:37:51.906230

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'aaaaac78b06d'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "equipment",
        sa.Column("id_equipment", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=100), nullable=False),
        sa.Column("standard", sa.String(length=50), nullable=True),
        sa.Column("max_speed", sa.Integer(), nullable=True),
        sa.Column("band", sa.String(length=20), nullable=True),
        sa.Column("antennas", sa.String(length=30), nullable=True),
        sa.Column("image_url", sa.String(length=255), nullable=True),
        sa.Column("video_url", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "date_created",
            sa.TIMESTAMP(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("creator", sa.String(length=50), nullable=False),
        sa.Column("date_formed", sa.TIMESTAMP(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'черновик'"),
        ),
    )

    op.create_table(
        "users",
        sa.Column("id_user", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=50), nullable=False, unique=True),
        sa.Column("password", sa.String(length=255), nullable=False),
    )

    op.create_table(
        "likes",
        sa.Column(
            "id_user",
            sa.Integer(),
            sa.ForeignKey("users.id_user"),
            nullable=False,
            primary_key=True,
        ),
        sa.Column(
            "id_equipment",
            sa.Integer(),
            sa.ForeignKey("equipment.id_equipment"),
            nullable=False,
            primary_key=True,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("likes")
    op.drop_table("users")
    op.drop_table("equipment")