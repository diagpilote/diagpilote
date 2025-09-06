"""perf: composite + trigram indexes (v6)

Revision ID: 56d767b22f3c
Revises: bd3b39b82034
Create Date: 2025-09-06 09:59:41.526819
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "56d767b22f3c"
down_revision: Union[str, None] = "bd3b39b82034"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
def upgrade() -> None:
    # extension
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    # composites
    op.execute("CREATE INDEX IF NOT EXISTS ix_rdv_status_created_at ON public.rdv (status, created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_rdv_status_date_start ON public.rdv (status, date_start)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_devis_status_created_at ON public.devis (status, created_at)")
    # trigram
    op.execute("CREATE INDEX IF NOT EXISTS ix_devis_ref_trgm        ON public.devis USING gin (ref gin_trgm_ops)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_devis_client_trgm     ON public.devis USING gin (client gin_trgm_ops)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_rdv_client_nom_trgm   ON public.rdv   USING gin (client_nom gin_trgm_ops)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_rdv_adresse_trgm      ON public.rdv   USING gin (adresse gin_trgm_ops)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_rdv_ville_trgm        ON public.rdv   USING gin (ville gin_trgm_ops)")
def downgrade() -> None:
    # trigram
    op.execute("DROP INDEX IF EXISTS public.ix_rdv_ville_trgm")
    op.execute("DROP INDEX IF EXISTS public.ix_rdv_adresse_trgm")
    op.execute("DROP INDEX IF EXISTS public.ix_rdv_client_nom_trgm")
    op.execute("DROP INDEX IF EXISTS public.ix_devis_client_trgm")
    op.execute("DROP INDEX IF EXISTS public.ix_devis_ref_trgm")
    # composites
    op.execute("DROP INDEX IF EXISTS public.ix_devis_status_created_at")
    op.execute("DROP INDEX IF EXISTS public.ix_rdv_status_date_start")
    op.execute("DROP INDEX IF EXISTS public.ix_rdv_status_created_at")
