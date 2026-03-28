"""
Redis Cache Layer for EduVision Phase 1 (Task 1.2)

Purpose:
- Cache feedback generation results to achieve <1.5s latency SLA
- Store concept embeddings for semantic search
- Maintain quiz session state for resumption across browser sessions

TTL Strategy:
- Feedback: 3600s (1 hour) — Students unlikely to retake same quiz <1h
- Embeddings: 86400s (24 hours) — Concept vectors stable, used for search
- Quiz State: 300s (5 minutes) — Temporary mid-quiz progress, expires if abandoned
- Session: 604800s (7 days) — User session tokens for across-browser persistence

Cache Naming Convention:
- feedback:{quiz_response_id} — Cached feedback object (TTL: 1h)
- embedding:{concept_id} — Cached concept embedding (TTL: 24h)
- quiz_state:{quiz_id}:{user_id} — Temporary quiz progress (TTL: 5m)
- session:{session_id} — User session data (TTL: 7d)
"""

import json
import logging
from typing import Optional, Dict, Any
from redis.asyncio import from_url, Redis
from .config import REDIS_URL

logger = logging.getLogger(__name__)

# Global Redis client (singleton)
redis_client: Optional[Redis] = None


async def init_redis() -> Redis:
    """Initialize Redis connection pool on app startup."""
    global redis_client
    try:
        redis_client = await from_url(REDIS_URL, encoding="utf-8", decode_responses=True)
        # Test connection
        await redis_client.ping()
        logger.info(f"✓ Redis connected: {REDIS_URL}")
        return redis_client
    except Exception as e:
        logger.error(f"✗ Redis connection failed: {e}")
        raise


async def close_redis():
    """Close Redis connection on app shutdown."""
    global redis_client
    if redis_client:
        await redis_client.close()
        logger.info("✓ Redis connection closed")


async def get_redis() -> Optional[Redis]:
    """Get the Redis client instance."""
    return redis_client


# ============================================================================
# Cache Functions: Feedback & Latency Optimization
# ============================================================================


async def cache_feedback(
    quiz_response_id: str,
    feedback_data: Dict[str, Any],
    ttl: int = 3600,
) -> bool:
    """
    Cache feedback for quiz response to enable sub-1.5s retrieval.
    
    Args:
        quiz_response_id: Unique ID of quiz response
        feedback_data: Feedback object { text, source_citation, is_correct }
        ttl: Time-to-live in seconds (default: 1 hour)
    
    Returns:
        True if cached successfully, False if Redis unavailable
    """
    if not redis_client:
        return False
    
    try:
        key = f"feedback:{quiz_response_id}"
        await redis_client.setex(
            key,
            ttl,
            json.dumps(feedback_data)
        )
        logger.debug(f"✓ Cached feedback: {key} (TTL: {ttl}s)")
        return True
    except Exception as e:
        logger.warning(f"Failed to cache feedback: {e}")
        return False


async def get_cached_feedback(quiz_response_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve cached feedback for quiz response.
    
    Cache hit latency: <50ms
    Cache miss: Fall through to LLM generation (1-2s)
    
    Args:
        quiz_response_id: Unique ID of quiz response
    
    Returns:
        Feedback dict if cache hit, None if cache miss or Redis unavailable
    """
    if not redis_client:
        return None
    
    try:
        key = f"feedback:{quiz_response_id}"
        data = await redis_client.get(key)
        if data:
            logger.debug(f"✓ Cache hit: {key}")
            return json.loads(data)
        logger.debug(f"✗ Cache miss: {key}")
        return None
    except Exception as e:
        logger.warning(f"Failed to retrieve cached feedback: {e}")
        return None


async def invalidate_feedback_cache(quiz_response_id: str) -> bool:
    """
    Delete cached feedback (e.g., if feedback needs regeneration).
    
    Args:
        quiz_response_id: Unique ID of quiz response
    
    Returns:
        True if deleted, False if not found or Redis unavailable
    """
    if not redis_client:
        return False
    
    try:
        key = f"feedback:{quiz_response_id}"
        deleted = await redis_client.delete(key)
        if deleted:
            logger.debug(f"✓ Invalidas feedback cache: {key}")
        return bool(deleted)
    except Exception as e:
        logger.warning(f"Failed to invalidate feedback cache: {e}")
        return False


# ============================================================================
# Cache Functions: Embeddings & Semantic Search
# ============================================================================


async def cache_embedding(
    concept_id: str,
    embedding_vector: list[float],
    ttl: int = 86400,
) -> bool:
    """
    Cache concept embedding for semantic search.
    
    Args:
        concept_id: Unique ID of concept
        embedding_vector: 1536-dimensional float array from Azure OpenAI
        ttl: Time-to-live in seconds (default: 24 hours)
    
    Returns:
        True if cached successfully, False if Redis unavailable
    """
    if not redis_client:
        return False
    
    try:
        key = f"embedding:{concept_id}"
        # Store as JSON string for compatibility
        await redis_client.setex(
            key,
            ttl,
            json.dumps(embedding_vector)
        )
        logger.debug(f"✓ Cached embedding: {key} (dims: {len(embedding_vector)})")
        return True
    except Exception as e:
        logger.warning(f"Failed to cache embedding: {e}")
        return False


async def get_cached_embedding(concept_id: str) -> Optional[list[float]]:
    """
    Retrieve cached concept embedding.
    
    Args:
        concept_id: Unique ID of concept
    
    Returns:
        Embedding vector if cached, None if cache miss
    """
    if not redis_client:
        return None
    
    try:
        key = f"embedding:{concept_id}"
        data = await redis_client.get(key)
        if data:
            logger.debug(f"✓ Cache hit: {key}")
            return json.loads(data)
        return None
    except Exception as e:
        logger.warning(f"Failed to retrieve embedding: {e}")
        return None


# ============================================================================
# Cache Functions: Quiz Session State
# ============================================================================


async def cache_quiz_state(
    quiz_id: str,
    user_id: str,
    state: Dict[str, Any],
    ttl: int = 300,
) -> bool:
    """
    Cache temporary quiz progress for mid-quiz resumption.
    
    Example state:
    {
        "current_question": 2,
        "answers": { "q1": "option_a", "q2": "option_b" },
        "started_at": "2026-03-28T12:45:00Z"
    }
    
    Args:
        quiz_id: Unique ID of quiz
        user_id: Unique ID of user
        state: Quiz progress object
        ttl: Time-to-live in seconds (default: 5 minutes)
    
    Returns:
        True if cached successfully
    """
    if not redis_client:
        return False
    
    try:
        key = f"quiz_state:{quiz_id}:{user_id}"
        await redis_client.setex(
            key,
            ttl,
            json.dumps(state)
        )
        logger.debug(f"✓ Cached quiz state: {key}")
        return True
    except Exception as e:
        logger.warning(f"Failed to cache quiz state: {e}")
        return False


async def get_cached_quiz_state(quiz_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve cached quiz progress.
    
    Args:
        quiz_id: Unique ID of quiz
        user_id: Unique ID of user
    
    Returns:
        Quiz state if cached, None if expired or not found
    """
    if not redis_client:
        return None
    
    try:
        key = f"quiz_state:{quiz_id}:{user_id}"
        data = await redis_client.get(key)
        if data:
            logger.debug(f"✓ Cache hit: {key}")
            return json.loads(data)
        return None
    except Exception as e:
        logger.warning(f"Failed to retrieve quiz state: {e}")
        return None


async def clear_quiz_state(quiz_id: str, user_id: str) -> bool:
    """
    Delete cached quiz state after submission.
    
    Args:
        quiz_id: Unique ID of quiz
        user_id: Unique ID of user
    
    Returns:
        True if deleted
    """
    if not redis_client:
        return False
    
    try:
        key = f"quiz_state:{quiz_id}:{user_id}"
        deleted = await redis_client.delete(key)
        if deleted:
            logger.debug(f"✓ Cleared quiz state: {key}")
        return bool(deleted)
    except Exception as e:
        logger.warning(f"Failed to clear quiz state: {e}")
        return False


# ============================================================================
# Cache Functions: Session Management
# ============================================================================


async def cache_session(
    session_id: str,
    session_data: Dict[str, Any],
    ttl: int = 604800,
) -> bool:
    """
    Cache user session for across-browser persistence.
    
    Args:
        session_id: Unique session identifier
        session_data: Session object { user_id, access_token, created_at }
        ttl: Time-to-live in seconds (default: 7 days)
    
    Returns:
        True if cached successfully
    """
    if not redis_client:
        return False
    
    try:
        key = f"session:{session_id}"
        await redis_client.setex(
            key,
            ttl,
            json.dumps(session_data)
        )
        logger.debug(f"✓ Cached session: {key} (TTL: {ttl}s)")
        return True
    except Exception as e:
        logger.warning(f"Failed to cache session: {e}")
        return False


async def get_cached_session(session_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve cached session.
    
    Args:
        session_id: Unique session identifier
    
    Returns:
        Session data if cached, None if expired
    """
    if not redis_client:
        return None
    
    try:
        key = f"session:{session_id}"
        data = await redis_client.get(key)
        if data:
            logger.debug(f"✓ Cache hit: {key}")
            return json.loads(data)
        return None
    except Exception as e:
        logger.warning(f"Failed to retrieve session: {e}")
        return None


# ============================================================================
# Health Check
# ============================================================================


async def redis_health_check() -> bool:
    """
    Check Redis connection health.
    
    Returns:
        True if Redis is reachable, False otherwise
    """
    if not redis_client:
        return False
    
    try:
        await redis_client.ping()
        return True
    except Exception as e:
        logger.warning(f"Redis health check failed: {e}")
        return False
