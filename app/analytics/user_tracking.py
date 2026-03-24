from datetime import datetime
from typing import Dict, List


EVENT_LOG: List[Dict] = []


def track_event(event: Dict) -> Dict:
    """Store a lightweight analytics event in memory."""
    payload = dict(event)
    payload.setdefault("timestamp", datetime.now().isoformat())
    EVENT_LOG.append(payload)
    return {"status": "tracked", "count": len(EVENT_LOG)}
