"""Shared contracts. Never treat model-provided ids as authenticated identities."""

from dataclasses import dataclass
from datetime import datetime, timezone
import re
import uuid


class ResearchError(Exception):
    def __init__(self, code, message, retryable=False):
        super().__init__(message)
        self.code, self.retryable = code, retryable


def require(condition, code, message):
    if not condition:
        raise ResearchError(code, message)


def identifier(value):
    require(isinstance(value, str) and re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", value),
            "INVALID_ID", "Use a lowercase identifier of at most 64 characters.")
    return value


def bounded_text(value, name="text", limit=100000, empty=False):
    require(isinstance(value, str) and (empty or value.strip()) and len(value) <= limit,
            "INVALID_INPUT", f"{name} must be text, nonempty unless optional, at most {limit} characters.")
    return value.strip()


def now():
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix):
    return prefix + "_" + uuid.uuid4().hex


@dataclass(frozen=True)
class ExecutionContext:
    user_id: str
    profile: str
    profile_home: str
    project_id: str
    role: str
    session_id: str = ""
    platform: str = "cli"


RECORD_KINDS = {"note", "experience", "problem", "experiment", "decision", "paper", "idea", "feedback", "update"}
