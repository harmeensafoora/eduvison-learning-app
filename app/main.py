import json
import os
import uuid
import secrets
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Any

import httpx
from fastapi import FastAPI, UploadFile, File, Form, Depends, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from .ai_utils import summarize_text, detailed_summary_text
from .auth_utils import create_access_token, create_refresh_token, decode_token, utcnow, hash_value, verify_hash
from .config import (
    BASE_UPLOAD_DIR,
    FRONTEND_ORIGIN,
    COOKIE_SECURE,
    SESSION_COOKIE_NAME,
    REFRESH_COOKIE_NAME,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
    APP_PUBLIC_URL,
    GOOGLE_CLIENT_ID,
)
from .database import get_db, init_db
from .db_models import (
    User,
    UserProfile,
    LearningSession,
    Concept,
    LearningEvent,
    QuizAttempt,
    TopicProgress,
    RefreshToken,
    EmailToken,
)
from .pdf_utils import save_upload, extract_text, extract_images
from .quiz_engine import generate_quiz_from_content, evaluate_answer, generate_check_questions_from_summary
from .visual_query import generate_visual_search_payload
from .image_search import fetch_first_image
from .schemas import (
    GoogleAuthRequest,
    EmailSignupRequest,
    EmailLoginRequest,
    RequestResetRequest,
    ResetPasswordRequest,
    ChangePasswordRequest,
    TranslateRequest,
    TrackEventRequest,
    InferProfileRequest,
    GenerateQuizRequest,
    SubmitQuizRequest,
    NextStepsRequest,
    CognitiveStatusRequest,
    VisualQueryRequest,
)

app = FastAPI(title="EduVision - Adaptive Learning Platform")

allow_origins = ["*"] if FRONTEND_ORIGIN == "*" else [FRONTEND_ORIGIN]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "static"))
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/files", StaticFiles(directory=BASE_UPLOAD_DIR), name="files")


@app.on_event("startup")
async def on_startup():
    await init_db()


def set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE_NAME,
        access_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        refresh_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
        path="/",
    )


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    response.delete_cookie(REFRESH_COOKIE_NAME, path="/")


async def get_current_user_optional(request: Request, db: AsyncSession) -> User | None:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    return await db.get(User, user_id)


async def get_current_user_required(request: Request, db: AsyncSession) -> User:
    user = await get_current_user_optional(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


async def get_current_user_verified_required(request: Request, db: AsyncSession) -> User:
    user = await get_current_user_required(request, db)
    if not user.email_verified_at:
        raise HTTPException(status_code=403, detail="Email not verified")
    return user


async def ensure_profile(db: AsyncSession, user_id: str) -> UserProfile:
    stmt = select(UserProfile).where(UserProfile.user_id == user_id)
    profile = (await db.execute(stmt)).scalar_one_or_none()
    if profile:
        return profile
    profile = UserProfile(user_id=user_id)
    db.add(profile)
    await db.flush()
    return profile


def to_original_url(path: str) -> str:
    rel = os.path.relpath(path, BASE_UPLOAD_DIR).replace("\\", "/")
    return f"/files/{rel}"


async def _redirect_if_anon(path: str, request: Request, db: AsyncSession) -> RedirectResponse | None:
    user = await get_current_user_optional(request, db)
    if user:
        return None
    return RedirectResponse(url=f"/login?next={path}", status_code=302)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _validate_password(password: str) -> None:
    if not password or len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    if len(password) > 128 or len(password.encode("utf-8")) > 256:
        raise HTTPException(status_code=400, detail="Password is too long")


async def _issue_refresh_token(db: AsyncSession, user_id: str, refresh: str) -> None:
    db.add(
        RefreshToken(
            user_id=user_id,
            token=refresh,
            expires_at=(utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)).replace(tzinfo=None),
        )
    )


async def _revoke_refresh_tokens(db: AsyncSession, user_id: str) -> None:
    rows = list((await db.execute(select(RefreshToken).where(RefreshToken.user_id == user_id))).scalars().all())
    for row in rows:
        row.revoked_at = datetime.utcnow()


async def _create_email_token(
    db: AsyncSession,
    user: User,
    purpose: str,
    expires_in: timedelta,
) -> str:
    raw = secrets.token_urlsafe(32)
    row = EmailToken(
        user_id=user.id,
        email=(user.email or "").lower(),
        purpose=purpose,
        token_hash=_hash_token(raw),
        expires_at=(utcnow() + expires_in).replace(tzinfo=None),
    )
    db.add(row)
    return raw


def extract_concepts_from_summary(summary: str) -> list[dict[str, Any]]:
    concepts: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for raw in summary.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("### "):
            title = line[4:].strip()
            current = {
                "id": str(uuid.uuid4()),
                "name": title,
                "summary": "",
                "bullets": [],
                "type": "core",
                "importance": 1,
            }
            concepts.append(current)
            continue
        if current and line.startswith(("- ", "* ")):
            current["bullets"].append(line[2:].strip())

    if not concepts:
        lines = [ln.strip("-*# ").strip() for ln in summary.splitlines() if ln.strip()][:6]
        for idx, line in enumerate(lines):
            concepts.append(
                {
                    "id": str(uuid.uuid4()),
                    "name": line[:80] or f"Concept {idx+1}",
                    "summary": line,
                    "bullets": [line],
                    "type": "core",
                    "importance": max(1, 5 - idx),
                }
            )

    for idx, concept in enumerate(concepts):
        bullets = concept.get("bullets", [])
        concept["summary"] = bullets[0] if bullets else f"Key idea from {concept['name']}"
        concept["type"] = "foundation" if idx == 0 else ("bridge" if idx < 3 else "detail")
        concept["importance"] = min(5, max(1, len(bullets) if bullets else 2))

    return concepts[:12]


def estimate_study_time_minutes(text: str, concepts: list[dict[str, Any]]) -> int:
    word_count = len(text.split())
    baseline = max(8, word_count // 180)
    return min(120, baseline + len(concepts) * 4)


async def maybe_infer_profile(db: AsyncSession, user_id: str) -> UserProfile:
    profile = await ensure_profile(db, user_id)

    events_stmt = (
        select(LearningEvent)
        .where(LearningEvent.user_id == user_id)
        .order_by(LearningEvent.created_at.desc())
        .limit(30)
    )
    events = list((await db.execute(events_stmt)).scalars().all())
    if len(events) < 3:
        return profile

    modality_time: dict[str, float] = {}
    for e in events:
        modality = (e.payload or {}).get("modality")
        time_ms = float((e.payload or {}).get("time_on_chunk_ms", 0))
        if modality:
            modality_time[modality] = modality_time.get(modality, 0) + max(0.0, time_ms)

    if modality_time:
        profile.preferred_modality = max(modality_time.items(), key=lambda kv: kv[1])[0]

    attempts = list(
        (
            await db.execute(
                select(QuizAttempt)
                .where(QuizAttempt.user_id == user_id)
                .order_by(QuizAttempt.created_at.desc())
                .limit(30)
            )
        ).scalars().all()
    )

    if attempts:
        avg_score = sum(a.score for a in attempts) / len(attempts)
        if avg_score > 80:
            profile.difficulty_preference = "hard"
        elif avg_score < 50:
            profile.difficulty_preference = "easy"
        else:
            profile.difficulty_preference = "auto"

    completed_stmt = select(func.count(TopicProgress.id)).where(
        and_(TopicProgress.user_id == user_id, TopicProgress.status == "mastered")
    )
    completed = int((await db.execute(completed_stmt)).scalar() or 0)
    expected_minutes = max(1.0, completed * 6.0)

    total_time_ms = 0.0
    for e in events:
        total_time_ms += float((e.payload or {}).get("time_on_chunk_ms", 0))
    actual_minutes = max(0.1, total_time_ms / 60000.0)
    profile.learning_velocity = max(0.3, min(2.5, expected_minutes / max(0.1, actual_minutes)))

    text_events = [e for e in events if (e.payload or {}).get("modality") == "text"]
    visual_events = [e for e in events if (e.payload or {}).get("modality") == "visual"]
    text_time = sum(float((e.payload or {}).get("time_on_chunk_ms", 0)) for e in text_events)
    visual_time = sum(float((e.payload or {}).get("time_on_chunk_ms", 0)) for e in visual_events)

    if text_time > visual_time * 1.5:
        profile.cognitive_style = "visual"
    elif profile.preferred_modality == "practice":
        profile.cognitive_style = "kinesthetic"
    else:
        profile.cognitive_style = "conceptual"

    profile.last_active_at = datetime.utcnow()
    return profile


def compute_next_difficulty(current: str, score: int) -> str:
    if current == "medium" and score >= 80:
        return "hard"
    if current == "medium" and score < 50:
        return "easy"
    if current == "hard" and score >= 80:
        return "hard"
    if current == "easy" and score < 50:
        return "easy"
    return "medium"


async def compute_next_steps_for_session(db: AsyncSession, user: User, session_id: str) -> dict[str, Any]:
    progress = list(
        (
            await db.execute(
                select(TopicProgress, Concept)
                .join(Concept, Concept.id == TopicProgress.concept_id)
                .where(and_(TopicProgress.user_id == user.id, TopicProgress.session_id == session_id))
                .order_by(Concept.order_index.asc())
            )
        ).all()
    )

    if not progress:
        return {"primary_action": "Upload a PDF to begin", "secondary_actions": [], "estimated_minutes_remaining": 0, "session_id": session_id}

    weak = [row for row in progress if row[0].score < 50 and row[0].attempt_count >= 2]
    unlocked = [row for row in progress if row[0].status == "unlocked"]
    remaining = [row for row in progress if row[0].status != "mastered"]

    if weak:
        primary = f"Revisit {weak[0][1].name} - you're close"
    elif unlocked:
        primary = f"Continue to {unlocked[0][1].name}"
    elif remaining:
        primary = "Strengthen weak areas before finishing"
    else:
        avg_mastery = sum(r[0].score for r in progress) / max(1, len(progress))
        primary = "You've mastered this document. Want a final test?" if avg_mastery >= 80 else "Strengthen weak areas before finishing"

    profile = await ensure_profile(db, user.id)
    velocity = max(0.4, profile.learning_velocity or 1.0)
    estimated = int(sum((r[1].estimated_minutes or 5.0) for r in remaining) / velocity)
    secondary = [f"Review {r[1].name}" for r in remaining[:3]]

    return {
        "primary_action": primary,
        "secondary_actions": secondary,
        "estimated_minutes_remaining": max(0, estimated),
        "session_id": session_id,
    }


@app.post("/auth/signup")
async def auth_signup(payload: EmailSignupRequest, response: Response, db: AsyncSession = Depends(get_db)):
    email = payload.email.lower()
    _validate_password(payload.password)

    existing = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if existing:
        if existing.auth_provider == "google" and not existing.hashed_password:
            raise HTTPException(status_code=400, detail="This email uses Google sign-in")
        raise HTTPException(status_code=400, detail="Account already exists. Please sign in.")

    user = User(email=email, display_name=payload.display_name or email.split("@")[0], auth_provider="email")
    user.hashed_password = hash_value(payload.password)
    user.email_verified_at = None
    db.add(user)
    await db.flush()

    profile = await ensure_profile(db, user.id)

    verify_token = await _create_email_token(db, user, "verify_email", timedelta(hours=24))
    verify_url = f"{APP_PUBLIC_URL}/auth/verify-email?token={verify_token}"

    access = create_access_token(user.id, user.email or "")
    refresh = create_refresh_token(user.id)
    await _issue_refresh_token(db, user.id, refresh)
    set_auth_cookies(response, access, refresh)

    return {
        "user": {"id": user.id, "email": user.email, "display_name": user.display_name, "avatar_url": user.avatar_url},
        "profile": {
            "preferred_modality": profile.preferred_modality,
            "learning_velocity": profile.learning_velocity,
            "cognitive_style": profile.cognitive_style,
            "difficulty_preference": profile.difficulty_preference,
        },
        "verified": False,
        "verify_url": verify_url,
    }


@app.post("/auth/login")
async def auth_login(payload: EmailLoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    email = payload.email.lower()
    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid email or password")
    if not user.hashed_password:
        if user.auth_provider == "google":
            raise HTTPException(status_code=400, detail="This email uses Google sign-in")
        raise HTTPException(
            status_code=400,
            detail="No password set for this account. Use password reset to set one.",
        )
    if not verify_hash(payload.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Invalid email or password")

    user.last_login_at = datetime.utcnow()
    profile = await ensure_profile(db, user.id)

    access = create_access_token(user.id, user.email or "")
    refresh = create_refresh_token(user.id)
    await _issue_refresh_token(db, user.id, refresh)
    set_auth_cookies(response, access, refresh)

    verified = bool(user.email_verified_at)
    return {
        "user": {"id": user.id, "email": user.email, "display_name": user.display_name, "avatar_url": user.avatar_url},
        "profile": {
            "preferred_modality": profile.preferred_modality,
            "learning_velocity": profile.learning_velocity,
            "cognitive_style": profile.cognitive_style,
            "difficulty_preference": profile.difficulty_preference,
        },
        "verified": verified,
        "can_resend_verification": not verified,
    }


@app.post("/auth/resend-verification")
async def auth_resend_verification(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user_required(request, db)
    if user.email_verified_at:
        return {"status": "already_verified"}
    if not user.email:
        raise HTTPException(status_code=400, detail="Missing email")

    verify_token = await _create_email_token(db, user, "verify_email", timedelta(hours=24))
    verify_url = f"{APP_PUBLIC_URL}/auth/verify-email?token={verify_token}"
    return {"status": "sent", "verify_url": verify_url}


@app.get("/auth/verify-email")
async def auth_verify_email(token: str, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    wants_html = "text/html" in (request.headers.get("accept") or "").lower()
    token_hash = _hash_token(token)

    row = (
        await db.execute(
            select(EmailToken).where(
                and_(
                    EmailToken.token_hash == token_hash,
                    EmailToken.purpose == "verify_email",
                )
            )
        )
    ).scalar_one_or_none()
    if not row or row.consumed_at is not None:
        if wants_html:
            return HTMLResponse(status_code=400, content="<h2>Invalid link</h2><p><a href='/'>Back</a></p>")
        raise HTTPException(status_code=400, detail="Invalid link")
    if row.expires_at.replace(tzinfo=timezone.utc) < utcnow():
        if wants_html:
            return HTMLResponse(status_code=400, content="<h2>Link expired</h2><p><a href='/'>Back</a></p>")
        raise HTTPException(status_code=400, detail="Link expired")

    user = await db.get(User, row.user_id)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid link")

    user.email_verified_at = datetime.utcnow()
    row.consumed_at = datetime.utcnow()

    if wants_html:
        return RedirectResponse(url="/", status_code=302)
    return {"status": "verified"}


@app.post("/auth/request-password-reset")
async def auth_request_password_reset(payload: RequestResetRequest, db: AsyncSession = Depends(get_db)):
    email = payload.email.lower()
    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()

    reset_url = None
    if user and user.email:
        reset_token = await _create_email_token(db, user, "reset_password", timedelta(minutes=30))
        reset_url = f"{APP_PUBLIC_URL}/auth/reset?token={reset_token}"

    return {"status": "ok", "reset_url": reset_url}


@app.get("/auth/reset", response_class=HTMLResponse)
async def auth_reset_page(token: str):
    return HTMLResponse(
        content=f"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Reset password</title>
  <style>
    body {{ font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial; background:#0b0f17; color:#f8fafc; margin:0; padding:2rem; }}
    .card {{ max-width:420px; margin:0 auto; background:rgba(255,255,255,.06); border:1px solid rgba(255,255,255,.14); border-radius:16px; padding:1.25rem; }}
    h1 {{ margin:0 0 .75rem; font-size:1.25rem; }}
    label {{ display:block; font-size:.9rem; margin:.75rem 0 .35rem; opacity:.9; }}
    input {{ width:100%; padding:.7rem .8rem; border-radius:12px; border:1px solid rgba(255,255,255,.18); background:rgba(0,0,0,.25); color:#fff; }}
    button {{ margin-top:1rem; width:100%; padding:.75rem .9rem; border-radius:12px; border:1px solid rgba(255,255,255,.18); background:rgba(255,255,255,.12); color:#fff; font-weight:700; cursor:pointer; }}
    .msg {{ margin-top:.75rem; font-size:.9rem; opacity:.9; }}
    a {{ color:#93c5fd; }}
  </style>
</head>
<body>
  <div class="card">
    <h1>Set a new password</h1>
    <form id="f">
      <input type="hidden" name="token" value="{token}" />
      <label>New password</label>
      <input name="new_password" type="password" minlength="8" required />
      <button type="submit">Reset password</button>
      <div class="msg" id="msg"></div>
    </form>
  </div>
  <script>
    const form = document.getElementById('f');
    const msg = document.getElementById('msg');
    form.addEventListener('submit', async (e) => {{
      e.preventDefault();
      msg.textContent = 'Working…';
      const fd = new FormData(form);
      const body = Object.fromEntries(fd.entries());
      const res = await fetch('/auth/reset-password', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify(body),
        credentials: 'include'
      }});
      const data = await res.json().catch(() => ({{}}));
      if (!res.ok) {{
        msg.textContent = data.detail || 'Reset failed';
        return;
      }}
      msg.innerHTML = 'Password updated. <a href=\"/\">Go back</a>.';
    }});
  </script>
</body>
</html>
""",
    )


@app.post("/auth/reset-password")
async def auth_reset_password(payload: ResetPasswordRequest, response: Response, db: AsyncSession = Depends(get_db)):
    _validate_password(payload.new_password)
    token_hash = _hash_token(payload.token)

    row = (
        await db.execute(
            select(EmailToken).where(
                and_(
                    EmailToken.token_hash == token_hash,
                    EmailToken.purpose == "reset_password",
                )
            )
        )
    ).scalar_one_or_none()
    if not row or row.consumed_at is not None:
        raise HTTPException(status_code=400, detail="Invalid link")
    if row.expires_at.replace(tzinfo=timezone.utc) < utcnow():
        raise HTTPException(status_code=400, detail="Link expired")

    user = await db.get(User, row.user_id)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid link")

    user.hashed_password = hash_value(payload.new_password)
    row.consumed_at = datetime.utcnow()
    await _revoke_refresh_tokens(db, user.id)
    clear_auth_cookies(response)
    return {"status": "ok"}


@app.post("/auth/change-password")
async def auth_change_password(payload: ChangePasswordRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    user = await get_current_user_required(request, db)
    if not user.hashed_password:
        raise HTTPException(status_code=400, detail="Password login is not enabled for this account")
    if not verify_hash(payload.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    _validate_password(payload.new_password)
    user.hashed_password = hash_value(payload.new_password)
    await _revoke_refresh_tokens(db, user.id)
    clear_auth_cookies(response)
    return {"status": "ok"}


@app.post("/auth/google")
async def auth_google(payload: GoogleAuthRequest, response: Response, db: AsyncSession = Depends(get_db)):
    async with httpx.AsyncClient(timeout=10.0) as client:
        token_info = await client.get("https://oauth2.googleapis.com/tokeninfo", params={"id_token": payload.id_token})
    if token_info.status_code != 200:
        raise HTTPException(status_code=400, detail="Invalid Google token")

    info = token_info.json()
    if GOOGLE_CLIENT_ID and info.get("aud") != GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=400, detail="Invalid token audience")

    email = (info.get("email") or "").lower()
    if not email:
        raise HTTPException(status_code=400, detail="Google token missing email")

    stmt = select(User).where(User.email == email)
    user = (await db.execute(stmt)).scalar_one_or_none()
    if not user:
        user = User(
            email=email,
            display_name=info.get("name") or email.split("@")[0],
            avatar_url=info.get("picture"),
            auth_provider="google",
        )
        user.email_verified_at = datetime.utcnow()
        db.add(user)
        await db.flush()
    elif not user.email_verified_at:
        user.email_verified_at = datetime.utcnow()

    user.last_login_at = datetime.utcnow()
    profile = await ensure_profile(db, user.id)

    access = create_access_token(user.id, user.email or "")
    refresh = create_refresh_token(user.id)
    await _issue_refresh_token(db, user.id, refresh)

    set_auth_cookies(response, access, refresh)
    return {
        "user": {"id": user.id, "email": user.email, "display_name": user.display_name, "avatar_url": user.avatar_url},
        "profile": {
            "preferred_modality": profile.preferred_modality,
            "learning_velocity": profile.learning_velocity,
            "cognitive_style": profile.cognitive_style,
            "difficulty_preference": profile.difficulty_preference,
        },
    }


@app.get("/auth/google-client-id")
async def auth_google_client_id():
    return {"client_id": GOOGLE_CLIENT_ID}


@app.post("/auth/refresh")
async def auth_refresh(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    refresh = request.cookies.get(REFRESH_COOKIE_NAME)
    if not refresh:
        raise HTTPException(status_code=401, detail="Missing refresh token")
    payload = decode_token(refresh)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    row_stmt = select(RefreshToken).where(RefreshToken.token == refresh)
    row = (await db.execute(row_stmt)).scalar_one_or_none()
    if not row or row.revoked_at is not None or row.expires_at.replace(tzinfo=timezone.utc) < utcnow():
        raise HTTPException(status_code=401, detail="Refresh token expired")

    user = await db.get(User, payload.get("sub"))
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    access = create_access_token(user.id, user.email or "")
    set_auth_cookies(response, access, refresh)
    return {"status": "ok"}


@app.post("/auth/logout")
async def auth_logout(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    refresh = request.cookies.get(REFRESH_COOKIE_NAME)
    if refresh:
        row = (await db.execute(select(RefreshToken).where(RefreshToken.token == refresh))).scalar_one_or_none()
        if row:
            row.revoked_at = datetime.utcnow()
    clear_auth_cookies(response)
    return {"status": "ok"}


@app.get("/auth/me")
async def auth_me(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    user = await get_current_user_optional(request, db)
    if not user:
        return {"authenticated": False}
    profile = await ensure_profile(db, user.id)
    return {
        "authenticated": True,
        "user": {
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "avatar_url": user.avatar_url,
            "verified": bool(user.email_verified_at),
        },
        "profile": {
            "preferred_modality": profile.preferred_modality,
            "avg_session_length_minutes": profile.avg_session_length_minutes,
            "total_concepts_mastered": profile.total_concepts_mastered,
            "learning_velocity": profile.learning_velocity,
            "streak_days": profile.streak_days,
            "cognitive_style": profile.cognitive_style,
            "difficulty_preference": profile.difficulty_preference,
        },
    }


@app.get("/api/user/documents")
async def user_documents(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user_required(request, db)

    sessions = list(
        (
            await db.execute(
                select(LearningSession)
                .where(LearningSession.user_id == user.id)
                .order_by(LearningSession.created_at.desc())
                .limit(24)
            )
        ).scalars().all()
    )
    if not sessions:
        return {"documents": []}

    session_ids = [s.id for s in sessions]
    progress_rows = list(
        (
            await db.execute(
                select(TopicProgress).where(and_(TopicProgress.user_id == user.id, TopicProgress.session_id.in_(session_ids)))
            )
        ).scalars().all()
    )
    progress_by_session: dict[str, list[TopicProgress]] = {}
    for p in progress_rows:
        progress_by_session.setdefault(p.session_id, []).append(p)

    docs: list[dict[str, Any]] = []
    for s in sessions:
        rows = progress_by_session.get(s.id, [])
        total = len(rows)
        mastered = sum(1 for r in rows if r.status == "mastered")
        pct = int(round((mastered / total) * 100)) if total else 0
        created = s.created_at.strftime("%b %d, %Y") if s.created_at else "—"
        docs.append(
            {
                "id": s.id,
                "title": s.filename or "Untitled",
                "progress": pct,
                "progress_label": f"{pct}%",
                "subtitle": f"{total} concepts • {created}",
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
        )

    return {"documents": docs}


@app.get("/api/user/at-risk-concepts")
async def user_at_risk_concepts(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user_required(request, db)

    rows = list(
        (
            await db.execute(
                select(TopicProgress, Concept)
                .join(Concept, Concept.id == TopicProgress.concept_id)
                .where(
                    and_(
                        TopicProgress.user_id == user.id,
                        TopicProgress.session_id.is_not(None),
                        TopicProgress.status.in_(["struggling", "in_progress"]),
                    )
                )
                .order_by(TopicProgress.score.asc(), TopicProgress.updated_at.desc())
                .limit(10)
            )
        ).all()
    )

    concepts: list[dict[str, Any]] = []
    for p, c in rows:
        hint = f"Score {int(p.score or 0)} • {p.attempt_count or 0} attempts"
        concepts.append(
            {
                "session_id": p.session_id,
                "concept_id": c.id,
                "name": c.name,
                "hint": hint,
                "score": int(p.score or 0),
                "attempt_count": int(p.attempt_count or 0),
            }
        )

    return {"concepts": concepts}


@app.get("/api/user/recommendations")
async def user_recommendations(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user_required(request, db)

    latest = (await db.execute(select(LearningSession).where(LearningSession.user_id == user.id).order_by(LearningSession.created_at.desc()).limit(1))).scalar_one_or_none()
    if not latest:
        return {"primary_action": "Upload a PDF to start learning", "secondary_actions": [], "estimated_minutes_remaining": 0, "session_id": None}

    return await compute_next_steps_for_session(db, user, latest.id)


@app.post("/api/process")
async def process_document(
    request: Request,
    file: UploadFile = File(...),
    learningIntent: str = Form("Understand the chapter"),
    db: AsyncSession = Depends(get_db),
):
    user = await get_current_user_verified_required(request, db)

    contents = await file.read()
    session_id = str(uuid.uuid4())
    pdf_path = save_upload(file.filename, contents)
    text = extract_text(pdf_path)
    summary = await summarize_text(text, max_sections=8)
    image_paths = extract_images(pdf_path, session_id)

    large_image_paths = []
    for path in image_paths:
        try:
            if os.path.getsize(path) > 1024:
                large_image_paths.append(path)
            else:
                os.remove(path)
        except OSError:
            continue

    concepts = extract_concepts_from_summary(summary)
    overview = {
        "session_id": session_id,
        "file_name": file.filename,
        "intent": learningIntent,
        "concepts": concepts,
        "estimated_study_time_minutes": estimate_study_time_minutes(text, concepts),
        "visuals_count": len(large_image_paths),
    }

    db_session = LearningSession(
        id=session_id,
        user_id=user.id,
        filename=file.filename,
        pdf_path=pdf_path,
        text_content=text,
        summary=summary,
        intent=learningIntent,
        image_paths_json=[to_original_url(p) for p in large_image_paths],
        concepts_json=concepts,
        overview_json=overview,
    )
    db.add(db_session)

    for idx, c in enumerate(concepts):
        content = "\n".join([f"- {b}" for b in c.get("bullets", [])]) or c.get("summary", "")
        db.add(
            Concept(
                id=c["id"],
                session_id=session_id,
                name=c["name"],
                summary=c.get("summary", ""),
                content=content,
                concept_type=c.get("type", "core"),
                importance=c.get("importance", 1),
                order_index=idx,
                estimated_minutes=5,
            )
        )
        db.add(
            TopicProgress(
                user_id=user.id,
                session_id=session_id,
                concept_id=c["id"],
                status="unlocked" if idx == 0 else "locked",
                current_difficulty="medium",
            )
        )

    # Ensure the session is committed before returning the `sessionId`.
    # Otherwise, the client can redirect to `/learn/{sessionId}` and fetch
    # `/api/session/{sessionId}` before the dependency teardown commits.
    await db.commit()

    return {
        "sessionId": session_id,
        "status": "complete",
        "mainTopic": concepts[0]["name"] if concepts else file.filename,
        "studyTime": f"{overview['estimated_study_time_minutes']} min",
        "visuals": len(large_image_paths),
        "concepts": concepts,
        "summary": summary,
        "pdfUrl": to_original_url(pdf_path),
    }


@app.get("/api/session/{session_id}")
async def get_session(session_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user_verified_required(request, db)
    session = await db.get(LearningSession, session_id)
    if not session or session.user_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")

    pdf_url: str | None = None
    if session.pdf_path:
        pdf_url = to_original_url(session.pdf_path)

    concepts = list(
        (
            await db.execute(select(Concept).where(Concept.session_id == session_id).order_by(Concept.order_index.asc()))
        ).scalars().all()
    )
    progress = list(
        (
            await db.execute(
                select(TopicProgress).where(and_(TopicProgress.session_id == session_id, TopicProgress.user_id == user.id))
            )
        ).scalars().all()
    )
    progress_map = {p.concept_id: p for p in progress}

    return {
        "session": {
            "id": session.id,
            "filename": session.filename,
            "pdf_url": pdf_url,
            "summary": session.summary,
            "concepts": [
                {
                    "id": c.id,
                    "title": c.name,
                    "summary": c.summary,
                    "content": c.content,
                    "order_index": c.order_index,
                    "estimated_minutes": c.estimated_minutes,
                    "status": progress_map.get(c.id).status if progress_map.get(c.id) else "locked",
                    "score": progress_map.get(c.id).score if progress_map.get(c.id) else 0,
                    "attempt_count": progress_map.get(c.id).attempt_count if progress_map.get(c.id) else 0,
                    "current_difficulty": progress_map.get(c.id).current_difficulty if progress_map.get(c.id) else "medium",
                }
                for c in concepts
            ],
        }
    }


@app.get("/api/session/{session_id}/check-questions")
async def get_check_questions(session_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user_verified_required(request, db)
    session = await db.get(LearningSession, session_id)
    if not session or session.user_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")

    overview = session.overview_json or {}
    if isinstance(overview, dict) and overview.get("check_questions"):
        return {"questions": overview.get("check_questions")}

    questions = await generate_check_questions_from_summary(session.summary or "", n=3)
    if not isinstance(overview, dict):
        overview = {}
    overview["check_questions"] = questions
    session.overview_json = overview
    await db.commit()

    return {"questions": questions}


@app.get("/api/session/{session_id}/detailed-summary")
async def get_detailed_summary(session_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user_verified_required(request, db)
    session = await db.get(LearningSession, session_id)
    if not session or session.user_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")

    overview = session.overview_json or {}
    if isinstance(overview, dict) and overview.get("detailed_summary"):
        return {"detailed_summary": overview.get("detailed_summary")}

    detailed = await detailed_summary_text(session.text_content or "")
    if not isinstance(overview, dict):
        overview = {}
    overview["detailed_summary"] = detailed
    session.overview_json = overview
    await db.commit()
    return {"detailed_summary": detailed}


@app.post("/api/session/{session_id}/translate")
async def translate_session_text(session_id: str, payload: TranslateRequest, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user_verified_required(request, db)
    session = await db.get(LearningSession, session_id)
    if not session or session.user_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")

    target = (payload.target_language or "").strip()
    if not target:
        raise HTTPException(status_code=400, detail="Missing target_language")

    overview = session.overview_json or {}
    if not isinstance(overview, dict):
        overview = {}

    translations = overview.get("translations")
    if not isinstance(translations, dict):
        translations = {}

    cache_key = target.lower()
    if cache_key in translations and isinstance(translations.get(cache_key), str):
        return {"translated_text": translations.get(cache_key), "cached": True}

    source_text = payload.text
    if not source_text:
        source_text = overview.get("detailed_summary") or session.summary or ""

    from .azure_openai_utils import azure_text

    prompt = f"""Translate the following markdown into {target}.
Preserve markdown structure (headings, bullets) and keep meaning accurate.

Text:
{source_text}
"""
    translated = await azure_text(
        system="You are a precise translator for study notes.",
        prompt=prompt,
        fallback=source_text,
    )

    translations[cache_key] = translated
    overview["translations"] = translations
    session.overview_json = overview
    await db.commit()

    return {"translated_text": translated, "cached": False}


@app.post("/api/track-event")
async def track_event(payload: TrackEventRequest, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user_verified_required(request, db)
    event = LearningEvent(
        user_id=user.id,
        session_id=payload.session_id,
        chunk_id=payload.chunk_id,
        event_type=payload.event_type,
        payload=payload.payload,
    )
    db.add(event)
    return {"ok": True}


@app.post("/api/infer-profile")
async def infer_profile(_: InferProfileRequest, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user_verified_required(request, db)
    profile = await maybe_infer_profile(db, user.id)
    return {
        "preferred_modality": profile.preferred_modality,
        "learning_velocity": profile.learning_velocity,
        "cognitive_style": profile.cognitive_style,
        "difficulty_preference": profile.difficulty_preference,
    }


@app.post("/api/generate-quiz")
async def generate_quiz(payload: GenerateQuizRequest, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user_verified_required(request, db)
    concept = await db.get(Concept, payload.chunk_id)
    if not concept:
        raise HTTPException(status_code=404, detail="Concept not found")

    question = await generate_quiz_from_content(
        concept.content or concept.summary or concept.name,
        payload.difficulty,
        payload.question_type,
    )

    # Cache generated question for consistent evaluation on submit.
    session = await db.get(LearningSession, concept.session_id)
    if session:
        overview = session.overview_json or {}
        if not isinstance(overview, dict):
            overview = {}
        cache = overview.get("quiz_cache")
        if not isinstance(cache, dict):
            cache = {}
        key = f"{concept.id}:{payload.difficulty}:{(payload.question_type or '').strip().lower()}"
        cache[key] = question
        overview["quiz_cache"] = cache
        session.overview_json = overview
        await db.commit()

    return {
        "chunk_id": concept.id,
        "difficulty": payload.difficulty,
        "question_type": payload.question_type,
        "question": question,
    }


@app.post("/api/submit-quiz")
async def submit_quiz(payload: SubmitQuizRequest, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user_verified_required(request, db)
    concept = await db.get(Concept, payload.chunk_id)
    if not concept:
        raise HTTPException(status_code=404, detail="Concept not found")

    qt = (payload.question_type or "").strip().lower()
    session = await db.get(LearningSession, concept.session_id)
    cached = None
    if session and isinstance(session.overview_json, dict):
        cache = session.overview_json.get("quiz_cache")
        if isinstance(cache, dict):
            cached = cache.get(f"{concept.id}:{payload.difficulty}:{qt}")

    generated = cached or await generate_quiz_from_content(
        concept.content or concept.summary or concept.name,
        payload.difficulty,
        payload.question_type,
    )
    evaluation = await evaluate_answer(generated, payload.user_answer)

    score = int(evaluation.get("score", 0))
    misconceptions = evaluation.get("misconceptions", [])
    next_difficulty = compute_next_difficulty(payload.difficulty, score)
    mastered = payload.difficulty == "hard" and score >= 80
    needs_simplification = payload.difficulty == "easy" and score < 50

    attempt = QuizAttempt(
        user_id=user.id,
        chunk_id=concept.id,
        session_id=concept.session_id,
        difficulty=payload.difficulty,
        score=score,
        time_taken_ms=payload.time_taken_ms,
        misconceptions=misconceptions,
    )
    db.add(attempt)

    progress_stmt = select(TopicProgress).where(
        and_(
            TopicProgress.user_id == user.id,
            TopicProgress.session_id == concept.session_id,
            TopicProgress.concept_id == concept.id,
        )
    )
    progress = (await db.execute(progress_stmt)).scalar_one_or_none()
    if not progress:
        progress = TopicProgress(user_id=user.id, session_id=concept.session_id, concept_id=concept.id, status="in_progress")
        db.add(progress)

    progress.attempt_count += 1
    progress.score = max(progress.score, score)
    progress.current_difficulty = next_difficulty
    progress.needs_simplification = needs_simplification
    progress.last_attempt_at = datetime.utcnow()

    if mastered:
        progress.status = "mastered"
    elif score < 50 and progress.attempt_count >= 2:
        progress.status = "struggling"
    else:
        progress.status = "in_progress"

    if progress.status == "mastered":
        next_stmt = select(TopicProgress).where(
            and_(
                TopicProgress.session_id == concept.session_id,
                TopicProgress.user_id == user.id,
                TopicProgress.created_at > progress.created_at,
            )
        ).order_by(TopicProgress.created_at.asc()).limit(1)
        next_progress = (await db.execute(next_stmt)).scalar_one_or_none()
        if next_progress and next_progress.status == "locked":
            next_progress.status = "unlocked"

    await maybe_infer_profile(db, user.id)

    return {
        "score": score,
        "feedback": evaluation.get("feedback", "Here's where to focus next."),
        "misconceptions": misconceptions,
        "next_difficulty": next_difficulty,
        "mastered": mastered,
    }


@app.post("/api/visual-query")
async def visual_query(payload: VisualQueryRequest) -> dict[str, str]:
    # Standalone enhancement layer: does not touch session/db logic.
    return generate_visual_search_payload(payload.text or "")


@app.post("/api/visual-image")
async def visual_image(payload: VisualQueryRequest) -> dict[str, str | None]:
    """Generate a visual query and fetch an actual image for it."""
    text = payload.text or ""
    # Generate the optimized search query
    visual_payload = generate_visual_search_payload(text)
    search_query = visual_payload.get("search_query", "")
    
    if not search_query:
        return {"image_url": None, "error": "Could not generate search query", "search_query": ""}
    
    # Fetch the image (with fallback to placeholder)
    image_url = await fetch_first_image(search_query)
    
    # fetch_first_image always returns a URL (placeholder fallback), so error is None
    return {
        "image_url": image_url,
        "search_query": search_query,
        "error": None
    }


@app.post("/api/cognitive-status")
async def cognitive_status(_: CognitiveStatusRequest, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user_verified_required(request, db)
    events = list(
        (
            await db.execute(
                select(LearningEvent)
                .where(LearningEvent.user_id == user.id)
                .order_by(LearningEvent.created_at.desc())
                .limit(10)
            )
        ).scalars().all()
    )

    if not events:
        return {"status": "optimal", "message": "In the zone", "action": None}

    overload = 0
    underload = 0

    chunk_visits: dict[str, int] = {}
    recall_scores: list[float] = []

    for e in events:
        p = e.payload or {}
        time_ms = float(p.get("time_on_chunk_ms", 0))
        estimated_minutes = float(p.get("estimated_minutes", 5))

        if time_ms > estimated_minutes * 60_000 * 3:
            overload += 1
        if time_ms and time_ms < estimated_minutes * 60_000 * 0.4:
            underload += 1

        cid = e.chunk_id or ""
        if cid:
            chunk_visits[cid] = chunk_visits.get(cid, 0) + (1 if e.event_type == "revisit" else 0)

        score = p.get("score")
        if isinstance(score, (int, float)):
            recall_scores.append(float(score))

    if any(v > 2 for v in chunk_visits.values()):
        overload += 1

    if len(recall_scores) >= 3 and recall_scores[0] < recall_scores[1] < recall_scores[2]:
        overload += 1
    if len(recall_scores) >= 3 and min(recall_scores) >= 85:
        underload += 1

    if overload >= 2:
        return {
            "status": "overloaded",
            "message": "Slow down - your brain needs a moment",
            "action": "Take a 5 min break",
        }

    recent_cutoff = datetime.utcnow() - timedelta(minutes=25)
    recent_chunks_stmt = select(func.count(LearningEvent.id)).where(
        and_(
            LearningEvent.user_id == user.id,
            LearningEvent.created_at >= recent_cutoff,
            LearningEvent.event_type.in_(["view_end", "quiz_submit", "recall_attempt"]),
        )
    )
    recent_activity = int((await db.execute(recent_chunks_stmt)).scalar() or 0)
    if recent_activity >= 6:
        return {
            "status": "overloaded",
            "message": "You've been at this for a while. A break now will help you remember more.",
            "action": "Take a 5 min break",
        }

    if underload >= 2:
        return {
            "status": "cruising",
            "message": "You're moving fast - want harder content?",
            "action": "Switch to hard",
        }

    return {"status": "optimal", "message": "In the zone", "action": None}


@app.post("/api/next-steps")
async def next_steps(payload: NextStepsRequest, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user_verified_required(request, db)
    if payload.user_id and payload.user_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    progress = list(
        (
            await db.execute(
                select(TopicProgress, Concept)
                .join(Concept, Concept.id == TopicProgress.concept_id)
                .where(and_(TopicProgress.user_id == user.id, TopicProgress.session_id == payload.session_id))
                .order_by(Concept.order_index.asc())
            )
        ).all()
    )

    weak = [row for row in progress if row[0].score < 50 and row[0].attempt_count >= 2]
    unlocked = [row for row in progress if row[0].status == "unlocked"]
    done = [row for row in progress if row[0].status == "mastered"]
    remaining = [row for row in progress if row[0].status != "mastered"]

    if weak:
        primary = f"Revisit {weak[0][1].name} - you're close"
    elif unlocked:
        primary = f"Continue to {unlocked[0][1].name}"
    elif remaining:
        primary = "Strengthen weak areas before finishing"
    else:
        avg_mastery = sum(r[0].score for r in progress) / max(1, len(progress))
        if avg_mastery >= 80:
            primary = "You've mastered this document. Want to test yourself on the full set?"
        else:
            primary = "Strengthen weak areas before finishing"

    profile = await ensure_profile(db, user.id)
    velocity = max(0.4, profile.learning_velocity or 1.0)
    estimated = int(sum((r[1].estimated_minutes or 5.0) for r in remaining) / velocity)

    secondary = [f"Review {r[1].name}" for r in remaining[:3]]

    return {
        "primary_action": primary,
        "secondary_actions": secondary,
        "estimated_minutes_remaining": max(0, estimated),
    }


@app.get("/favicon.ico")
async def favicon():
    return Response(status_code=204)


@app.get("/", response_class=HTMLResponse)
async def landing_page(request: Request):
    response = templates.TemplateResponse("landing.html", {"request": request})
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    response = templates.TemplateResponse("login.html", {"request": request})
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    response = templates.TemplateResponse("signup.html", {"request": request})
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request, db: AsyncSession = Depends(get_db)):
    maybe = await _redirect_if_anon("/dashboard", request, db)
    if maybe:
        return maybe
    response = templates.TemplateResponse("dashboard.html", {"request": request})
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/upload", response_class=HTMLResponse)
async def upload_page(request: Request, db: AsyncSession = Depends(get_db)):
    maybe = await _redirect_if_anon("/upload", request, db)
    if maybe:
        return maybe
    response = templates.TemplateResponse("upload.html", {"request": request})
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/analytics", response_class=HTMLResponse)
async def analytics_page(request: Request, db: AsyncSession = Depends(get_db)):
    maybe = await _redirect_if_anon("/analytics", request, db)
    if maybe:
        return maybe
    response = templates.TemplateResponse("analytics.html", {"request": request})
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, db: AsyncSession = Depends(get_db)):
    maybe = await _redirect_if_anon("/settings", request, db)
    if maybe:
        return maybe
    response = templates.TemplateResponse("settings.html", {"request": request})
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/learn/{session_id}", response_class=HTMLResponse)
async def learn_page(session_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    maybe = await _redirect_if_anon(f"/learn/{session_id}", request, db)
    if maybe:
        return maybe
    response = templates.TemplateResponse("learn.html", {"request": request, "session_id": session_id, "view": "summary"})
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/learn/{session_id}/quiz", response_class=HTMLResponse)
async def learn_quiz_page(session_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    maybe = await _redirect_if_anon(f"/learn/{session_id}/quiz", request, db)
    if maybe:
        return maybe
    response = templates.TemplateResponse("learn.html", {"request": request, "session_id": session_id, "view": "quiz"})
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/learn/{session_id}/details", response_class=HTMLResponse)
async def learn_details_page(session_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    maybe = await _redirect_if_anon(f"/learn/{session_id}/details", request, db)
    if maybe:
        return maybe
    response = templates.TemplateResponse("learn.html", {"request": request, "session_id": session_id, "view": "details"})
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    users = int((await db.execute(select(func.count(User.id)))).scalar() or 0)
    sessions = int((await db.execute(select(func.count(LearningSession.id)))).scalar() or 0)
    return {"status": "healthy", "app": "EduVision", "users": users, "sessions": sessions}
