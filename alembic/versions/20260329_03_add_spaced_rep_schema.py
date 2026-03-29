"""Add spaced repetition state table for Leitner scheduler

Revision ID: 20260329_03
Revises: 20260328_02
Create Date: 2026-03-29 16:15:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260329_03'
down_revision = '20260328_02'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create spaced_rep_state table
    op.create_table(
        'spaced_rep_state',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('concept_id', sa.String(), nullable=False),
        sa.Column('box', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('streak_correct', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_review_at', sa.DateTime(), nullable=True),
        sa.Column('next_review_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['concept_id'], ['pdf_concepts.id'], name='fk_srs_concept', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_srs_user', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for query performance
    op.create_index('ix_spaced_rep_state_user_id', 'spaced_rep_state', ['user_id'])
    op.create_index('ix_spaced_rep_state_concept_id', 'spaced_rep_state', ['concept_id'])
    op.create_index('ix_spaced_rep_state_next_review_at', 'spaced_rep_state', ['next_review_at'])
    # Composite index for "user's reviews" queries
    op.create_index('ix_spaced_rep_state_user_next_review', 'spaced_rep_state', ['user_id', 'next_review_at'])


def downgrade() -> None:
    op.drop_index('ix_spaced_rep_state_user_next_review', table_name='spaced_rep_state')
    op.drop_index('ix_spaced_rep_state_next_review_at', table_name='spaced_rep_state')
    op.drop_index('ix_spaced_rep_state_concept_id', table_name='spaced_rep_state')
    op.drop_index('ix_spaced_rep_state_user_id', table_name='spaced_rep_state')
    op.drop_table('spaced_rep_state')
