"""The six existing CRA input types; generated ideas are not database records."""

INPUT_TYPES = ("experience", "decision", "experiment", "online", "diagnosis", "proposal")
STATUSES = {"draft", "confirmed", "rejected", "superseded"}


def evidence_eligible(record):
    return record["status"] == "confirmed"
