"""
LLM Pipeline Functions for Learning Content Generation

Handles:
- Concept extraction from PDF text
- Quiz question generation with MCQ format
- Personalized feedback generation on quiz responses
- Response validation and error handling
"""

import json
import logging
from typing import List, Dict, Any, Optional

from .azure_openai_client import call_azure_openai_completion, validate_json_response

logger = logging.getLogger(__name__)


async def extract_concepts(
    pdf_text: str,
    title: str = "",
    max_concepts: int = 8,
) -> List[Dict[str, Any]]:
    """
    Extract key learning concepts from PDF text using Azure OpenAI

    Args:
        pdf_text: Full text extracted from PDF document
        title: Optional document title for context
        max_concepts: Maximum number of concepts to extract (default 8)

    Returns:
        List of concept dicts with:
        - name: Concept name
        - definition: Clear definition/explanation
        - page_reference: Estimated page number
        - related_concepts: List of related concept names
        - importance: 'high'/'medium'/'low'

    Raises:
        ValueError: If LLM response is invalid or unparseable
        Exception: If API call fails (retried 3x automatically)

    Example:
        >>> concepts = await extract_concepts("The mitochondria is...", title="Biology 101")
        >>> len(concepts) <= 8
        >>> concepts[0]['importance'] in ['high', 'medium', 'low']
    """
    prompt = f"""
Analyze the following educational text and extract the {max_concepts} most important learning concepts.

For each concept, provide:
1. **name**: Short concept name (2-4 words)
2. **definition**: Clear, student-friendly explanation (1-2 sentences)
3. **page_reference**: Estimated page number (0-based index into text chunks)
4. **related_concepts**: List of related concept names (2-3 concepts)
5. **importance**: 'high' (foundational), 'medium' (important), or 'low' (supporting)

Focus on:
- Foundational concepts students must understand
- Clear, actionable definitions
- Relationships between concepts
- Pedagogical importance

Document Title: {title if title else "Untitled"}

TEXT TO ANALYZE:
{pdf_text[:5000]}  # Limit to first 5000 chars for API efficiency

Return ONLY valid JSON array with no markdown:
"""

    try:
        response_text = await call_azure_openai_completion(
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert educational content specialist. Extract learning concepts that help students understand and retain knowledge.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=2000,
            json_mode=True,
        )

        concepts = validate_json_response(
            response_text,
            expected_keys=[],
        )

        # Ensure it's a list
        if not isinstance(concepts, list):
            concepts = [concepts]

        # Validate concept structure
        for concept in concepts:
            required = ["name", "definition", "page_reference", "related_concepts", "importance"]
            if not all(key in concept for key in required):
                raise ValueError(f"Concept missing required fields: {concept}")

            # Validate importance enum
            if concept["importance"] not in ["high", "medium", "low"]:
                concept["importance"] = "medium"

        logger.info(f"Extracted {len(concepts)} concepts from PDF text")
        return concepts[:max_concepts]  # Enforce max limit

    except Exception as e:
        logger.error(f"Concept extraction failed: {str(e)}")
        raise ValueError(f"Failed to extract concepts: {str(e)}")


async def generate_quiz_questions(
    concept_name: str,
    concept_definition: str,
    context_text: str = "",
    num_questions: int = 3,
) -> List[Dict[str, Any]]:
    """
    Generate multiple-choice quiz questions for a learning concept

    Args:
        concept_name: Name of the concept
        concept_definition: Definition/explanation of the concept
        context_text: Optional surrounding text from document
        num_questions: Number of questions to generate (default 3)

    Returns:
        List of question dicts with:
        - question_text: The MCQ question
        - distractors: List of 3-4 wrong answers (will be shuffled client-side)
        - correct_answer: The correct answer (should be one of distractors)
        - explanation: Why this is correct (for post-submission feedback)
        - difficulty: 'easy'/'medium'/'hard'

    Raises:
        ValueError: If LLM response is invalid
        Exception: If API call fails

    Example:
        >>> questions = await generate_quiz_questions(
        ...     "Photosynthesis",
        ...     "Process where plants convert light to chemical energy",
        ... )
        >>> len(questions) == 3
        >>> all(q['correct_answer'] in q['distractors'] for q in questions)
    """
    prompt = f"""
Generate {num_questions} high-quality multiple-choice questions to test understanding of this concept:

Concept: {concept_name}
Definition: {concept_definition}
{f"Context: {context_text[:1000]}" if context_text else ""}

For each question:
1. **question_text**: Clear, specific question testing understanding (not memorization)
2. **distractors**: List of 4 possible answers including 1 correct + 3 plausible wrong answers
3. **correct_answer**: Exact match of one item from distractors
4. **explanation**: Clear explanation of why this is correct (50-100 words)
5. **difficulty**: 'easy' (basic recall), 'medium' (application), 'hard' (analysis/synthesis)

Guidelines:
- Avoid trick questions or ambiguous wording
- Make distractors plausible but clearly wrong
- Test understanding, not memorization
- Include a mix of difficulty levels
- Explanations should help students learn

Return ONLY valid JSON array of question objects:
"""

    try:
        response_text = await call_azure_openai_completion(
            messages=[
                {
                    "role": "system",
                    "content": "You are an experienced educational test designer. Create fair, effective multiple-choice questions that accurately assess understanding.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.8,
            max_tokens=2500,
            json_mode=True,
        )

        questions = validate_json_response(
            response_text,
            expected_keys=[],
        )

        # Ensure it's a list
        if not isinstance(questions, list):
            questions = [questions]

        # Validate question structure
        for i, question in enumerate(questions):
            required = ["question_text", "distractors", "correct_answer", "explanation", "difficulty"]
            if not all(key in question for key in required):
                raise ValueError(f"Question {i} missing required fields")

            # Validate correct answer is in distractors
            if question["correct_answer"] not in question["distractors"]:
                logger.warning(f"Question {i}: correct answer not in distractors, adding it")
                question["distractors"].append(question["correct_answer"])

            # Validate difficulty
            if question["difficulty"] not in ["easy", "medium", "hard"]:
                question["difficulty"] = "medium"

        logger.info(f"Generated {len(questions)} quiz questions for {concept_name}")
        return questions[:num_questions]  # Enforce max limit

    except Exception as e:
        logger.error(f"Quiz question generation failed: {str(e)}")
        raise ValueError(f"Failed to generate quiz questions: {str(e)}")


async def generate_feedback(
    concept_name: str,
    question_text: str,
    user_answer: str,
    correct_answer: str,
    is_correct: bool,
    explanation: str = "",
    user_knowledge_level: str = "intermediate",
) -> Dict[str, Any]:
    """
    Generate personalized feedback on a quiz response using Azure OpenAI

    Args:
        concept_name: Concept being tested
        question_text: The quiz question
        user_answer: User's submitted answer
        correct_answer: The correct answer
        is_correct: Whether user's answer was correct
        explanation: Question explanation from quiz data
        user_knowledge_level: 'beginner'/'intermediate'/'advanced' for personalization

    Returns:
        Dict with:
        - feedback_text: Personalized feedback (50-150 words)
        - is_correct: Boolean confirmation
        - source_citation: Reference to concept/context
        - next_learning_steps: List of 2-3 suggested topics to review
        - confidence_score: 0.0-1.0 confidence in feedback quality

    Raises:
        ValueError: If LLM response is invalid
        Exception: If API call fails

    Example:
        >>> feedback = await generate_feedback(
        ...     "Photosynthesis",
        ...     "What is the main product of photosynthesis?",
        ...     "Carbon dioxide",
        ...     "Glucose",
        ...     False,
        ... )
        >>> feedback['is_correct'] == False
        >>> len(feedback['next_learning_steps']) > 0
    """
    correctness_phrase = "You answered correctly!" if is_correct else "This answer needs review."

    prompt = f"""
Generate personalized learning feedback for a student quiz response.

Context:
- Concept: {concept_name}
- Knowledge Level: {user_knowledge_level}
- Question: {question_text}
- User's Answer: {user_answer}
- Correct Answer: {correct_answer}
- Result: {correctness_phrase}
- Explanation: {explanation}

Generate feedback that:
1. Acknowledges the student's attempt
2. Clarifies the correct concept ({correctness_phrase})
3. Explains WHY the answer is correct/incorrect
4. Connects to the broader concept learning
5. Suggests 2-3 related topics to review next

Adapt the language to a {user_knowledge_level} level student.

Return ONLY valid JSON with:
{{
    "feedback_text": "Personalized feedback (50-150 words)",
    "is_correct": {str(is_correct).lower()},
    "source_citation": "Where in the concept/document this comes from",
    "next_learning_steps": ["Topic 1", "Topic 2", "Topic 3"],
    "confidence_score": 0.85
}}
"""

    try:
        response_text = await call_azure_openai_completion(
            messages=[
                {
                    "role": "system",
                    "content": "You are a supportive educational tutor. Provide encouraging, clear feedback that helps students learn and correct misconceptions.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.8,
            max_tokens=1000,
            json_mode=True,
        )

        feedback = validate_json_response(
            response_text,
            expected_keys=[
                "feedback_text",
                "is_correct",
                "source_citation",
                "next_learning_steps",
                "confidence_score",
            ],
        )

        # Validate confidence score
        confidence = feedback.get("confidence_score", 0.8)
        if not isinstance(confidence, (int, float)):
            confidence = 0.8
        feedback["confidence_score"] = max(0.0, min(1.0, confidence))

        logger.info(f"Generated feedback for {concept_name} question")
        return feedback

    except Exception as e:
        logger.error(f"Feedback generation failed: {str(e)}")
        raise ValueError(f"Failed to generate feedback: {str(e)}")


async def batch_generate_feedback(
    responses: List[Dict[str, Any]],
    user_knowledge_level: str = "intermediate",
) -> List[Dict[str, Any]]:
    """
    Generate feedback for multiple quiz responses (batch operation)

    Args:
        responses: List of response dicts with required fields
        user_knowledge_level: User's general knowledge level

    Returns:
        List of feedback dicts with same structure as generate_feedback

    Note:
        Processes sequentially to respect API rate limits
    """
    feedbacks = []

    for response in responses:
        try:
            feedback = await generate_feedback(
                concept_name=response.get("concept_name", "Unknown Concept"),
                question_text=response.get("question_text", ""),
                user_answer=response.get("user_answer", ""),
                correct_answer=response.get("correct_answer", ""),
                is_correct=response.get("is_correct", False),
                explanation=response.get("explanation", ""),
                user_knowledge_level=user_knowledge_level,
            )
            feedbacks.append(feedback)

        except Exception as e:
            logger.error(f"Failed to generate feedback for response: {str(e)}")
            # Add error feedback instead of failing entire batch
            feedbacks.append(
                {
                    "feedback_text": "Unable to generate personalized feedback at this time. Please try again later.",
                    "is_correct": response.get("is_correct", False),
                    "source_citation": "Error in feedback generation",
                    "next_learning_steps": [],
                    "confidence_score": 0.0,
                }
            )

    logger.info(f"Batch generated feedback for {len(feedbacks)} responses")
    return feedbacks
