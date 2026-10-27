"""Small shared validation contracts."""

import re


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


def bounded_text(value, name, limit, empty=False):
    require(isinstance(value, str) and (empty or value.strip()) and len(value) <= limit,
            "INVALID_INPUT", f"{name} must be text of at most {limit} characters.")
    return value.strip()
