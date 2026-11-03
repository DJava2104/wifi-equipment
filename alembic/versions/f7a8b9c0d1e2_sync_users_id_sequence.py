"""sync users id sequence after seeding user_0

Revision ID: f7a8b9c0d1e2
Revises: b2c3d4e5f6a7
Create Date: 2026-11-04 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'f7a8b9c0d1e2'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # user_0 вставлен с явным id_user = 1, счётчик SERIAL от этого не сдвигается —
    # без синхронизации первая регистрация получила бы id 1 и упала с ошибкой.
    op.execute(
        "SELECT setval(pg_get_serial_sequence('users', 'id_user'), "
        "COALESCE((SELECT MAX(id_user) FROM users), 1))"
    )


def downgrade() -> None:
    """Downgrade schema."""
    pass
