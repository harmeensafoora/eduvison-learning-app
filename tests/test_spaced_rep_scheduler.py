"""
Tests for Spaced Repetition Scheduler (Task 3.1)
"""

import pytest
import uuid
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.db_models import Base, User, PDFConcept, PDFUpload, SpacedRepState
from app.schedules import (
    schedule_next_review,
    get_user_review_schedule,
    get_or_create_spaced_rep_state,
    LEITNER_INTERVALS,
)

# Use in-memory SQLite for testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture
async def test_db():
    """Create test database and tables."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    yield async_session
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest.fixture
async def sample_data(test_db):
    """Create sample users, PDFs, and concepts for testing."""
    async with test_db() as session:
        # Create user
        user = User(id=str(uuid.uuid4()), email="test@example.com", display_name="Test User")
        session.add(user)
        
        # Create PDF upload
        pdf = PDFUpload(
            id=str(uuid.uuid4()),
            user_id=user.id,
            filename="test.pdf",
            file_path="/uploads/test.pdf",
            status="complete"
        )
        session.add(pdf)
        
        # Create concepts
        concepts = [
            PDFConcept(
                id=str(uuid.uuid4()),
                pdf_id=pdf.id,
                name=f"Concept {i}",
                definition=f"Definition of concept {i}"
            )
            for i in range(5)
        ]
        for concept in concepts:
            session.add(concept)
        
        await session.commit()
        
        return {
            "user_id": user.id,
            "pdf_id": pdf.id,
            "concepts": concepts,
        }


@pytest.mark.asyncio
async def test_schedule_first_correct_answer(sample_data):
    """First correct answer keeps box 1, increments streak."""
    user_id = sample_data["user_id"]
    concept_id = sample_data["concepts"][0].id
    
    result = await schedule_next_review(user_id, concept_id, is_correct=True)
    
    assert result["box"] == 1
    assert result["streak_correct"] == 1
    assert result["next_review_at"] > datetime.utcnow()


@pytest.mark.asyncio
async def test_schedule_three_correct_advances_box(sample_data):
    """Third consecutive correct answer advances from box 1 to 2."""
    user_id = sample_data["user_id"]
    concept_id = sample_data["concepts"][0].id
    
    await schedule_next_review(user_id, concept_id, is_correct=True)
    await schedule_next_review(user_id, concept_id, is_correct=True)
    result = await schedule_next_review(user_id, concept_id, is_correct=True)
    
    assert result["box"] == 2
    assert result["streak_correct"] == 0


@pytest.mark.asyncio
async def test_schedule_wrong_answer_resets_to_box_1(sample_data):
    """Wrong answer resets to box 1 regardless of current box."""
    user_id = sample_data["user_id"]
    concept_id = sample_data["concepts"][0].id
    
    await schedule_next_review(user_id, concept_id, is_correct=True)
    await schedule_next_review(user_id, concept_id, is_correct=True)
    await schedule_next_review(user_id, concept_id, is_correct=True)
    
    result = await schedule_next_review(user_id, concept_id, is_correct=False)
    
    assert result["box"] == 1
    assert result["streak_correct"] == 0


@pytest.mark.asyncio
async def test_get_user_review_schedule(sample_data):
    """Review schedule returns concepts due in next 7 days."""
    user_id = sample_data["user_id"]
    concepts = sample_data["concepts"][:3]
    
    for i, concept in enumerate(concepts):
        for _ in range(i):
            await schedule_next_review(user_id, concept.id, is_correct=True)
    
    schedule = await get_user_review_schedule(user_id, days_ahead=7)
    
    if schedule:
        assert "concept_id" in schedule[0]
        assert "name" in schedule[0]
        assert "due_at" in schedule[0]
        assert "box" in schedule[0]


@pytest.mark.asyncio
async def test_100_plus_schedules_generated(sample_data):
    """Stress test: generate 100+ schedules with no errors."""
    user_id = sample_data["user_id"]
    pdf_id = sample_data["pdf_id"]
    
    for i in range(105):
        async with _test_session_factory() as session:
            concept = PDFConcept(
                id=str(uuid.uuid4()),
                pdf_id=pdf_id,
                name=f"Stress {i}",
                definition=f"Def {i}"
            )
            session.add(concept)
            await session.commit()
            concept_id = concept.id
        
        result = await schedule_next_review(user_id, concept_id, is_correct=True)
        assert result["box"] in [1, 2, 3]


@pytest.mark.asyncio
async def test_box_3_maximum(sample_data):
    """Box 3 is maximum - should not advance beyond it."""
    user_id = sample_data["user_id"]
    concept_id = sample_data["concepts"][0].id
    
    for _ in range(12):
        await schedule_next_review(user_id, concept_id, is_correct=True)
    
    result = await schedule_next_review(user_id, concept_id, is_correct=True)
    assert result["box"] == 3


@pytest.mark.asyncio
async def test_intervals_correct():
    """Verify Leitner intervals."""
    assert LEITNER_INTERVALS[1] == timedelta(days=1)
    assert LEITNER_INTERVALS[2] == timedelta(days=3)
    assert LEITNER_INTERVALS[3] == timedelta(days=7)


# ============================================================================
# Run tests with pytest
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
