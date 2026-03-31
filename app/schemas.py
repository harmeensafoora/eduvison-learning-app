from pydantic import BaseModel, field_validator
from typing import Any
import re

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+(\.[^@\s]+)*$")


def _email_basic(value: str) -> str:
    email = (value or "").strip().lower()
    if not email or len(email) > 254 or not _EMAIL_RE.match(email):
        raise ValueError("Enter an email like name@example.com")
    return email

class GoogleAuthRequest(BaseModel):
    id_token: str


class EmailSignupRequest(BaseModel):
    email: str
    password: str
    display_name: str | None = None

    @field_validator("email")
    @classmethod
    def _validate_email(cls, v: str) -> str:
        return _email_basic(v)


class EmailLoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def _validate_email(cls, v: str) -> str:
        return _email_basic(v)


class RequestResetRequest(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def _validate_email(cls, v: str) -> str:
        return _email_basic(v)


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class TranslateRequest(BaseModel):
    target_language: str
    text: str | None = None


class TrackEventRequest(BaseModel):
    session_id: str | None = None
    chunk_id: str | None = None
    event_type: str
    payload: dict[str, Any] = {}


class InferProfileRequest(BaseModel):
    session_id: str | None = None


class GenerateQuizRequest(BaseModel):
    chunk_id: str
    difficulty: str = "medium"
    question_type: str | None = None


class SubmitQuizRequest(BaseModel):
    chunk_id: str
    user_answer: str
    difficulty: str = "medium"
    time_taken_ms: int = 0
    question_type: str | None = None


class NextStepsRequest(BaseModel):
    user_id: str | None = None
    session_id: str


class CognitiveStatusRequest(BaseModel):
    session_id: str | None = None


class VisualQueryRequest(BaseModel):
    text: str
