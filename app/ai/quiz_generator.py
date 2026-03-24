from ..models import DifficultyLevel
from ..quiz_engine import generate_quiz_from_content


def create_quiz(topic_name: str, summary: str, detailed_text: str, difficulty: str, question_count: int = 8):
    """Generate quiz questions through the existing quiz engine."""
    try:
        difficulty_level = DifficultyLevel(difficulty)
    except ValueError:
        difficulty_level = DifficultyLevel.INTERMEDIATE

    return generate_quiz_from_content(
        topic_name=topic_name,
        summary=summary,
        detailed_text=detailed_text,
        difficulty=difficulty_level,
        num_questions=question_count,
    )
