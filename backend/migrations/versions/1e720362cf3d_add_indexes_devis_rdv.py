"""add indexes devis & rdv

Revision ID: 1e720362cf3d
Revises: e47c3ef055f0
Create Date: 2025-09-05 19:47:59.230477

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1e720362cf3d'
down_revision: Union[str, None] = 'e47c3ef055f0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
