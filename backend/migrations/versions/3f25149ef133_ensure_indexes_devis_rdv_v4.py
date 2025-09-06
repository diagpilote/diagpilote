"""ensure indexes devis & rdv (v4)

Revision ID: 3f25149ef133
Revises: 96dca63e4182
Create Date: 2025-09-06 09:25:04.484763

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3f25149ef133'
down_revision: Union[str, None] = '96dca63e4182'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
