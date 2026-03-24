from typing import Dict, List


def summarize_engagement(events: List[Dict]) -> Dict:
    """Return simple engagement counters from tracked events."""
    event_types = {}
    for event in events:
        key = event.get("type", "unknown")
        event_types[key] = event_types.get(key, 0) + 1

    return {
        "total_events": len(events),
        "by_type": event_types,
    }
