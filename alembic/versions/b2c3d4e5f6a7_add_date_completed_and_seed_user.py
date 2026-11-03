"""add date_completed column and seed current user

Revision ID: b2c3d4e5f6a7
Revises: e1f2a3b4c5d6
Create Date: 2026-10-20 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'e1f2a3b4c5d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('routers', sa.Column('date_completed', sa.TIMESTAMP(), nullable=True))

    op.execute(
        "INSERT INTO users (id_user, username, password) "
        "VALUES (1, 'user_0', 'password') ON CONFLICT DO NOTHING"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DELETE FROM users WHERE id_user = 1 AND username = 'user_0'")
    op.drop_column('routers', 'date_completed')
