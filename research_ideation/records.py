"""与 CRA 对齐的研究记录定义；审核状态与可见范围独立。"""

from .models import require

CRA_TYPES = {"experience", "decision", "experiment", "online", "diagnosis", "proposal"}
KIND_TO_TYPE = {"idea": "proposal", **{k: k for k in CRA_TYPES}}
TYPE_TO_KIND = {**{k: k for k in CRA_TYPES}, "proposal": "idea"}
STATUSES = {"draft", "confirmed", "rejected", "superseded"}
REQUIRED = {
    "experience": {"claim", "source_kind"}, "decision": {"occasion"},
    "experiment": {"change"}, "online": {"day"},
    "diagnosis": {"experiment_id"}, "proposal": {"bottleneck", "change"},
}
HUMAN_FIELDS = {
    "decision": {"conclusion", "reasons"},
    "experiment": {"conclusion", "decision_reason"},
    "proposal": {"adopted", "adoption_reason"},
}


def validate_fields(kind, fields, *, complete=False):
    require(isinstance(fields, dict), "INVALID_INPUT", "fields must be an object.")
    record_type = KIND_TO_TYPE.get(kind)
    import json
    require(len(json.dumps(fields,ensure_ascii=False))<=100000,"INVALID_INPUT","Type-specific fields are too large.")
    if complete and record_type:
        required = REQUIRED[record_type] | HUMAN_FIELDS.get(record_type, set())
        missing = [key for key in required if key not in fields or fields[key] is None or fields[key] == ""]
        require(not missing, "INCOMPLETE_RECORD", "Missing fields: " + ", ".join(sorted(missing)))
    if record_type:
        text_fields=(REQUIRED[record_type] | HUMAN_FIELDS.get(record_type,set()))-{"adopted"}
        for key in text_fields:
            if key in fields and fields[key] is not None:
                require(isinstance(fields[key],str),"INVALID_INPUT",key+" must be text.")
        if record_type=="online" and fields.get("day"):
            from datetime import date
            try:date.fromisoformat(fields["day"])
            except ValueError:require(False,"INVALID_INPUT","day must use YYYY-MM-DD.")
    if record_type == "experience" and "source_kind" in fields:
        require(fields["source_kind"] in {"paper", "blog", "peer", "pitfall"},
                "INVALID_INPUT", "Unknown experience source_kind.")
    if "adopted" in fields:
        require(type(fields["adopted"]) is bool or fields["adopted"] is None,
                "INVALID_INPUT", "adopted must be a human supplied boolean or null.")
    return fields


def evidence_eligible(record):
    # 原始论文是可阅读的外部资料，不能因此声称其提炼结论已人工确认。
    return record.get("status", "draft") == "confirmed" or record["kind"] == "paper"


def normalize_sources(sources):
    require(isinstance(sources, list) and len(sources) <= 50, "INVALID_INPUT", "At most 50 sources.")
    result = []
    for source in sources:
        require(isinstance(source, dict) and {"kind", "uri"} <= source.keys() and
                set(source) <= {"kind", "uri", "locator", "sha256", "coverage"},
                "INVALID_SOURCE", "Source needs kind and uri, with optional locator/sha256/coverage.")
        require(all(isinstance(value, str) and len(value) <= 4000 for value in source.values())
                and source["uri"].strip(), "INVALID_SOURCE", "Source values must be bounded strings.")
        result.append(dict(source))
    require(len({(s["uri"], s.get("locator", "")) for s in result}) == len(result),
            "INVALID_SOURCE", "Duplicate source locator.")
    return result
