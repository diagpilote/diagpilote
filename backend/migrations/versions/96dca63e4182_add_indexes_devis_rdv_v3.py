"""add indexes devis & rdv (v3)

Revision ID: 96dca63e4182
Revises: bd1c6bfa4a16
Create Date: 2025-09-06 09:18:11.308509

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '96dca63e4182'
down_revision: Union[str, None] = 'bd1c6bfa4a16'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
