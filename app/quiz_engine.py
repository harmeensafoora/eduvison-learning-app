"""
Quiz generation and assessment logic using Azure OpenAI.
Automatically generates quiz questions from educational content.
"""

import json
from typing import List, Dict
import uuid
from openai import AzureOpenAI, APIConnectionError

from .config import (
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_ENDPOINT,
    AZURE_OPENAI_API_VERSION,
    AZURE_OPENAI_DEPLOYMENT,
)
from .models import QuizQuestion, QuestionType, DifficultyLevel

def _get_client() -> AzureOpenAI | None:
    if not (AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_DEPLOYMENT):
        return None
    return AzureOpenAI(
        api_key=AZURE_OPENAI_API_KEY,
        api_version=AZURE_OPENAI_API_VERSION,
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
    )


def _extract_key_points(content: str, limit: int = 8) -> List[str]:
    """Pull short quiz-worthy statements from markdown bullets and sentences."""
    points: List[str] = []

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith(("### ", "## ", "# ")):
            continue
        if line.startswith(("- ", "* ")):
            candidate = line[2:].strip()
        else:
            candidate = line
        if candidate and candidate not in points:
            points.append(candidate)
        if len(points) >= limit:
            return points

    sentences = [segment.strip() for segment in content.replace("\n", " ").split(".") if segment.strip()]
    for sentence in sentences:
        if sentence and sentence not in points:
            points.append(sentence)
        if len(points) >= limit:
            break

    return points[:limit]


def _fallback_quiz_from_summary(
    topic_name: str,
    summary: str,
    difficulty: DifficultyLevel,
    num_questions: int,
) -> List[QuizQuestion]:
    """Return deterministic quiz questions when the LLM is unavailable."""
    points = _extract_key_points(summary, limit=max(num_questions, 4))
    if not points:
        points = [
            f"{topic_name} introduces foundational concepts that should be reviewed carefully.",
            f"Understanding the main mechanism in {topic_name} helps with later recall.",
            f"Key terminology from {topic_name} should be revised before assessment.",
            f"Examples from {topic_name} can be used to test applied understanding.",
        ]

    questions: List[QuizQuestion] = []
    for index in range(num_questions):
        point = points[index % len(points)]
        if index % 3 == 0:
            prompt = f"Which statement best matches this study point from {topic_name}?"
            correct = point
            distractors = [
                f"{topic_name} is mainly about unrelated peripheral details.",
                "The topic can be understood without reviewing any core concepts.",
                "Memorizing isolated terms is enough without understanding the idea.",
            ]
            questions.append(
                QuizQuestion(
                    id=f"fallback-{index + 1}",
                    question=prompt,
                    type=QuestionType.MULTIPLE_CHOICE,
                    difficulty=difficulty,
                    correct_answer=correct,
                    options=[correct, *distractors],
                    explanation=f"The source summary explicitly emphasizes: {point}",
                    related_topic=topic_name,
                    points=1,
                )
            )
        elif index % 3 == 1:
            questions.append(
                QuizQuestion(
                    id=f"fallback-{index + 1}",
                    question=f"True or False: {point}",
                    type=QuestionType.TRUE_FALSE,
                    difficulty=difficulty,
                    correct_answer="True",
                    options=["True", "False"],
                    explanation="This statement is drawn directly from the processed content.",
                    related_topic=topic_name,
                    points=1,
                )
            )
        else:
            lead = point.split(",")[0].split(" because ")[0].strip()
            questions.append(
                QuizQuestion(
                    id=f"fallback-{index + 1}",
                    question=f"In one short phrase, what key idea should you remember about: {lead}?",
                    type=QuestionType.SHORT_ANSWER,
                    difficulty=difficulty,
                    correct_answer=lead,
                    options=[],
                    explanation=f"A strong answer should mention this extracted idea: {point}",
                    related_topic=topic_name,
                    points=1,
                )
            )

    return questions[:num_questions]


def generate_quiz_from_content(
    topic_name: str,
    summary: str,
    detailed_text: str = "",
    difficulty: DifficultyLevel = DifficultyLevel.INTERMEDIATE,
    num_questions: int = 8,
) -> List[QuizQuestion]:
    """
    Generate quiz questions from educational content.
    Uses Azure OpenAI to intelligently create assessment questions.
    """

    content = f"{summary}\n\n{detailed_text}" if detailed_text else summary
    if len(content) > 8000:
        content = content[:8000]

    prompt = f"""You are an expert educational assessment designer. Generate {num_questions} quiz questions 
based on the provided educational material about "{topic_name}".

CRITICAL REQUIREMENTS:
- Generate EXACTLY {num_questions} questions in valid JSON format
- Vary question types: use multiple_choice, true_false, short_answer, fill_blank
- Difficulty level: {difficulty.value}
- Each question must have a clear, unambiguous correct answer
- Provide 4 options for multiple choice questions
- Each question must include an explanation

Return ONLY valid JSON (no markdown, no extra text) in this exact format:
{{
  "questions": [
    {{
      "id": "q1",
      "question": "Question text?",
      "type": "multiple_choice",
      "difficulty": "{difficulty.value}",
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "correct_answer": "Option A",
      "explanation": "Explanation of the correct answer",
      "points": 1
    }},
    {{
      "id": "q2",
      "question": "True or False: Statement here?",
      "type": "true_false",
      "difficulty": "{difficulty.value}",
      "options": ["True", "False"],
      "correct_answer": "True",
      "explanation": "Explanation",
      "points": 1
    }},
    {{
      "id": "q3",
      "question": "Short answer: What is _____?",
      "type": "short_answer",
      "difficulty": "{difficulty.value}",
      "options": [],
      "correct_answer": "expected answer",
      "explanation": "Why this is correct",
      "points": 2
    }},
    {{
      "id": "q4",
      "question": "Fill in the blank: The _____ is responsible for...",
      "type": "fill_blank",
      "difficulty": "{difficulty.value}",
      "options": [],
      "correct_answer": "correct_term",
      "explanation": "Explanation",
      "points": 1
    }}
  ]
}}

EDUCATIONAL MATERIAL:
{content}

Generate the questions now. Return ONLY the JSON object, nothing else."""

    client = _get_client()
    if client is None:
        return _fallback_quiz_from_summary(topic_name, summary, difficulty, num_questions)

    try:
        resp = client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=3000,
        )

        response_text = resp.choices[0].message.content.strip()

        # Extract JSON from response
        try:
            data = json.loads(response_text)
            questions = []

            for q_data in data.get("questions", []):
                question = QuizQuestion(
                    id=q_data.get("id", f"q{uuid.uuid4().hex[:8]}"),
                    question=q_data.get("question", ""),
                    type=QuestionType(q_data.get("type", "multiple_choice")),
                    difficulty=DifficultyLevel(q_data.get("difficulty", difficulty.value)),
                    correct_answer=q_data.get("correct_answer", ""),
                    options=q_data.get("options", []),
                    explanation=q_data.get("explanation", ""),
                    related_topic=topic_name,
                    points=q_data.get("points", 1),
                )
                questions.append(question)

            if questions:
                return questions[:num_questions]  # Ensure we don't exceed requested count
            return _fallback_quiz_from_summary(topic_name, summary, difficulty, num_questions)

        except json.JSONDecodeError as e:
            print(f"Failed to parse quiz JSON: {e}")
            print(f"Response: {response_text[:500]}")
            return _fallback_quiz_from_summary(topic_name, summary, difficulty, num_questions)

    except APIConnectionError as e:
        print(f"Azure OpenAI connection error in generate_quiz_from_content: {e}")
        return _fallback_quiz_from_summary(topic_name, summary, difficulty, num_questions)
    except Exception as e:
        print(f"Unexpected error in generate_quiz_from_content: {e}")
        return _fallback_quiz_from_summary(topic_name, summary, difficulty, num_questions)


def generate_knowledge_gap_assessment(
    topic_name: str,
    summary: str,
) -> List[QuizQuestion]:
    """
    Generate diagnostic assessment questions to identify knowledge gaps.
    These questions are designed to uncover misconceptions and weak areas.
    """

    if len(summary) > 6000:
        summary = summary[:6000]

    prompt = f"""You are a diagnostic assessment expert. Create 5 diagnostic questions to identify 
knowledge gaps and misconceptions about "{topic_name}".

These questions should:
- Target common misconceptions in this topic
- Reveal incomplete understanding
- Be at BEGINNER difficulty level
- Have plausible distractors that represent common mistakes

Return ONLY valid JSON (no markdown):
{{
  "questions": [
    {{
      "id": "d1",
      "question": "Which of the following is INCORRECT?",
      "type": "multiple_choice",
      "difficulty": "beginner",
      "options": ["Correct statement", "Common misconception", "Another misconception", "Another wrong answer"],
      "correct_answer": "Common misconception",
      "explanation": "The correct understanding is...",
      "points": 1
    }}
  ]
}}

TOPIC CONTENT:
{summary}

Generate now. Return ONLY JSON."""

    client = _get_client()
    if client is None:
        return []

    try:
        resp = client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=1500,
        )

        response_text = resp.choices[0].message.content.strip()
        data = json.loads(response_text)
        questions = []

        for q_data in data.get("questions", []):
            question = QuizQuestion(
                id=q_data.get("id", f"d{uuid.uuid4().hex[:8]}"),
                question=q_data.get("question", ""),
                type=QuestionType(q_data.get("type", "multiple_choice")),
                difficulty=DifficultyLevel.BEGINNER,
                correct_answer=q_data.get("correct_answer", ""),
                options=q_data.get("options", []),
                explanation=q_data.get("explanation", ""),
                related_topic=topic_name,
                points=1,
            )
            questions.append(question)

        return questions

    except Exception as e:
        print(f"Error in generate_knowledge_gap_assessment: {e}")
        return []


def evaluate_answer(
    question: QuizQuestion,
    user_answer: str,
    is_multiple_choice: bool = True,
) -> Dict:
    """
    Evaluate a user's answer (with AI assistance for short answers).
    Returns score and feedback.
    """

    if question.type == QuestionType.MULTIPLE_CHOICE or question.type == QuestionType.TRUE_FALSE:
        is_correct = user_answer.strip().lower() == question.correct_answer.strip().lower()
        score = question.points if is_correct else 0

        return {
            "is_correct": is_correct,
            "score": score,
            "explanation": question.explanation,
            "correct_answer": question.correct_answer,
        }

    elif question.type in [QuestionType.SHORT_ANSWER, QuestionType.FILL_BLANK]:
        # Use AI for fuzzy matching on short answers
        if not AZURE_OPENAI_API_KEY or not AZURE_OPENAI_ENDPOINT:
            # Fallback: exact match
            is_correct = user_answer.strip().lower() == question.correct_answer.strip().lower()
            score = question.points if is_correct else 0
            return {
                "is_correct": is_correct,
                "score": score,
                "explanation": question.explanation,
                "correct_answer": question.correct_answer,
            }

        prompt = f"""Evaluate if the student's answer is correct for this question.

Question: {question.question}
Expected Answer: {question.correct_answer}
Student's Answer: {user_answer}

Consider:
- Exact matches (100% correct)
- Paraphrasing (75% credit)
- Partially correct (50% credit)
- Incorrect (0% credit)

Return ONLY JSON:
{{
  "is_correct": true/false,
  "score_percentage": 0-100,
  "feedback": "Brief feedback"
}}"""

        try:
            eval_client = _get_client()
            if eval_client is None:
                raise Exception("Azure OpenAI not configured")
            resp = eval_client.chat.completions.create(
                model=AZURE_OPENAI_DEPLOYMENT,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=300,
            )

            response_text = resp.choices[0].message.content.strip()
            data = json.loads(response_text)

            score = int(question.points * (data.get("score_percentage", 0) / 100))

            return {
                "is_correct": data.get("is_correct", False),
                "score": score,
                "explanation": question.explanation,
                "correct_answer": question.correct_answer,
                "feedback": data.get("feedback", ""),
            }

        except Exception as e:
            print(f"Error evaluating short answer: {e}")
            # Fallback
            is_correct = user_answer.strip().lower() == question.correct_answer.strip().lower()
            score = question.points if is_correct else 0
            return {
                "is_correct": is_correct,
                "score": score,
                "explanation": question.explanation,
                "correct_answer": question.correct_answer,
            }

    return {
        "is_correct": False,
        "score": 0,
        "explanation": question.explanation,
        "correct_answer": question.correct_answer,
    }
