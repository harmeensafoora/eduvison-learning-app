"""
Leitner Scheduler Backend - Spaced Repetition State Management (Task 3.1)

Evidence-based spaced repetition intervals:
- Box 1: 1 day (immediate review)
- Box 2: 3 days (reinforcement)
- Box 3: 7 days (long-term retention)

Progression: 3 consecutive correct → advance box
Failure: 1 incorrect → reset to Box 1
"""

import logging
from datetime import datetime, timedelta
from sqlalchemy import select, and_, func
from app.database import AsyncSessionLocal
from app.db_models import SpacedRepState, PDFConcept

logger = logging.getLogger(__name__)

LEITNER_INTERVALS = {
    1: timedelta(days=1),
    2: timedelta(days=3),
    3: timedelta(days=7),
}

STREAK_THRESHOLD = 3


async def get_or_create_spaced_rep_state(
    session, user_id: str, concept_id: str
) -> SpacedRepState:
    """Get existing spaced rep state or create new with box 1."""
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
        await session.flush()
        logger.info(f"Created spaced_rep_state for user {user_id}, concept {concept_id}")
    
    return state


async def schedule_next_review(
    user_id: str, concept_id: str, is_correct: bool
) -> dict:
    """
    Update spaced rep state after quiz answer.
    Handles box progression and scheduling.
    """
    try:
        async with AsyncSessionLocal() as session:
            state = await get_or_create_spaced_rep_state(session, user_id, concept_id)
            
            advanced_box = False
            
            if is_correct:
                state.streak_correct += 1
                if state.streak_correct >= STREAK_THRESHOLD:
                    if state.box < 3:
                        state.box += 1
                        advanced_box = True
                        logger.info(
                            f"Concept {concept_id} advanced from box {state.box - 1} " 
                            f"to box {state.box} for user {user_id}"
                        )
                    state.streak_correct = 0
            else:
                state.box = 1
                state.streak_correct = 0
                logger.info(f"Concept {concept_id} reset to box 1 for user {user_id}")
            
            state.last_review_at = datetime.utcnow()
            state.next_review_at = datetime.utcnow() + LEITNER_INTERVALS[state.box]
            
            await session.commit()
            
            logger.info(
                f"Scheduled {concept_id} for user {user_id}: "
                f"box={state.box}, next={state.next_review_at.isoformat()}, "
                f"correct={is_correct}, streak={state.streak_correct}"
            )
            
            return {
                "box": state.box,
                "next_review_at": state.next_review_at,
                "streak_correct": state.streak_correct,
                "advanced_box": advanced_box,
            }
    
    except Exception as e:
        logger.error(f"Error scheduling review: {e}", exc_info=True)
        return {
            "box": 1,
            "next_review_at": datetime.utcnow() + timedelta(days=1),
            "streak_correct": 0,
            "advanced_box": False,
        }


async def get_user_review_schedule(user_id: str, days_ahead: int = 7) -> list:
    """Get all concepts due for review in next N days."""
    try:
        async with AsyncSessionLocal() as session:
            now = datetime.utcnow()
            future = now + timedelta(days=days_ahead)
            
            stmt = (
                select(SpacedRepState, PDFConcept.name)
                .join(PDFConcept, SpacedRepState.concept_id == PDFConcept.id)
                .where(
                    and_(
                        SpacedRepState.user_id == user_id,
                        SpacedRepState.next_review_at >= now,
                        SpacedRepState.next_review_at <= future,
                    )
                )
                .order_by(SpacedRepState.next_review_at.asc())
            )
            
            results = await session.execute(stmt)
            rows = results.all()
            
            schedule = [
                {
                    "concept_id": str(row[0].concept_id),
                    "name": row[1],
                    "due_at": row[0].next_review_at,
                    "box": row[0].box,
                }
                for row in rows
            ]
            
            logger.info(f"Retrieved {len(schedule)} scheduled reviews for user {user_id}")
            return schedule
    
    except Exception as e:
        logger.error(f"Error retrieving review schedule: {e}", exc_info=True)
        return []


async def get_reviews_due_today(user_id: str) -> int:
    """Count concepts due for review today."""
    try:
        async with AsyncSessionLocal() as session:
            now = datetime.utcnow()
            today_end = now.replace(hour=23, minute=59, second=59)
            
            stmt = select(func.count()).select_from(SpacedRepState).where(
                and_(
                    SpacedRepState.user_id == user_id,
                    SpacedRepState.next_review_at <= today_end,
                    SpacedRepState.next_review_at >= now
                )
            )
            
            count = await session.scalar(stmt)
            return count or 0
    
    except Exception as e:
        logger.error(f"Error counting today's reviews: {e}", exc_info=True)
        return 0
