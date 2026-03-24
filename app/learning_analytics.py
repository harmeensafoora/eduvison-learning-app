"""
Learning analytics and adaptive recommendations engine.
Provides spaced repetition scheduling, mastery analysis, and personalized learning paths.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Tuple
from .models import TopicProgress, LearnerProfile, DifficultyLevel


class LearningAnalytics:
    """Analyzes learner progress and provides adaptive recommendations."""

    @staticmethod
    def calculate_retention_score(progress: TopicProgress) -> float:
        """
        Calculate knowledge retention score (0-100).
        Based on quiz performance, review frequency, and time decay.
        """
        if not progress.quiz_attempts:
            return 0.0

        recent_attempts = progress.quiz_attempts[-3:]
        base_score = (
            sum(attempt.score for attempt in recent_attempts) / len(recent_attempts)
            if recent_attempts else progress.best_quiz_score
        )

        # Bonus for frequent reviews (up to 10%)
        review_bonus = min(progress.times_viewed * 2, 10)

        # Time decay: deduct points for each week since last review
        days_since_review = (datetime.now() - progress.last_viewed).days
        time_penalty = min(days_since_review * 2.5, 35)

        retention = base_score + review_bonus - time_penalty
        return max(0, min(100, retention))

    @staticmethod
    def get_spaced_repetition_schedule(progress: TopicProgress) -> Dict:
        """
        Get optimal spaced repetition schedule using Ebbinghaus spacing.
        Returns when to review next based on current mastery level.
        """
        mastery = progress.get_mastery_level()
        days_since_view = (datetime.now() - progress.last_viewed).days

        # Classic spaced repetition intervals (in days)
        schedules = {
            "not_attempted": {
                "next_review": 1,
                "status": "Not started - Review immediately",
            },
            "beginning": {
                "next_review": 1,
                "status": "Struggling - Daily review recommended",
            },
            "developing": {
                "next_review": 3,
                "status": "Making progress - Review in 3 days",
            },
            "proficient": {
                "next_review": 7,
                "status": "Good understanding - Review in 1 week",
            },
            "mastered": {
                "next_review": 30,
                "status": "Mastered - Review in 1 month",
            },
        }

        schedule = schedules.get(mastery, schedules["developing"])
        next_review_date = progress.last_viewed + timedelta(days=schedule["next_review"])
        is_overdue = next_review_date <= datetime.now()

        return {
            "mastery_level": mastery,
            "days_since_last_view": days_since_view,
            "next_review_days": schedule["next_review"],
            "next_review_date": next_review_date.isoformat(),
            "is_overdue": is_overdue,
            "recommendation": schedule["status"],
        }

    @staticmethod
    def get_difficulty_recommendation(progress: TopicProgress, attempt_count: int = 0) -> DifficultyLevel:
        """
        Recommend difficulty level for next quiz based on performance.
        """
        if not progress.quiz_attempts:
            return DifficultyLevel.BEGINNER

        avg_score = sum(a.score for a in progress.quiz_attempts) / len(progress.quiz_attempts)

        if avg_score >= 85:
            return DifficultyLevel.ADVANCED
        elif avg_score >= 70:
            return DifficultyLevel.INTERMEDIATE
        else:
            return DifficultyLevel.BEGINNER

    @staticmethod
    def identify_weak_areas(profile: LearnerProfile) -> List[Dict]:
        """
        Identify topics where learner is struggling.
        Returns list of weak areas with recommendations.
        """
        weak_areas = []

        for topic_id, progress in profile.topic_progress.items():
            if progress.best_quiz_score < 70 and progress.quiz_attempts:
                topic = profile.topics.get(topic_id)
                weak_areas.append(
                    {
                        "topic_id": topic_id,
                        "topic_name": topic.name if topic else topic_id,
                        "current_score": progress.best_quiz_score,
                        "attempts": len(progress.quiz_attempts),
                        "recommendation": "Review prerequisites and fundamentals",
                        "suggested_difficulty": "beginner",
                    }
                )

        return sorted(weak_areas, key=lambda x: x["current_score"])

    @staticmethod
    def get_learning_velocity(profile: LearnerProfile) -> Dict:
        """
        Calculate learner's learning velocity (progress per unit time).
        """
        active_days = max((datetime.now() - profile.created_at).days + 1, 1)
        total_attempts = sum(
            len(progress.quiz_attempts) for progress in profile.topic_progress.values()
        )

        if profile.overall_completion_percentage == 0 and total_attempts == 0:
            return {
                "velocity": 0,
                "pace": "Just started",
                "projected_completion_days": None,
                "projected_completion": "Complete a quiz or open more learning views to build analytics.",
                "active_days": active_days,
                "quizzes_per_day": 0,
            }

        velocity = profile.overall_completion_percentage / active_days
        remaining_percentage = 100 - profile.overall_completion_percentage

        if velocity > 0:
            days_remaining = remaining_percentage / velocity
        else:
            days_remaining = None

        if velocity >= 25:
            pace = "Fast learner"
        elif velocity >= 10:
            pace = "Moderate pace"
        else:
            pace = "Steady pace"

        projected_completion = (
            f"At this pace, full completion is about {max(1, int(round(days_remaining)))} day(s) away."
            if days_remaining is not None else
            "Not enough progress data for a projection yet."
        )

        return {
            "velocity": round(velocity, 3),
            "percentage_per_day": round(velocity, 2),
            "pace": pace,
            "projected_completion_days": int(round(days_remaining)) if days_remaining is not None else None,
            "projected_completion": projected_completion,
            "active_days": active_days,
            "quizzes_per_day": round(total_attempts / active_days, 2),
        }

    @staticmethod
    def get_learning_path(profile: LearnerProfile) -> List[Dict]:
        """
        Generate personalized learning path based on prerequisites and progress.
        """
        path = []

        # Topics not started, with prerequisites met
        for topic_id, topic in profile.topics.items():
            progress = profile.topic_progress.get(topic_id)

            if not progress or progress.times_viewed == 0:
                # Check if prerequisites are met
                prerequisites_met = all(
                    profile.topic_progress.get(prereq_id)
                    and profile.topic_progress[prereq_id].best_quiz_score >= 70
                    for prereq_id in topic.prerequisites
                )

                path.append(
                    {
                        "topic_id": topic_id,
                        "topic_name": topic.name,
                        "status": "Ready to start" if prerequisites_met else "Blocked - prerequisites needed",
                        "prerequisites_met": prerequisites_met,
                        "estimated_time_minutes": topic.estimated_time_minutes,
                        "reason": (
                            f"Recommended next topic" if prerequisites_met
                            else f"Complete {', '.join(topic.prerequisites)} first"
                        ),
                    }
                )

        return path

    @staticmethod
    def get_study_recommendations(profile: LearnerProfile) -> List[Dict]:
        """
        Generate personalized study recommendations.
        """
        recommendations = []

        # Spaced repetition reviews
        review_topics = profile.get_next_review_topics()
        if review_topics:
            recommendations.append(
                {
                    "type": "spaced_repetition",
                    "priority": "high",
                    "title": "Time for Spaced Repetition Review",
                    "description": f"You have {len(review_topics)} topic(s) due for review",
                    "topics": review_topics,
                    "action": "Review these topics to maximize retention",
                }
            )

        # Weak areas
        weak = LearningAnalytics.identify_weak_areas(profile)
        if weak:
            recommendations.append(
                {
                    "type": "remedial",
                    "priority": "high",
                    "title": "Strengthen Weak Areas",
                    "description": f"You're struggling with {len(weak)} topic(s)",
                    "weak_topics": [w["topic_name"] for w in weak],
                    "action": "Practice these topics with beginner difficulty",
                }
            )

        # Learning velocity insights
        velocity = LearningAnalytics.get_learning_velocity(profile)
        if velocity["pace"] == "Steady pace":
            recommendations.append(
                {
                    "type": "pacing",
                    "priority": "medium",
                    "title": "Increase Consistency",
                    "description": velocity["projected_completion"],
                    "action": "Add one extra focused study block or quiz attempt this week",
                }
            )

        # Practice recommendations
        topics_with_low_attempts = [
            t_id for t_id, prog in profile.topic_progress.items()
            if len(prog.quiz_attempts) < 2
        ]
        if topics_with_low_attempts:
            recommendations.append(
                {
                    "type": "practice",
                    "priority": "medium",
                    "title": "More Practice Needed",
                    "description": f"{len(topics_with_low_attempts)} topic(s) need more practice",
                    "action": "Take additional quizzes to reinforce learning",
                }
            )

        return recommendations

    @staticmethod
    def estimate_mastery_probability(
        current_score: float,
        num_attempts: int,
        days_since_last_review: int,
    ) -> float:
        """
        Estimate probability of achieving mastery (90%+) with continued practice.
        """
        # Based on learning curve theory
        base_probability = min(current_score / 90, 1.0)  # If already at 90, prob = 1.0
        attempt_bonus = min(num_attempts * 0.05, 0.2)  # Each attempt adds up to 20%
        recency_factor = max(1.0 - (days_since_last_review * 0.02), 0.5)  # Recent reviews boost

        probability = (base_probability + attempt_bonus) * recency_factor
        return round(max(0, min(1, probability)), 2)

    @staticmethod
    def generate_study_plan(profile: LearnerProfile, weeks: int = 4) -> Dict:
        """
        Generate a structured study plan for the next N weeks.
        """
        daily_goal_minutes = 30
        total_minutes = daily_goal_minutes * 7 * weeks
        review_topics = profile.get_next_review_topics()
        upcoming_topics = [
            t_id for t_id, prog in profile.topic_progress.items()
            if prog.times_viewed == 0
        ][:5]

        weekly_plan = []
        for week in range(1, weeks + 1):
            if week == 1 and review_topics:
                focus = "Revisit weak areas and complete one quiz retry."
            elif week == 1:
                focus = "Consolidate the core topic summary and one practice quiz."
            elif week == 2:
                focus = "Deepen understanding with details, visuals, and medium-difficulty quiz work."
            elif week == 3:
                focus = "Strengthen weak spots and review spaced-repetition topics."
            else:
                focus = "Assess mastery, revisit mistakes, and move to an advanced follow-up topic."
            weekly_plan.append({"week": week, "focus": focus})

        return {
            "duration_weeks": weeks,
            "daily_goal_minutes": daily_goal_minutes,
            "total_minutes": total_minutes,
            "topics_for_review": len(review_topics),
            "new_topics_available": len(upcoming_topics),
            "weekly_plan": weekly_plan,
            "recommended_schedule": {
                "review_days": ["Monday", "Wednesday", "Friday"],
                "practice_days": ["Tuesday", "Thursday"],
                "assessment_days": ["Saturday"],
                "rest_day": "Sunday",
            },
            "success_metrics": {
                "target_average_score": 85,
                "completion_percentage_target": 100,
                "weekly_progress_target": 25,
            },
        }
