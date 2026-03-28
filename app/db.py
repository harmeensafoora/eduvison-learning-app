import json
import os
import sqlite3
from datetime import datetime
from typing import Any


BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "eduvision.sqlite")


def _now_iso() -> str:
    return datetime.now().isoformat()


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create the minimal schema needed for preference tracking."""
    with _get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_profile (
                user_id TEXT PRIMARY KEY,
                learning_style TEXT,
                preferred_chunk_size TEXT,
                optimal_study_duration INTEGER,
                visual_vs_text_preference REAL,
                mastery_speed REAL,
                retention_curve TEXT,
                detail_mode_preference TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )


def get_user_profile(user_id: str) -> dict[str, Any] | None:
    init_db()
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM user_profile WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if not row:
            return None
        return dict(row)


def upsert_user_profile(user_id: str, **fields: Any) -> None:
    """
    Upsert a user profile keyed by `user_id`.

    Note: since the app currently has no auth, we use the current
    `session_id` as a stand-in for `user_id` (good enough for Phase 1).
    """
    init_db()

    allowed = {
        "learning_style",
        "preferred_chunk_size",
        "optimal_study_duration",
        "visual_vs_text_preference",
        "mastery_speed",
        "retention_curve",
        "detail_mode_preference",
    }

    filtered: dict[str, Any] = {k: v for k, v in fields.items() if k in allowed}

    # Normalize json-ish fields.
    if "retention_curve" in filtered and filtered["retention_curve"] is not None:
        if not isinstance(filtered["retention_curve"], str):
            filtered["retention_curve"] = json.dumps(filtered["retention_curve"])

    now = _now_iso()

    keys = list(filtered.keys())
    insert_cols = ["user_id"] + keys + ["created_at", "updated_at"]
    placeholders = ", ".join(["?"] * len(insert_cols))
    insert_cols_sql = ", ".join(insert_cols)

    insert_values = [user_id] + [filtered[k] for k in keys] + [now, now]

    # Update only provided keys; always refresh updated_at.
    set_clauses = [f"{k} = excluded.{k}" for k in keys]
    set_clauses.append("updated_at = excluded.updated_at")
    set_sql = ", ".join(set_clauses) if set_clauses else "updated_at = excluded.updated_at"

    with _get_conn() as conn:
        conn.execute(
            f"""
            INSERT INTO user_profile ({insert_cols_sql})
            VALUES ({placeholders})
            ON CONFLICT(user_id) DO UPDATE SET
            {set_sql}
            """,
            insert_values,
        )

