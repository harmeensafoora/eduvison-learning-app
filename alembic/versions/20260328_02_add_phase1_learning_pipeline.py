"""add phase 1 learning pipeline tables

Revision ID: 20260328_02
Revises: 20260326_01
Create Date: 2026-03-28 12:45:00
"""
from alembic import op
import sqlalchemy as sa


revision = "20260328_02"
down_revision = "20260326_01"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return name in inspector.get_table_names()


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return False
    columns = {col["name"] for col in inspector.get_columns(table)}
    return column in columns


def upgrade() -> None:
    # PDFUpload table - stores uploaded PDFs and their processing status
    if not _has_table("pdf_uploads"):
        op.create_table(
            "pdf_uploads",
            sa.Column("id", sa.String(36), nullable=False),
            sa.Column("user_id", sa.String(36), nullable=False),
            sa.Column("filename", sa.String(255), nullable=False),
            sa.Column("file_path", sa.String(512), nullable=False),
            sa.Column("status", sa.String(50), nullable=False, server_default="uploading"),
            sa.Column("concepts_count", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("processing_started", sa.DateTime(), nullable=True),
            sa.Column("processing_completed", sa.DateTime(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("idx_pdf_uploads_user_id", "pdf_uploads", ["user_id"])
        op.create_index("idx_pdf_uploads_status", "pdf_uploads", ["status"])

    # Concept table - stores extracted concepts from PDFs
    if not _has_table("concepts"):
        op.create_table(
            "concepts",
            sa.Column("id", sa.String(36), nullable=False),
            sa.Column("pdf_id", sa.String(36), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("definition", sa.Text(), nullable=True),
            sa.Column("page_reference", sa.String(100), nullable=True),
            sa.Column("related_concepts", sa.JSON(), nullable=True),
            sa.Column("embedding", sa.LargeBinary(), nullable=True),  # Vector (1536)
            sa.Column("quality_score", sa.Float(), nullable=True),  # 1-5 scale
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["pdf_id"], ["pdf_uploads.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("idx_concepts_pdf_id", "concepts", ["pdf_id"])

    # Quiz table - stores quiz instances for concepts
    if not _has_table("quizzes"):
        op.create_table(
            "quizzes",
            sa.Column("id", sa.String(36), nullable=False),
            sa.Column("concept_id", sa.String(36), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["concept_id"], ["concepts.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("idx_quizzes_concept_id", "quizzes", ["concept_id"])

    # QuizQuestion table - stores individual questions in a quiz
    if not _has_table("quiz_questions"):
        op.create_table(
            "quiz_questions",
            sa.Column("id", sa.String(36), nullable=False),
            sa.Column("quiz_id", sa.String(36), nullable=False),
            sa.Column("question_text", sa.Text(), nullable=False),
            sa.Column("correct_answer", sa.String(255), nullable=False),
            sa.Column("distractors", sa.JSON(), nullable=False),  # ["option_2", "option_3", "option_4"]
            sa.Column("explanation", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["quiz_id"], ["quizzes.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("idx_quiz_questions_quiz_id", "quiz_questions", ["quiz_id"])

    # QuizResponse table - stores user responses to quizzes
    if not _has_table("quiz_responses"):
        op.create_table(
            "quiz_responses",
            sa.Column("id", sa.String(36), nullable=False),
            sa.Column("user_id", sa.String(36), nullable=False),
            sa.Column("quiz_id", sa.String(36), nullable=False),
            sa.Column("concept_id", sa.String(36), nullable=False),
            sa.Column("answered", sa.JSON(), nullable=False),  # { question_id: user_answer }
            sa.Column("correct_count", sa.Integer(), nullable=False),
            sa.Column("total_questions", sa.Integer(), nullable=False),
            sa.Column("score_percent", sa.Float(), nullable=False),
            sa.Column("submitted_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["quiz_id"], ["quizzes.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["concept_id"], ["concepts.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("idx_quiz_responses_user_id", "quiz_responses", ["user_id"])
        op.create_index("idx_quiz_responses_concept_id", "quiz_responses", ["concept_id"])
        op.create_index("idx_quiz_responses_submitted_at", "quiz_responses", ["submitted_at"])

    # Feedback table - stores feedback for quiz answers
    if not _has_table("feedback"):
        op.create_table(
            "feedback",
            sa.Column("id", sa.String(36), nullable=False),
            sa.Column("quiz_response_id", sa.String(36), nullable=False),
            sa.Column("question_id", sa.String(36), nullable=False),
            sa.Column("is_correct", sa.Boolean(), nullable=False),
            sa.Column("feedback_text", sa.Text(), nullable=False),
            sa.Column("source_citation", sa.String(255), nullable=True),  # "page 12, section 'Light Reactions'"
            sa.Column("generated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["quiz_response_id"], ["quiz_responses.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["question_id"], ["quiz_questions.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("idx_feedback_quiz_response_id", "feedback", ["quiz_response_id"])

    # RefreshToken table - stores refresh token information for session management
    if not _has_table("refresh_tokens"):
        op.create_table(
            "refresh_tokens",
            sa.Column("id", sa.String(36), nullable=False),
            sa.Column("user_id", sa.String(36), nullable=False),
            sa.Column("token_hash", sa.String(255), nullable=False),  # Hashed for security
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("revoked", sa.Boolean(), nullable=False, server_default="false"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("idx_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
        op.create_index("idx_refresh_tokens_expires_at", "refresh_tokens", ["expires_at"])

    # Add indexes to existing tables for performance
    if _has_table("users") and not _has_column("users", "hashed_password"):
        op.add_column("users", sa.Column("hashed_password", sa.Text(), nullable=True))

    if _has_table("users"):
        op.create_index("idx_users_email", "users", ["email"], unique=True)

    if _has_table("sessions"):
        op.create_index("idx_sessions_user_id", "sessions", ["user_id"])


def downgrade() -> None:
    # Drop indexes
    if _has_table("sessions"):
        op.drop_index("idx_sessions_user_id", table_name="sessions")

    if _has_table("users"):
        op.drop_index("idx_users_email", table_name="users")

    if _has_table("refresh_tokens"):
        op.drop_index("idx_refresh_tokens_expires_at", table_name="refresh_tokens")
        op.drop_index("idx_refresh_tokens_user_id", table_name="refresh_tokens")

    if _has_table("feedback"):
        op.drop_index("idx_feedback_quiz_response_id", table_name="feedback")

    if _has_table("quiz_responses"):
        op.drop_index("idx_quiz_responses_submitted_at", table_name="quiz_responses")
        op.drop_index("idx_quiz_responses_concept_id", table_name="quiz_responses")
        op.drop_index("idx_quiz_responses_user_id", table_name="quiz_responses")

    if _has_table("quiz_questions"):
        op.drop_index("idx_quiz_questions_quiz_id", table_name="quiz_questions")

    if _has_table("quizzes"):
        op.drop_index("idx_quizzes_concept_id", table_name="quizzes")

    if _has_table("concepts"):
        op.drop_index("idx_concepts_pdf_id", table_name="concepts")

    if _has_table("pdf_uploads"):
        op.drop_index("idx_pdf_uploads_status", table_name="pdf_uploads")
        op.drop_index("idx_pdf_uploads_user_id", table_name="pdf_uploads")

    # Drop tables
    if _has_table("feedback"):
        op.drop_table("feedback")

    if _has_table("refresh_tokens"):
        op.drop_table("refresh_tokens")

    if _has_table("quiz_responses"):
        op.drop_table("quiz_responses")

    if _has_table("quiz_questions"):
        op.drop_table("quiz_questions")

    if _has_table("quizzes"):
        op.drop_table("quizzes")

    if _has_table("concepts"):
        op.drop_table("concepts")

    if _has_table("pdf_uploads"):
        op.drop_table("pdf_uploads")

    if _has_table("users"):
        if _has_column("users", "hashed_password"):
            op.drop_column("users", "hashed_password")
