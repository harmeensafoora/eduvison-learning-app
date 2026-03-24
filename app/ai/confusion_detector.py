from typing import Dict, List


def detect_confusion_points(concepts: List[Dict]) -> List[Dict]:
    """Flag concepts that look dense enough to need extra explanation."""
    confusion_points: List[Dict] = []

    for concept in concepts:
        bullets = concept.get("bullets", [])
        if len(bullets) >= 3 or any(len(item.split()) > 12 for item in bullets):
            confusion_points.append(
                {
                    "concept": concept["name"],
                    "reason": "Dense concept cluster detected from the source summary.",
                    "tip": "Review the details tab and quiz this concept after the summary pass.",
                }
            )

    return confusion_points[:3]
