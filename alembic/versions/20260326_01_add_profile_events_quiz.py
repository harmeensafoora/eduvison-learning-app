"""add profile events quiz tables

Revision ID: 20260326_01
Revises: 
Create Date: 2026-03-26 00:00:00
"""
from alembic import op
import sqlalchemy as sa


revision = "20260326_01"
down_revision = None
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return name in inspector.get_table_names()


def upgrade() -> None:
    if not _has_table("user_profile"):
        op.create_table(
            "user_profile",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("user_id", sa.String(length=36), nullable=False),
            sa.Column("preferred_modality", sa.Text(), nullable=True),
            sa.Column("avg_session_length_minutes", sa.Float(), nullable=True, server_default="0"),
            sa.Column("total_concepts_mastered", sa.Integer(), nullable=True, server_default="0"),
            sa.Column("learning_velocity", sa.Float(), nullable=True, server_default="1.0"),
            sa.Column("last_active_at", sa.DateTime(), nullable=True),
            sa.Column("streak_days", sa.Integer(), nullable=True, server_default="0"),
            sa.Column("cognitive_style", sa.Text(), nullable=True),
            sa.Column("difficulty_preference", sa.Text(), nullable=True, server_default="auto"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id"),
        )

    if not _has_table("learning_events"):
        op.create_table(
            "learning_events",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("user_id", sa.String(length=36), nullable=False),
            sa.Column("chunk_id", sa.String(length=36), nullable=True),
            sa.Column("session_id", sa.String(length=36), nullable=True),
            sa.Column("event_type", sa.Text(), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["chunk_id"], ["concepts.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _has_table("quiz_attempts"):
        op.create_table(
            "quiz_attempts",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("user_id", sa.String(length=36), nullable=False),
            sa.Column("chunk_id", sa.String(length=36), nullable=True),
            sa.Column("session_id", sa.String(length=36), nullable=True),
            sa.Column("difficulty", sa.Text(), nullable=True),
            sa.Column("score", sa.Integer(), nullable=True),
            sa.Column("time_taken_ms", sa.Integer(), nullable=True),
            sa.Column("misconceptions", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["chunk_id"], ["concepts.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )


def downgrade() -> None:
    if _has_table("quiz_attempts"):
        op.drop_table("quiz_attempts")
    if _has_table("learning_events"):
        op.drop_table("learning_events")
    if _has_table("user_profile"):
        op.drop_table("user_profile")
