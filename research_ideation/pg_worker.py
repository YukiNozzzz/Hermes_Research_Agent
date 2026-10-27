"""CRA-environment reader for existing public tables. No DDL or write operations."""

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from research_ideation.models import ResearchError, require, identifier
from research_ideation.records import INPUT_TYPES

SCOPE = """type = ANY(:types)
    AND (fields->'_ri'->>'project_id' = :project
         OR (:unscoped AND fields->'_ri'->>'project_id' IS NULL))
    AND COALESCE(fields->'_ri'->>'visibility', 'project') = 'project'"""
REQUIRED_TABLES = ("records", "record_revisions", "sources", "record_sources", "record_links")


def validate_request(request):
    require(isinstance(request, dict) and set(request) == {"operation", "project_id", "include_unscoped"},
            "INVALID_OPERATION", "Only the configured read-only input request is accepted.")
    require(request["operation"] in {"health", "inputs"}, "INVALID_OPERATION", "Only health and inputs are available.")
    identifier(request["project_id"])
    require(type(request["include_unscoped"]) is bool, "INVALID_CONFIG", "include_unscoped must be true or false.")


def run_request(connection, request):
    from sqlalchemy import text
    validate_request(request)
    parameters = {"types": list(INPUT_TYPES), "project": request["project_id"], "unscoped": request["include_unscoped"]}
    if request["operation"] == "health":
        tables = {name: connection.execute(text("SELECT to_regclass(:name)"), {"name": "public." + name}).scalar() is not None
                  for name in REQUIRED_TABLES}
        ready = all(tables.values())
        groups = [dict(row) for row in connection.execute(text("SELECT type,status,count(*) AS count FROM public.records WHERE " + SCOPE + " GROUP BY type,status ORDER BY type,status"), parameters).mappings()] if ready else []
        return {"connected": True, "backend": "postgresql", "source": "public.records",
                "project_id": request["project_id"], "include_unscoped": request["include_unscoped"],
                "read_only": connection.execute(text("SHOW transaction_read_only")).scalar() == "on",
                "ready": ready, "tables": tables, "input_counts_by_status": groups}

    rows = [dict(row) for row in connection.execute(text("""SELECT id,type,title,body,status,version,fields,tags,owner,
        created_by,confirmed_by,confirmed_at,created_at,updated_at
        FROM public.records WHERE """ + SCOPE + " ORDER BY created_at,id"), parameters).mappings()]
    if not rows:
        return []
    versions = {row["id"]: row["version"] for row in rows}
    ids = list(versions)
    sources, links = {}, {}
    for source in connection.execute(text("""SELECT rs.record_id,s.kind,s.uri,s.title,s.sha256,s.meta,rs.locator
        FROM public.record_sources rs JOIN public.sources s ON s.id=rs.source_id
        WHERE rs.record_id=ANY(:ids) ORDER BY rs.record_id,s.id,rs.locator"""), {"ids": ids}).mappings():
        source = dict(source)
        sources.setdefault(source.pop("record_id"), []).append(source)
    for link in connection.execute(text("""SELECT src_id,dst_id,relation,note FROM public.record_links
        WHERE src_id=ANY(:ids) ORDER BY src_id,dst_id,relation"""), {"ids": ids}).mappings():
        source_id = link["src_id"]
        item = {"target_id": link["dst_id"], "relation": link["relation"], "note": link["note"],
                "available_in_context": link["dst_id"] in versions}
        if item["available_in_context"]:
            item["version"] = versions[link["dst_id"]]
        links.setdefault(source_id, []).append(item)
    for row in rows:
        row["fields"] = {key: value for key, value in row["fields"].items() if key != "_ri"}
        row["sources"], row["links"] = sources.get(row["id"], []), links.get(row["id"], [])
        for key in ("confirmed_at", "created_at", "updated_at"):
            if row[key] is not None:
                row[key] = row[key].isoformat()
    return rows


def main():
    repository, env_file = sys.argv[1:]
    request = json.load(sys.stdin)
    validate_request(request)
    sys.path.insert(0, str(Path(repository) / "src"))
    from cra.config import Settings
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url
    settings = Settings(_env_file=env_file)
    require("database_url" in settings.model_fields_set and make_url(settings.database_url).get_backend_name() == "postgresql",
            "INVALID_CONFIG", "The configured environment must contain a PostgreSQL connection.")
    engine = create_engine(settings.database_url, connect_args={"connect_timeout": 10,
        "options": "-c statement_timeout=15000 -c default_transaction_read_only=on",
        "application_name": "research-ideation-readonly"})
    try:
        with engine.connect().execution_options(isolation_level="REPEATABLE READ") as connection:
            with connection.begin():
                connection.execute(text("SET TRANSACTION READ ONLY"))
                result = run_request(connection, request)
        print(json.dumps({"ok": True, "data": result}, ensure_ascii=False))
    finally:
        engine.dispose()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        state = getattr(getattr(exc, "orig", None), "sqlstate", "")
        code = exc.code if isinstance(exc, ResearchError) else {"42P01": "DATABASE_NOT_READY", "42501": "DATABASE_ACCESS_DENIED"}.get(state, "DATABASE_ERROR")
        message = str(exc) if isinstance(exc, ResearchError) else "PostgreSQL inputs could not be read. Check the connection, permissions and source tables; no data was saved."
        print(json.dumps({"ok": False, "code": code, "message": message, "retryable": code == "DATABASE_ERROR"}, ensure_ascii=False))
        sys.exit(1)
