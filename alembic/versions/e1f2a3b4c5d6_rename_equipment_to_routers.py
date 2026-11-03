"""rename equipment to routers

Revision ID: e1f2a3b4c5d6
Revises: c91aeb75b7e7
Create Date: 2026-10-21 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e1f2a3b4c5d6'
down_revision: Union[str, Sequence[str], None] = 'c91aeb75b7e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.rename_table('equipment', 'routers')
    op.alter_column('routers', 'id_equipment', new_column_name='id_routers')
    op.alter_column('likes', 'id_equipment', new_column_name='id_routers')


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column('likes', 'id_routers', new_column_name='id_equipment')
    op.alter_column('routers', 'id_routers', new_column_name='id_equipment')
    op.rename_table('routers', 'equipment')
