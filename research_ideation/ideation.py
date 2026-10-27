"""Load full shared inputs for conversational ideation, without task persistence."""

from datetime import datetime, timezone
import json
from .models import bounded_text, require
from .records import INPUT_TYPES, evidence_eligible


def start(database, question, constraints=""):
    question = bounded_text(question, "question", 5000)
    constraints = bounded_text(constraints, "constraints", 10000, empty=True)
    records = {kind: [] for kind in INPUT_TYPES}
    for record in database.call("inputs"):
        require(record.get("type") in records, "INVALID_RECORD", "Database returned a record outside the six input types.")
        record = {**record, "evidence_eligible": evidence_eligible(record)}
        records[record["type"]].append(record)
    counts = {kind: len(items) for kind, items in records.items()}
    return {
        "question": question, "constraints": constraints, "project": database.project,
        "read_at": datetime.now(timezone.utc).isoformat(),
        "background": {"records": records, "counts": counts,
            "missing_types": [kind for kind, count in counts.items() if not count],
            "content_characters": len(json.dumps(records, ensure_ascii=False)),
            "coverage": "All six-type records in the deployment-configured public.records scope, full stored bodies and all statuses. No search, summarization or count limit. Read in one repeatable-read transaction; no persisted task or server-side version pinning."},
        "output_policy": "Discuss ideas in this conversation. Save a local document with Hermes file tools only when requested. Do not upload ideas, conversations or reports to PostgreSQL.",
        "reasoning_rules": [
            "Missing types are unknown; no type is mandatory.",
            "Drafts can motivate provisional hypotheses; label their unconfirmed status.",
            "Rejected and superseded records are historical context, not current confirmed evidence.",
            "Diagnoses are explanations to challenge; online correlations do not establish causation.",
            "Historical proposals are not completed experiments or adopted decisions.",
            "Cite actual input IDs, versions and sources. Re-read when current facts are needed.",
            "If the host truncated the input or model capacity is exceeded, disclose the limitation and stop recommendations; do not silently summarize or filter.",
            "Output one affordable, falsifiable idea or explain why no recommendation is justified.",
        ],
    }
