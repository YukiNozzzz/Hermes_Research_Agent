"""Model-facing operations. No user_id, profile, data_root or arbitrary filesystem parameters."""


def schema(name,description,properties,required=()):
    return {"name":name,"description":description,"parameters":{"type":"object","properties":properties,
            "required":list(required),"additionalProperties":False}}


TEXT={"type":"string"}
PROJECT={"project_id":{"type":"string","description":"Omit to use the single user's configured default project; specify another project only if already registered."}}
REF={"type":"object","properties":{"id":TEXT,"version":{"type":"integer"},"quote":TEXT},"required":["id","version"],"additionalProperties":False}
REFS={"type":"array","items":REF,"maxItems":50}
CANDIDATE={"type":"object","properties":{**{k:TEXT for k in ("title","hypothesis","method","related_work","experiment","risks")},"refs":REFS},
           "required":["title","hypothesis","method","related_work","experiment","risks","refs"],"additionalProperties":False}

SCHEMAS=[
schema("research_project","Read this profile's project overview, current problems, history, personal experience and feedback. Shared and personal records remain distinguished.",PROJECT),
schema("research_record","Record a user-reported fact, problem, decision, experiment or experience. Default private. Use project scope only for explicitly shared facts. Generated ideas must use research_finish. Updates require the version read.",
       {**PROJECT,"kind":{"type":"string","enum":["note","experience","problem","experiment","decision"]},"title":TEXT,"body":TEXT,
        "visibility":{"type":"string","enum":["private","project"]},"refs":REFS,"record_id":TEXT,"version":{"type":"integer"},
        "fields":{"type":"object","description":"Type-specific draft fields. Human conclusion/adoption fields are reserved for administrator review."},
        "sources":{"type":"array","maxItems":50,"items":{"type":"object","properties":{k:TEXT for k in ("kind","uri","locator","sha256","coverage")},"required":["kind","uri"],"additionalProperties":False}}},["title","body"]),
schema("research_search","Search accessible project and personal records by keywords; optional kind filter. During ideation always pass task_id so evidence is recorded. Results are snippets, not necessarily full text.",
       {**PROJECT,"query":TEXT,"kind":TEXT,"limit":{"type":"integer","minimum":1,"maximum":100},"task_id":TEXT},["query"]),
schema("research_read","Read a visible record's full stored text and actual version, or retrieve a saved task by its task_ id. During research pass task_id. A paper may contain only its abstract; honor content_coverage.",
       {**PROJECT,"record_id":TEXT,"task_id":TEXT,"version":{"type":"integer","minimum":1}},["record_id"]),
schema("research_start","Start evidence-grounded exploration of a concrete research difficulty. Returns real project context and a task_id. Personal tasks stay private; service tasks use only shared input.",
       {**PROJECT,"question":TEXT},["question"]),
schema("research_finish","Save an actual research task after reading evidence and reviewing candidates. Up to 3 candidates, or none with reasons. Every candidate needs observed id/version references, an experiment and risks. Finish is idempotent.",
       {**PROJECT,"task_id":TEXT,"candidates":{"type":"array","items":CANDIDATE,"maxItems":3},"review":TEXT,"check_scope":TEXT,"open_questions":TEXT},
       ["task_id","candidates","review","check_scope"]),
schema("research_publish","Only when the user explicitly asks: publish their own selected private record to the whole current project, or withdraw a shared record they may edit. Does not share the whole conversation. Private input dependencies must be resolved first.",
       {**PROJECT,"record_id":TEXT,"version":{"type":"integer"},"action":{"type":"string","enum":["publish","withdraw"]}},["record_id","version","action"]),
schema("research_feedback","Append the user's evaluation or real experimental outcome to an idea. Preserve reasons and provenance. Feedback is private initially; publish separately if requested.",
       {**PROJECT,"idea_id":TEXT,"evaluation":{"type":"string","enum":["accepted","rejected","needs_revision","testing","supported","not_supported"]},"reason":TEXT},["idea_id","evaluation","reason"]),
schema("research_update_papers","Fetch actual recent arXiv metadata/abstracts as the selected single user or its optional collector. Deduplicate and persist once per project/day. Run when the user requests an update or a scheduled workflow requires it; failure is not zero new papers.",
       {**PROJECT,"lookback_days":{"type":"integer","minimum":1,"maximum":365},"force":{"type":"boolean"}}),
]
