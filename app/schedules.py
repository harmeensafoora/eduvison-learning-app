"""
Spaced Repetition Scheduler - Leitner System Implementation

Uses evidence-based intervals (Karpicke & Roediger 2007):
- Box 1: Review in 1 day
- Box 2: Review in 3 days  
- Box 3: Review in 7 days

After 3 consecutive correct answers, advance to next box.
Wrong answer resets to Box 1.
"""

import logging
from datetime import datetime, timedelta
from sqlalchemy import select, and_
from app.database import async_session_factory
from app.db_models import SpacedRepState, PDFConcept

logger = logging.getLogger(__name__)

# Leitner intervals: Evidence-based (Karpicke & Roediger 2007)
LEITNER_INTERVALS = {
    1: timedelta(days=1),   # Box 1: review tomorrow
    2: timedelta(days=3),   # Box 2: review in 3 days
    3: timedelta(days=7),   # Box 3: review in 7 days
}


async def get_or_create_spaced_rep_state(
    session, user_id: str, concept_id: str
) -> SpacedRepState:
    """Get existing spaced rep state or create new (default box 1)."""
    stmt = select(SpacedRepState).where(
        and_(
            SpacedRepState.user_id == user_id,
            SpacedRepState.concept_id == concept_id,
        )
    )
    state = await session.scalar(stmt)
    if not state:
        state = SpacedRepState(
            user_id=user_id,
            concept_id=concept_id,
            box=1,
            streak_correct=0,
            next_review_at=datetime.utcnow() + timedelta(days=1),
        )
        session.add(state)
        await session.flush()  # Ensure ID assigned
    return state


async def schedule_next_review(
    user_id: str, concept_id: str, is_correct: bool
) -> dict:
    """
    Update spaced rep state after quiz answer.
    
    Rules:
    - Correct answer: increment streak; if streak==3, advance box
    - Incorrect answer: reset to box 1, streak 0
    - Next review based on current box (LEITNER_INTERVALS)
    
    Returns: {"box": int, "next_review_at": datetime, "streak_correct": int}
    """
    async with async_session_factory() as session:
        state = await get_or_create_spaced_rep_state(session, user_id, concept_id)
        
        if is_correct:
            state.streak_correct += 1
            if state.streak_correct >= 3:  # Ready to advance
                state.box = min(state.box + 1, 3)  # Cap at box 3
                state.streak_correct = 0
        else:
            state.box = 1
            state.streak_correct = 0
        
        state.last_review_at = datetime.utcnow()
        state.next_review_at = datetime.utcnow() + LEITNER_INTERVALS[state.box]
        
        await session.commit()
        
        logger.info(
            f"Scheduled {concept_id} for user {user_id}: "
            f"box={state.box}, next={state.next_review_at}, correct={is_correct}"
        )
        
        return {
            "box": state.box,
            "next_review_at": state.next_review_at,
            "streak_correct": state.streak_correct,
        }


async def get_user_review_schedule(user_id: str, days_ahead: int = 7) -> list:
    """
    Get all concepts due for review in next N days, grouped by due date.
    Used by dashboard to show "review today", "review this week" cards.
    
    Returns: [
        {"concept_id": "...", "name": "...", "due_at": datetime, "box": int},
        ...
    ]
    Ordered by due_at ascending.
    """
    async with async_session_factory() as session:
        now = datetime.utcnow()
        future = now + timedelta(days=days_ahead)
        
        stmt = (
            select(SpacedRepState, PDFConcept.name)
            .join(PDFConcept)
            .where(
                and_(
                    SpacedRepState.user_id == user_id,
                    SpacedRepState.next_review_at >= now,
                    SpacedRepState.next_review_at <= future,
                )
            )
            .order_by(SpacedRepState.next_review_at)
        )
        
        results = await session.execute(stmt)
        rows = results.all()
        
        return [
            {
                "concept_id": str(row[0].concept_id),
                "name": row[1],
                "due_at": row[0].next_review_at,
                "box": row[0].box,
            }
            for row in rows
        ]
