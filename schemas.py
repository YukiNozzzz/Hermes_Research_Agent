"""One read-only model tool; identity, SQL and paths are deployment configuration."""

SCHEMAS = [{
    "name": "research_start",
    "description": "Read ALL six types of shared research inputs from PostgreSQL with full stored bodies, statuses, versions and sources. No retrieval, summaries or count limit. Does not create a task, call a model or save an idea/report. Use the problem-exploration skill and answer in the conversation; save a local document only when requested.",
    "parameters": {
        "type": "object", "additionalProperties": False,
        "properties": {
            "question": {"type": "string", "minLength": 1, "maxLength": 5000},
            "constraints": {"type": "string", "maxLength": 10000,
                            "description": "Business goals, resource limits and protected metrics; unknowns stay explicit."},
        },
        "required": ["question"],
    },
}]
