"""
Enhanced data models for learning tracking, progress, and assessments.
Provides comprehensive learning session and learner data structures.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime
import json
from enum import Enum


class DifficultyLevel(str, Enum):
    """Difficulty levels for assessment and content."""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class QuestionType(str, Enum):
    """Types of quiz questions."""
    MULTIPLE_CHOICE = "multiple_choice"
    SHORT_ANSWER = "short_answer"
    TRUE_FALSE = "true_false"
    FILL_BLANK = "fill_blank"


@dataclass
class QuizQuestion:
    """Represents a single quiz question."""
    id: str
    question: str
    type: QuestionType
    difficulty: DifficultyLevel
    correct_answer: str
    options: List[str] = field(default_factory=list)  # For multiple choice
    explanation: str = ""
    related_topic: str = ""
    points: int = 1

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "question": self.question,
            "type": self.type.value,
            "difficulty": self.difficulty.value,
            "options": self.options,
            "explanation": self.explanation,
            "related_topic": self.related_topic,
            "points": self.points,
        }


@dataclass
class QuizAttempt:
    """Represents a user's attempt at a quiz."""
    quiz_id: str
    timestamp: datetime
    answers: Dict[str, str]  # question_id -> user_answer
    score: float  # Percentage
    time_taken: int  # In seconds
    topics_covered: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "quiz_id": self.quiz_id,
            "timestamp": self.timestamp.isoformat(),
            "score": self.score,
            "time_taken": self.time_taken,
            "topics_covered": self.topics_covered,
        }


@dataclass
class Topic:
    """Represents a learning topic."""
    id: str
    name: str
    summary: str
    details: str = ""
    prerequisites: List[str] = field(default_factory=list)
    related_topics: List[str] = field(default_factory=list)
    learning_objectives: List[str] = field(default_factory=list)
    difficulty: DifficultyLevel = DifficultyLevel.INTERMEDIATE
    estimated_time_minutes: int = 30
    keywords: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "summary": self.summary,
            "details": self.details,
            "prerequisites": self.prerequisites,
            "related_topics": self.related_topics,
            "learning_objectives": self.learning_objectives,
            "difficulty": self.difficulty.value,
            "estimated_time_minutes": self.estimated_time_minutes,
            "keywords": self.keywords,
        }


@dataclass
class TopicProgress:
    """Tracks learner progress on a specific topic."""
    topic_id: str
    first_viewed: datetime
    last_viewed: datetime
    times_viewed: int = 1
    completion_percentage: float = 0.0
    quiz_attempts: List[QuizAttempt] = field(default_factory=list)
    best_quiz_score: float = 0.0
    notes: str = ""
    bookmarks: List[Dict] = field(default_factory=list)  # {position, text, timestamp}
    time_spent_minutes: int = 0

    def get_mastery_level(self) -> str:
        """Determine mastery level based on quiz scores."""
        if not self.quiz_attempts:
            return "not_attempted"
        if self.best_quiz_score >= 90:
            return "mastered"
        elif self.best_quiz_score >= 75:
            return "proficient"
        elif self.best_quiz_score >= 60:
            return "developing"
        else:
            return "beginning"

    def to_dict(self) -> Dict:
        return {
            "topic_id": self.topic_id,
            "first_viewed": self.first_viewed.isoformat(),
            "last_viewed": self.last_viewed.isoformat(),
            "times_viewed": self.times_viewed,
            "completion_percentage": self.completion_percentage,
            "best_quiz_score": self.best_quiz_score,
            "mastery_level": self.get_mastery_level(),
            "time_spent_minutes": self.time_spent_minutes,
            "notes_preview": self.notes[:100] if self.notes else "",
            "bookmarks_count": len(self.bookmarks),
        }


@dataclass
class LearnerProfile:
    """Complete learner profile and progress tracking."""
    session_id: str
    created_at: datetime
    topics: Dict[str, Topic] = field(default_factory=dict)
    topic_progress: Dict[str, TopicProgress] = field(default_factory=dict)
    quizzes: Dict[str, List[QuizQuestion]] = field(default_factory=dict)  # topic_id -> questions
    learning_preferences: Dict = field(default_factory=dict)
    total_time_spent_minutes: int = 0
    overall_completion_percentage: float = 0.0

    def add_topic(self, topic: Topic) -> None:
        """Add a new topic."""
        self.topics[topic.id] = topic
        self.topic_progress[topic.id] = TopicProgress(
            topic_id=topic.id,
            first_viewed=datetime.now(),
            last_viewed=datetime.now(),
        )

    def get_next_review_topics(self) -> List[str]:
        """Get list of topics needing spaced repetition review."""
        from datetime import timedelta
        review_topics = []
        now = datetime.now()

        for topic_id, progress in self.topic_progress.items():
            days_since_last_view = (now - progress.last_viewed).days
            
            # Spaced repetition schedule: review after 1, 3, 7, 14, 30 days
            review_schedule = [1, 3, 7, 14, 30]
            should_review = days_since_last_view in review_schedule
            
            if should_review and progress.best_quiz_score < 90:
                review_topics.append(topic_id)

        return review_topics

    def calculate_overall_progress(self) -> None:
        """Calculate overall completion percentage."""
        if not self.topics:
            self.overall_completion_percentage = 0.0
            return

        total = 0
        for topic_id in self.topics:
            if topic_id in self.topic_progress:
                total += self.topic_progress[topic_id].completion_percentage

        self.overall_completion_percentage = total / len(self.topics)

    def get_dashboard_stats(self) -> Dict:
        """Get dashboard statistics."""
        attempts = [
            attempt
            for progress in self.topic_progress.values()
            for attempt in progress.quiz_attempts
        ]
        total_quizzes = len(attempts)
        avg_quiz_score = (
            sum(attempt.score for attempt in attempts) / total_quizzes
            if total_quizzes > 0 else 0
        )

        topics_with_quizzes = sum(
            1 for progress in self.topic_progress.values()
            if progress.quiz_attempts
        )

        return {
            "total_topics": len(self.topics),
            "topics_started": sum(1 for p in self.topic_progress.values() if p.times_viewed > 0),
            "topics_mastered": sum(1 for p in self.topic_progress.values() if p.get_mastery_level() == "mastered"),
            "total_quizzes_taken": total_quizzes,
            "topics_with_quizzes": topics_with_quizzes,
            "average_quiz_score": round(avg_quiz_score, 2),
            "total_time_spent_minutes": self.total_time_spent_minutes,
            "overall_completion_percentage": round(self.overall_completion_percentage, 2),
            "topics_needing_review": len(self.get_next_review_topics()),
        }
