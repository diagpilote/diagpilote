"""add indexes devis & rdv (v2)

Revision ID: bd1c6bfa4a16
Revises: 1e720362cf3d
Create Date: 2025-09-05 19:50:28.220936

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bd1c6bfa4a16'
down_revision: Union[str, None] = '1e720362cf3d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from alembic import op
    op.create_index("ix_devis_created_at","devis",["created_at"])
    op.create_index("ix_devis_montant","devis",["montant"])
    op.create_index("ix_rdv_status","rdv",["status"])
    op.create_index("ix_rdv_date_start","rdv",["date_start"])
    op.create_index("ix_rdv_created_at","rdv",["created_at"])
def downgrade() -> None:
    from alembic import op
    op.drop_index("ix_rdv_created_at", table_name="rdv")
    op.drop_index("ix_rdv_date_start", table_name="rdv")
    op.drop_index("ix_rdv_status", table_name="rdv")
    op.drop_index("ix_devis_montant", table_name="devis")
    op.drop_index("ix_devis_created_at", table_name="devis")
