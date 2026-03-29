"""
Elaboration Prompt Generator - Post-Quiz Learning Enhancement

Generates elaboration prompts after correct quiz answers to deepen encoding.
Features:
- Azure OpenAI integration with strict <1.5s timeout
- Redis caching (24h TTL) for concept elaborations
- Sensible fallback prompts on timeout/error
- 5 prompt types: application, connection, explanation, reflection, misconception
"""

import asyncio
import logging
import json
from typing import Optional
from datetime import timedelta

logger = logging.getLogger(__name__)

# Cache configuration
ELABORATION_CACHE_TTL = 86400  # 24 hours


async def get_elaboration_prompt(
    concept_id: str,
    concept_name: str,
    concept_summary: Optional[str] = None,
    user_history: Optional[dict] = None
) -> dict:
    """
    Retrieve or generate elaboration prompt for a concept.
    
    Strategy:
    1. Check Redis cache (TTL 24h) — if exists, return cached
    2. Generate fresh via Azure OpenAI (JSON mode) with timeout
    3. On timeout or error, return sensible fallback
    4. Cache result + return
    
    Args:
        concept_id: Unique concept identifier
        concept_name: Human-readable concept name
        concept_summary: Optional summary for context
        user_history: Optional dict with prior attempts
        
    Returns:
        {"prompt": str, "type": str, "cached": bool}
    """
    from app.cache import redis_client
    
    cache_key = f"elaboration:{concept_id}"
    
    # Step 1: Try cache
    if redis_client:
        try:
            cached = await redis_client.get(cache_key)
            if cached:
                logger.debug(f"Elaboration cache hit for {concept_id}")
                data = json.loads(cached)
                data["cached"] = True
                return data
        except Exception as e:
            logger.warning(f"Cache lookup failed: {e}")
    
    # Step 2: Generate fresh with timeout
    try:
        logger.info(f"Generating elaboration prompt for {concept_id}")
        
        prompt_obj = await asyncio.wait_for(
            _generate_elaboration_openai(concept_name, concept_summary, user_history),
            timeout=1.2  # Strict 1.2s timeout (buffer from 1.5s SLA)
        )
        
        # Cache result
        prompt_obj["cached"] = False
        if redis_client:
            try:
                await redis_client.setex(
                    cache_key,
                    ELABORATION_CACHE_TTL,
                    json.dumps(prompt_obj)
                )
            except Exception as e:
                logger.warning(f"Failed to cache elaboration: {e}")
        
        return prompt_obj
    
    except asyncio.TimeoutError:
        logger.warning(f"Elaboration generation timeout for {concept_id} - using fallback")
        fallback = _get_fallback_prompt(concept_name)
        
        # Cache fallback for 1 hour only
        if redis_client:
            try:
                await redis_client.setex(
                    cache_key,
                    3600,
                    json.dumps({"prompt": fallback, "type": "fallback", "cached": False})
                )
            except Exception:
                pass
        
        return {"prompt": fallback, "type": "fallback", "cached": False}
    
    except Exception as e:
        logger.error(f"Elaboration generation failed: {e}", exc_info=True)
        fallback = _get_fallback_prompt(concept_name)
        return {"prompt": fallback, "type": "fallback", "cached": False}


async def _generate_elaboration_openai(
    concept_name: str,
    concept_summary: Optional[str],
    user_history: Optional[dict]
) -> dict:
    """
    Generate elaboration prompt via Azure OpenAI with JSON mode.
    
    Returns: {"prompt": str, "type": "application|connection|explanation|reflection|misconception"}
    """
    from app.azure_openai_utils import azure_json
    
    system_prompt = """You are an expert learning science tutor. Generate a single, specific elaboration question 
(1-2 sentences max) that helps learners deepen understanding through generative retrieval.

Elaboration types:
- Application: Ask learner to apply concept to a new domain or situation
- Connection: Ask how concept relates to prior knowledge or other concepts  
- Explanation: Ask learner to explain in own words or teach to specific audience
- Reflection: Ask learner to reflect on personal experience or misconceptions
- Misconception: Ask about common misconceptions for this concept

IMPORTANT: Output ONLY valid JSON. No markdown, no code blocks."""

    history_context = ""
    if user_history and user_history.get("prior_errors"):
        history_context = f"\nUser struggled with: {', '.join(user_history['prior_errors'][:2])}"

    user_prompt = f"""Generate an elaboration question for this concept:
Name: "{concept_name}"
{f'Summary: {concept_summary}' if concept_summary else ''}{history_context}

Return ONLY valid JSON (no markdown):
{{"prompt": "question text here (1-2 sentences)", "type": "application|connection|explanation|reflection|misconception"}}"""

    result = await azure_json(
        system=system_prompt,
        prompt=user_prompt,
        json_mode=True,
        timeout_seconds=1.0
    )
    
    return result


def _get_fallback_prompt(concept_name: str) -> str:
    """Generate sensible fallback prompt when generator fails/times out."""
    fallback_templates = [
        f"How would you explain '{concept_name}' to someone with no background knowledge?",
        f"What's a real-world example of '{concept_name}' that you've encountered?",
        f"How does '{concept_name}' connect to what you already know about this subject?",
        f"Why might someone confuse '{concept_name}' with something else?",
        f"Can you think of a situation where understanding '{concept_name}' would be important?",
    ]
    
    # Rotate based on concept name hash to add variety
    idx = hash(concept_name) % len(fallback_templates)
    return fallback_templates[idx]
