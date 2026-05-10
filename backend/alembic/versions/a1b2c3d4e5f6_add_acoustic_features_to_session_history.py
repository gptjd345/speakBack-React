"""add acoustic_features to session_history

Revision ID: a1b2c3d4e5f6
Revises: 0e308189c81b
Create Date: 2026-05-08

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'a1b2c3d4e5f6'
down_revision = '0e308189c81b'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('session_history', sa.Column('acoustic_features', postgresql.JSON(astext_type=sa.Text()), nullable=True))


def downgrade():
    op.drop_column('session_history', 'acoustic_features')
