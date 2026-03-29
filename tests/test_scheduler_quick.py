"""Quick validation of Task 3.1 implementation"""

import asyncio
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
import uuid
from app.db_models import Base, User, PDFConcept, PDFUpload
from app.schedules import schedule_next_review

async def test_basic():
    """Test basic scheduler functionality."""
    engine = create_async_engine('sqlite+aiosqlite:///:memory:', echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    import app.schedules
    app.schedules.async_session_factory = AsyncSessionLocal
    
    # Create test data
    async with AsyncSessionLocal() as session:
        user = User(id=str(uuid.uuid4()), email='test@example.com')
        pdf = PDFUpload(id=str(uuid.uuid4()), user_id=user.id, filename='test.pdf', file_path='/tmp/test.pdf', status='complete')
        concept = PDFConcept(id=str(uuid.uuid4()), pdf_id=pdf.id, name='Test Concept', definition='A test')
        session.add_all([user, pdf, concept])
        await session.commit()
        user_id, concept_id = user.id, concept.id
    
    # Test basic flow
    print("Testing Task 3.1: Leitner Scheduler")
    print("-" * 50)
    
    # Test 1: First correct answer
    result = await schedule_next_review(user_id, concept_id, is_correct=True)
    assert result['box'] == 1, f"Expected box 1, got {result['box']}"
    assert result['streak_correct'] == 1, f"Expected streak 1, got {result['streak_correct']}"
    print("✓ Test 1: First correct answer - BOX 1, STREAK 1")
    
    # Test 2: Two more correct answers = advance to box 2
    await schedule_next_review(user_id, concept_id, is_correct=True)
    result = await schedule_next_review(user_id, concept_id, is_correct=True)
    assert result['box'] == 2, f"Expected box 2, got {result['box']}"
    assert result['streak_correct'] == 0, f"Expected streak 0 after advancement, got {result['streak_correct']}"
    print("✓ Test 2: Three correct answers - BOX 2 (advanced)")
    
    # Test 3: Wrong answer resets to box 1
    result = await schedule_next_review(user_id, concept_id, is_correct=False)
    assert result['box'] == 1, f"Expected box 1 after wrong answer, got {result['box']}"
    assert result['streak_correct'] == 0, f"Expected streak 0, got {result['streak_correct']}"
    print("✓ Test 3: Wrong answer - RESET TO BOX 1")
    
    print("\n✅ Task 3.1: Scheduler Tests PASSED")
    return True

if __name__ == '__main__':
    asyncio.run(test_basic())
