import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, Float, Integer, Boolean, DateTime, ForeignKey, JSON, LargeBinary
from sqlalchemy.orm import relationship
from .database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=_uuid)
    email = Column(String, unique=True, nullable=True)
    display_name = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)
    hashed_password = Column(Text, nullable=True)
    email_verified_at = Column(DateTime, nullable=True)
    auth_provider = Column(String, default="email")
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login_at = Column(DateTime, nullable=True)


class UserProfile(Base):
    __tablename__ = "user_profile"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    preferred_modality = Column(Text, nullable=True, default=None)
    avg_session_length_minutes = Column(Float, default=0)
    total_concepts_mastered = Column(Integer, default=0)
    learning_velocity = Column(Float, default=1.0)
    last_active_at = Column(DateTime, nullable=True)
    streak_days = Column(Integer, default=0)
    cognitive_style = Column(Text, nullable=True, default=None)
    difficulty_preference = Column(Text, default="auto")


class LearningSession(Base):
    __tablename__ = "sessions"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    filename = Column(String, nullable=True)
    pdf_path = Column(String, nullable=True)
    text_content = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    intent = Column(Text, default="Understand the chapter")
    image_paths_json = Column(JSON, default=list)
    concepts_json = Column(JSON, default=list)
    overview_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Concept(Base):
    __tablename__ = "concepts"

    id = Column(String, primary_key=True, default=_uuid)
    session_id = Column(String, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    summary = Column(Text, nullable=True)
    content = Column(Text, nullable=True)
    concept_type = Column(String, default="core")
    importance = Column(Integer, default=1)
    order_index = Column(Integer, default=0)
    prerequisites_json = Column(JSON, default=list)
    estimated_minutes = Column(Float, default=5.0)


class LearningEvent(Base):
    __tablename__ = "learning_events"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    chunk_id = Column(String, ForeignKey("concepts.id", ondelete="SET NULL"), nullable=True)
    session_id = Column(String, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=True)
    event_type = Column(Text, nullable=False)
    payload = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    chunk_id = Column(String, ForeignKey("concepts.id", ondelete="SET NULL"), nullable=True)
    session_id = Column(String, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=True)
    difficulty = Column(Text, default="medium")
    score = Column(Integer, default=0)
    time_taken_ms = Column(Integer, default=0)
    misconceptions = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)


class TopicProgress(Base):
    __tablename__ = "topic_progress"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    session_id = Column(String, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    concept_id = Column(String, ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False)
    score = Column(Integer, default=0)
    attempt_count = Column(Integer, default=0)
    status = Column(String, default="locked")
    needs_simplification = Column(Boolean, default=False)
    current_difficulty = Column(String, default="medium")
    last_attempt_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token = Column(String, unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class EmailToken(Base):
    __tablename__ = "email_tokens"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    email = Column(String, nullable=False, index=True)
    purpose = Column(String, nullable=False)  # verify_email | reset_password
    token_hash = Column(String, nullable=False, unique=True, index=True)
    expires_at = Column(DateTime, nullable=False)
    consumed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ============================================================================
# Phase 1: Core Learning Loop Models
# ============================================================================


class PDFUpload(Base):
    """Stores uploaded PDFs and their processing status (Task 2.1)."""
    __tablename__ = "pdf_uploads"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=False)
    status = Column(String(50), nullable=False, default="uploading")  # uploading, processing, complete, error
    concepts_count = Column(Integer, nullable=True)
    file_size_bytes = Column(Integer, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    processing_started = Column(DateTime, nullable=True)
    processing_completed = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)


class PDFConcept(Base):
    """Stores concepts extracted from PDFs (Task 2.2).
    Named PDFConcept to avoid conflict with existing Concept model (which is session-based).
    """
    __tablename__ = "pdf_concepts"

    id = Column(String, primary_key=True, default=_uuid)
    pdf_id = Column(String, ForeignKey("pdf_uploads.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    definition = Column(Text, nullable=True)
    page_reference = Column(String(100), nullable=True)
    related_concepts = Column(JSON, nullable=True, default=list)
    embedding = Column(LargeBinary, nullable=True)  # For semantic search (1536 dimensions)
    quality_score = Column(Float, nullable=True)  # 1-5 scale, set during human validation
    created_at = Column(DateTime, default=datetime.utcnow)


class Quiz(Base):
    """Stores quiz instances for PDF concepts (Task 2.3)."""
    __tablename__ = "quizzes"

    id = Column(String, primary_key=True, default=_uuid)
    concept_id = Column(String, ForeignKey("pdf_concepts.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class QuizQuestion(Base):
    """Stores individual questions in a quiz (Task 2.3 & 2.4)."""
    __tablename__ = "quiz_questions"

    id = Column(String, primary_key=True, default=_uuid)
    quiz_id = Column(String, ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False, index=True)
    question_text = Column(Text, nullable=False)
    correct_answer = Column(String(255), nullable=False)
    distractors = Column(JSON, nullable=False)  # ["option_2", "option_3", "option_4"]
    explanation = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class QuizResponse(Base):
    """Stores user responses to quizzes (Task 2.4 & 2.5)."""
    __tablename__ = "quiz_responses"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    quiz_id = Column(String, ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False)
    concept_id = Column(String, ForeignKey("pdf_concepts.id", ondelete="CASCADE"), nullable=False, index=True)
    answered = Column(JSON, nullable=False)  # { question_id: user_answer }
    correct_count = Column(Integer, nullable=False)
    total_questions = Column(Integer, nullable=False)
    score_percent = Column(Float, nullable=False)
    submitted_at = Column(DateTime, default=datetime.utcnow, index=True)


class Feedback(Base):
    """Stores feedback for quiz answers (Task 2.5)."""
    __tablename__ = "feedback"

    id = Column(String, primary_key=True, default=_uuid)
    quiz_response_id = Column(String, ForeignKey("quiz_responses.id", ondelete="CASCADE"), nullable=False, index=True)
    question_id = Column(String, ForeignKey("quiz_questions.id", ondelete="CASCADE"), nullable=False)
    is_correct = Column(Boolean, nullable=False)
    feedback_text = Column(Text, nullable=False)
    source_citation = Column(String(255), nullable=True)  # "page 12, section 'Light Reactions'"
    generated_at = Column(DateTime, default=datetime.utcnow)
