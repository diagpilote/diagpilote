"""add devis table

Revision ID: e47c3ef055f0
Revises: c5ba884e7c63
Create Date: 2025-09-05 18:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e47c3ef055f0'
down_revision = 'c5ba884e7c63'
branch_labels = None
depends_on = None
def upgrade():
    op.create_table(
        'devis',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('ref', sa.String(length=32), nullable=False),
        sa.Column('client', sa.String(length=255), nullable=False),
        sa.Column('montant', sa.Numeric(10, 2), nullable=False),
        sa.Column('devise', sa.String(length=8), nullable=False, server_default='EUR'),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='draft'),
        sa.Column('dossier_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=False), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=False), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['dossier_id'], ['dossiers.id'], name='devis_dossier_id_fkey', ondelete='SET NULL')
    )
    op.create_index('ix_devis_ref', 'devis', ['ref'], unique=True)
    op.create_index('ix_devis_status', 'devis', ['status'])
def downgrade():
    op.drop_index('ix_devis_status', table_name='devis')
    op.drop_index('ix_devis_ref', table_name='devis')
    op.drop_table('devis')
