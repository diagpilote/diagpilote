"""perf: composite indexes rdv/devis (v5)

Revision ID: bd3b39b82034
Revises: 3f25149ef133
Create Date: 2025-09-06 09:50:22.502580

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bd3b39b82034'
down_revision: Union[str, None] = '3f25149ef133'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
