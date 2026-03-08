"""create session_history table

Revision ID: 6c0d816c4d81
Revises: 00f27337acf6
Create Date: 2026-03-08 05:14:46.225048

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from datetime import datetime


# revision identifiers, used by Alembic.
revision: str = '6c0d816c4d81'
down_revision: Union[str, Sequence[str], None] = '00f27337acf6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'session_history',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('target_text', sa.Text(), nullable=False),
        sa.Column('user_transcript', sa.Text(), nullable=True),
        sa.Column('score', sa.Float(), nullable=True),
        sa.Column('strengths', sa.JSON(), nullable=True),
        sa.Column('improvements', sa.JSON(), nullable=True),
        sa.Column('rhythm_feedback', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow),
    )

def downgrade() -> None:
    op.drop_table('session_history')
