"""add session_patterns table with pgvector

Revision ID: 0e308189c81b
Revises: 6c0d816c4d81
Create Date: 2026-03-24 14:45:07.800172

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0e308189c81b'
down_revision: Union[str, Sequence[str], None] = '6c0d816c4d81'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # pgvector extension 활성화
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "session_patterns",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("session_history.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("pattern_text", sa.Text(), nullable=False),
        sa.Column("weak_words", sa.JSON(), nullable=True),
        sa.Column("transcript_mismatches", sa.JSON(), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("embedding", sa.Text(), nullable=True),  # vector stored as text for migration
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_session_patterns_user_id", "session_patterns", ["user_id"])
    op.create_index("ix_session_patterns_session_id", "session_patterns", ["session_id"])

    # embedding 컬럼을 vector 타입으로 변경
    op.execute("ALTER TABLE session_patterns ALTER COLUMN embedding TYPE vector(1536) USING embedding::vector")


def downgrade() -> None:
    op.drop_table("session_patterns")
