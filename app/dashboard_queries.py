"""
Dashboard Backend Queries & APIs (Task 3.3)

Optimized PostgreSQL queries for dashboard stats showing:
1. get_dashboard_stats(): Aggregated progress (concepts, score, streak)
2. get_review_calendar(): Calendar of due reviews (next 7 days)
3. get_recent_quizzes(): Last N quiz attempts with scores

Performance targets:
- Cold queries: <100ms
- Cached queries: <10ms
- Redis TTL: 10 minutes
- Cache invalidation on quiz submission
"""

import json
import logging
from datetime import datetime, timedelta
from sqlalchemy import select, func, and_
from app.database import AsyncSessionLocal
from app.db_models import (
    User,
    PDFConcept,
    QuizAttempt,
    SpacedRepState,
    QuizResponse,
)
from app.cache import redis_client

logger = logging.getLogger(__name__)

DASHBOARD_CACHE_TTL = 600  # 10 minutes


async def redis_get(key: str):
    """Safely get from Redis with error handling."""
    try:
        if redis_client:
            return await redis_client.get(key)
    except Exception as e:
        logger.warning(f"Redis get failed: {e}")
    return None


async def redis_set(key: str, value: str, ex: int = DASHBOARD_CACHE_TTL):
    """Safely set to Redis with error handling."""
    try:
        if redis_client:
            await redis_client.setex(key, ex, value)
    except Exception as e:
        logger.warning(f"Redis set failed: {e}")


async def get_dashboard_stats(user_id: str) -> dict:
    """
    Aggregated dashboard statistics for home view.
    
    Returns:
        {
            "concepts_mastered": int,
            "concepts_in_progress": int,
            "total_quizzes_completed": int,
            "average_score": float,
            "current_streak": int,
            "next_review_today": int,
            "learning_time_hours": float,
        }
    
    Cache: 10 minutes (invalidated on quiz submit)
    Query latency: <100ms cold, <10ms cached
    """
    cache_key = f"dashboard:stats:{user_id}"
    cached = await redis_get(cache_key)
    if cached:
        logger.info(f"Dashboard stats cache hit for {user_id}")
        return json.loads(cached)
    
    try:
        async with AsyncSessionLocal() as session:
            now = datetime.utcnow()
            today_end = now.replace(hour=23, minute=59, second=59)
            
            # 1. Count concepts mastered (assumption: QuizResponse score >= 90)
            mastered_stmt = select(func.count(func.distinct(QuizResponse.concept_id))).where(
                and_(
                    QuizResponse.user_id == user_id,
                    QuizResponse.score_percent >= 90
                )
            )
            concepts_mastered = await session.scalar(mastered_stmt) or 0
            
            # 2. Count quiz attempts
            total_quizzes_stmt = select(func.count()).select_from(QuizResponse).where(
                QuizResponse.user_id == user_id
            )
            total_quizzes = await session.scalar(total_quizzes_stmt) or 0
            
            # 3. Average score
            avg_score_stmt = select(func.avg(QuizResponse.score_percent)).where(
                QuizResponse.user_id == user_id
            )
            avg_score = await session.scalar(avg_score_stmt) or 0.0
            
            # 4. Current streak (consecutive correct)
            recent_stmt = (
                select(QuizResponse.score_percent)
                .where(QuizResponse.user_id == user_id)
                .order_by(QuizResponse.submitted_at.desc())
                .limit(20)
            )
            recent_results = await session.execute(recent_stmt)
            streak = 0
            for row in recent_results:
                if row[0] >= 80:
                    streak += 1
                else:
                    break
            
            # 5. Reviews due today from spaced rep
            today_reviews_stmt = select(func.count()).select_from(SpacedRepState).where(
                and_(
                    SpacedRepState.user_id == user_id,
                    SpacedRepState.next_review_at <= today_end,
                    SpacedRepState.next_review_at >= now
                )
            )
            today_reviews = await session.scalar(today_reviews_stmt) or 0
            
            # 6. Learning time estimate (5 min per quiz)
            learning_minutes = total_quizzes * 5
            learning_hours = learning_minutes / 60.0
            
            # 7. Concepts in progress (between mastery thresholds)
            concepts_in_progress = max(0, total_quizzes - concepts_mastered)
            
            stats = {
                "concepts_mastered": concepts_mastered,
                "concepts_in_progress": concepts_in_progress,
                "total_quizzes_completed": total_quizzes,
                "average_score": round(float(avg_score), 1),
                "current_streak": streak,
                "next_review_today": today_reviews,
                "learning_time_hours": round(learning_hours, 1),
            }
            
            # Cache result
            await redis_set(cache_key, json.dumps(stats))
            logger.info(f"Dashboard stats calculated for {user_id}")
            return stats
    
    except Exception as e:
        logger.error(f"Error retrieving dashboard stats: {e}", exc_info=True)
        return {
            "concepts_mastered": 0,
            "concepts_in_progress": 0,
            "total_quizzes_completed": 0,
            "average_score": 0.0,
            "current_streak": 0,
            "next_review_today": 0,
            "learning_time_hours": 0.0,
        }


async def get_review_calendar(user_id: str, days_ahead: int = 7) -> dict:
    """
    Calendar of concepts due for review (next N days).
    
    Returns:
        {
            "today": int,
            "this_week": int,
            "days": [
                {
                    "date": "2026-03-30",
                    "count": 3,
                    "concepts": [{"name": "...", "box": 1}, ...]
                },
                ...
            ]
        }
    
    Cache: 10 minutes
    Query latency: <100ms cold
    """
    cache_key = f"dashboard:calendar:{user_id}:{days_ahead}"
    cached = await redis_get(cache_key)
    if cached:
        logger.info(f"Review calendar cache hit for {user_id}")
        return json.loads(cached)
    
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
            
            # Group by date
            by_date = {}
            today_count = 0
            week_count = 0
            
            for state, concept_name in rows:
                date_key = state.next_review_at.date()
                if date_key not in by_date:
                    by_date[date_key] = []
                
                by_date[date_key].append({
                    "name": concept_name,
                    "box": state.box,
                    "concept_id": str(state.concept_id)
                })
                
                if state.next_review_at.date() == now.date():
                    today_count += 1
                week_count += 1
            
            # Format response
            calendar = {
                "today": today_count,
                "this_week": week_count,
                "days": [
                    {
                        "date": date.isoformat(),
                        "count": len(concepts),
                        "concepts": concepts
                    }
                    for date, concepts in sorted(by_date.items())
                ]
            }
            
            await redis_set(cache_key, json.dumps(calendar))
            return calendar
    
    except Exception as e:
        logger.error(f"Error retrieving review calendar: {e}", exc_info=True)
        return {"today": 0, "this_week": 0, "days": []}


async def get_recent_quizzes(user_id: str, limit: int = 5) -> list:
    """
    Recent quiz submissions with scores and concepts.
    
    Returns:
        [
            {
                "quiz_id": "...",
                "concept_name": "...",
                "score": 95,
                "submitted_at": "2026-03-29T14:30:00",
                "is_correct": true
            },
            ...
        ]
    
    Cache: 10 minutes
    Query latency: <100ms cold
    """
    cache_key = f"dashboard:recent:{user_id}:{limit}"
    cached = await redis_get(cache_key)
    if cached:
        logger.info(f"Recent quizzes cache hit for {user_id}")
        return json.loads(cached)
    
    try:
        async with AsyncSessionLocal() as session:
            stmt = (
                select(QuizResponse, PDFConcept.name)
                .outerjoin(PDFConcept, QuizResponse.concept_id == PDFConcept.id)
                .where(QuizResponse.user_id == user_id)
                .order_by(QuizResponse.submitted_at.desc())
                .limit(limit)
            )
            
            results = await session.execute(stmt)
            rows = results.all()
            
            recent = [
                {
                    "quiz_id": str(row[0].id),
                    "concept_name": row[1] or "Unknown",
                    "score": row[0].score_percent,
                    "submitted_at": row[0].submitted_at.isoformat(),
                    "is_correct": row[0].score_percent >= 80,
                }
                for row in rows
            ]
            
            await redis_set(cache_key, json.dumps(recent))
            return recent
    
    except Exception as e:
        logger.error(f"Error retrieving recent quizzes: {e}", exc_info=True)
        return []


async def invalidate_dashboard_cache(user_id: str):
    """
    Invalidate all dashboard caches for user.
    Called after quiz submit to ensure fresh stats.
    """
    cache_keys = [
        f"dashboard:stats:{user_id}",
        f"dashboard:calendar:{user_id}:7",
        f"dashboard:recent:{user_id}:5",
    ]
    
    try:
        for key in cache_keys:
            if redis_client:
                await redis_client.delete(key)
        logger.info(f"Dashboard cache invalidated for {user_id}")
    except Exception as e:
        logger.warning(f"Cache invalidation partial failure: {e}")
