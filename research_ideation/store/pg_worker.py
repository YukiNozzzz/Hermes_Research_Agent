"""仅由管理员配置的 CRA Python 运行。SQL 集中于 store，不加载 Hermes。"""

import hashlib
import json
from pathlib import Path
import sys


def main():
    repository, env_file = sys.argv[1:]
    sys.path.insert(0, str(Path(repository) / "src"))
    from datetime import UTC, datetime
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import sessionmaker
    from cra.config import Settings
    from cra.records.schema import parse_record, type_fields, missing_human_fields
    from cra.store.context import ContextStore
    from cra.store.models import Record, RecordRevision, RecordLink, RecordSource, Source

    request = json.load(sys.stdin)
    settings = Settings(_env_file=env_file)
    if "database_url" not in settings.model_fields_set:
        raise ValueError("Shared database is not configured.")
    engine = create_engine(settings.database_url, connect_args={
        "connect_timeout": 10, "options": "-c statement_timeout=15000"})
    store = ContextStore(sessionmaker(engine, expire_on_commit=False))
    project = request["project_id"]
    operation = request["operation"]
    if request.get("role") not in {"user", "service"}:
        raise ValueError("ACCESS_DENIED")
    if operation in {"review", "withdraw"} and request["role"] != "user":
        raise ValueError("ACCESS_DENIED")

    def check_project(row):
        bound = row.fields.get("_ri", {}).get("project_id")
        if bound is not None and bound != project:
            raise ValueError("NOT_FOUND")

    def document(session, row):
        check_project(row)
        doc = store._document(session, row)
        doc["fields"] = row.fields
        evidence={item["id"]:item for item in row.fields.get("_ri",{}).get("evidence",[])}
        for link in doc["links"]:
            ref=evidence.get("cra:"+link["target_id"])
            target=session.get(Record,link["target_id"])
            link["version"]=ref["version"] if ref else (target.version if target else None)
            link["quote"]=ref.get("quote","") if ref else ""
        return doc

    def read_version(session, record_id, version=None):
        row = session.get(Record, record_id)
        if row is None or row.status != "confirmed":
            raise ValueError("NOT_FOUND")
        check_project(row)
        for link in session.scalars(select(RecordLink).where(RecordLink.src_id==row.id)):
            target=session.get(Record,link.dst_id)
            if target is None or target.status!="confirmed":raise ValueError("NOT_FOUND")
            check_project(target)
        if version is None or version == row.version:
            return document(session, row)
        revision = session.scalar(select(RecordRevision).where(
            RecordRevision.record_id == record_id, RecordRevision.version == version))
        if revision is None or revision.snapshot.get("status") != "confirmed":
            raise ValueError("NOT_FOUND")
        snapshot = dict(revision.snapshot)
        snapshot.setdefault("fields", {key: value for key, value in snapshot.items()
                                       if key not in {"id", "type", "title", "body", "status", "sources", "links"}})
        return snapshot

    try:
        if operation == "check":
            data = store.check()
        elif operation == "search":
            kind = request.get("kind")
            if kind == "idea":
                kind = "proposal"
            if kind is not None and kind not in {"experience", "decision", "experiment", "online", "diagnosis", "proposal"}:
                data = []
            else:
                with store.sessions() as session:
                    query = store.search_query(request.get("query", ""), kind, min(request["limit"], 100))
                    # 过滤外部项目后再 LIMIT，不能让其他项目占据返回窗口。
                    query = query.where((Record.fields["_ri"]["project_id"].astext == project) |
                                        (Record.fields["_ri"]["project_id"].astext.is_(None)))
                    data = [document(session, row) for row in session.scalars(query)]
        elif operation == "read":
            with store.sessions() as session:
                data = read_version(session, request["record_id"], request.get("version"))
        elif operation == "export":
            item = request["record"]
            digest = hashlib.sha256((project + ":" + item["id"]).encode()).hexdigest()[:24]
            date = item["created_at"][:10].replace("-", "")
            prefixes = {"experience": "exp", "decision": "dec", "experiment": "run",
                        "online": "onl", "diagnosis": "diag", "proposal": "prop"}
            record_type = "proposal" if item["kind"] == "idea" else item["kind"]
            native_id = prefixes[record_type] + "-" + date + "-ri-" + digest
            content_hash = hashlib.sha256(json.dumps(item, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            with store.sessions.begin() as session:
                # 同一项目发布使用事务级锁，重试不会重复写入。
                from sqlalchemy import text
                session.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"), {"key": native_id})
                existing = session.get(Record, native_id)
                if existing:
                    check_project(existing)
                    if existing.fields.get("_ri", {}).get("content_hash") != content_hash:
                        raise ValueError("EXPORT_CONFLICT")
                    data = {"id": "cra:" + native_id, "version": existing.version, "status": existing.status}
                else:
                    fields = dict(item["fields"])
                    if record_type == "proposal":
                        fields["adopted"] = None
                        fields["adoption_reason"] = None
                    parsed = parse_record({**fields, "type": record_type, "id": native_id,
                        "title": item["title"], "body": item["body"], "created_by": "ri:" + request["user_id"]})
                    fields = {**fields, **type_fields(parsed), "_ri": {
                        "project_id": project, "origin_record": item["id"], "origin_version": item["version"],
                        "origin_task": item.get("task_id"), "content_hash": content_hash,
                        "evidence": request["evidence"], "exported_by": request["user_id"]}}
                    # 远程引用须仍可访问且版本一致；本地来源以明确共享的证据快照保存。
                    for evidence in request["evidence"]:
                        if evidence["id"].startswith("cra:"):
                            source_doc = read_version(session, evidence["id"][4:], evidence["version"])
                            if evidence.get("quote") and evidence["quote"] not in source_doc["body"]:
                                raise ValueError("INVALID_REFERENCE")
                    row = Record(id=native_id, type=record_type, title=item["title"], body=item["body"],
                                 fields=fields, owner=parsed.owner,tags=list(dict.fromkeys(["research-ideation", project,*parsed.tags])),
                                 status="draft", created_by="ri:" + request["user_id"])
                    session.add(row); session.flush()
                    linked=set()
                    for evidence in request["evidence"]:
                        if evidence["id"].startswith("cra:"):
                            if evidence["id"] not in linked:
                                session.add(RecordLink(src_id=native_id, dst_id=evidence["id"][4:], relation="cites"))
                                linked.add(evidence["id"])
                        for source in evidence.get("sources", []):
                            uri = source.get("uri", source.get("ref"))
                            if not uri:
                                continue
                            kind = source.get("kind", "url")
                            # 序列化来源以唯一 URI 复用，定位与证据版本另外保存在 _ri 中。
                            existing_source = session.scalar(select(Source).where(Source.uri == uri))
                            if existing_source is None:
                                existing_source = Source(kind=kind, uri=uri, sha256=source.get("sha256"))
                                session.add(existing_source); session.flush()
                            locator = source.get("locator", "")
                            key = (native_id, existing_source.id, locator)
                            if session.get(RecordSource, key) is None:
                                session.add(RecordSource(record_id=native_id, source_id=existing_source.id, locator=locator))
                                session.flush()
                    origin = Source(kind="url", uri=f"urn:research-ideation:{project}:{item['id']}",
                                    sha256=content_hash, meta={"task_id": item.get("task_id")})
                    session.add(origin); session.flush()
                    session.add(RecordSource(record_id=native_id, source_id=origin.id, locator="exported draft"))
                    session.flush()
                    snapshot = document(session, row)
                    session.add(RecordRevision(record_id=native_id, version=1, action="create",
                                               actor="ri:" + request["user_id"], snapshot=snapshot))
                    data = {"id": "cra:" + native_id, "version": 1, "status": "draft"}
        elif operation == "review":
            with store.sessions.begin() as session:
                row=session.get(Record,request["record_id"],with_for_update=True)
                if row is None:raise ValueError("NOT_FOUND")
                check_project(row)
                metadata=row.fields.get("_ri",{})
                if row.version!=request["version"]:raise ValueError("VERSION_CONFLICT")
                status=request["status"]
                allowed={"draft":{"confirmed","rejected"},"confirmed":{"superseded"},"rejected":set(),"superseded":set()}
                if status not in allowed[row.status]:raise ValueError("INVALID_TRANSITION")
                if status=="superseded" and session.scalar(select(RecordLink.src_id).join(Record,Record.id==RecordLink.src_id).where(
                    RecordLink.dst_id==row.id,Record.status.in_(["draft","confirmed"])).limit(1)):
                    raise ValueError("DEPENDANTS_EXIST")
                fields=request.get("fields")
                if fields is not None:
                    if not isinstance(fields,dict) or "_ri" in fields:raise ValueError("INVALID_INPUT")
                    fields={**row.fields,**fields,**({"_ri":metadata} if metadata else {})}
                else:fields=dict(row.fields)
                parsed=parse_record({**fields,"type":row.type,"id":row.id,"title":row.title,"body":row.body,"created_by":row.created_by})
                if status=="confirmed":
                    if missing_human_fields(parsed):raise ValueError("INCOMPLETE_RECORD")
                    if not session.scalar(select(RecordSource.record_id).where(RecordSource.record_id==row.id).limit(1)) and not session.scalar(select(RecordLink.src_id).where(RecordLink.src_id==row.id).limit(1)):
                        raise ValueError("EVIDENCE_REQUIRED")
                    for evidence in metadata.get("evidence",[]):
                        if evidence["id"].startswith("cra:"):
                            read_version(session,evidence["id"][4:],evidence["version"])
                row.fields=fields;row.status=status;row.version+=1;row.updated_at=datetime.now(UTC)
                if status=="confirmed":row.confirmed_by="ri:"+request["user_id"];row.confirmed_at=row.updated_at
                session.flush();data=document(session,row)
                session.add(RecordRevision(record_id=row.id,version=row.version,action={"confirmed":"confirm","rejected":"reject","superseded":"supersede"}[status],actor="ri:"+request["user_id"],snapshot=data))
        elif operation == "withdraw":
            with store.sessions.begin() as session:
                row = session.get(Record, request["record_id"], with_for_update=True)
                if row is None:
                    raise ValueError("NOT_FOUND")
                metadata = row.fields.get("_ri", {})
                if metadata.get("project_id") != project:
                    raise ValueError("ACCESS_DENIED")
                if row.status=="superseded":
                    print(json.dumps({"ok":True,"data":{"id":"cra:"+row.id,"version":row.version,"status":row.status}}))
                    return
                if row.version != request["version"]:
                    raise ValueError("VERSION_CONFLICT")
                dependant = session.scalar(select(RecordLink.src_id).join(Record, Record.id == RecordLink.src_id).where(
                    RecordLink.dst_id == row.id, Record.status.in_(["draft", "confirmed"])).limit(1))
                if dependant:
                    raise ValueError("DEPENDANTS_EXIST")
                row.status = "superseded"; row.version += 1; row.updated_at = datetime.now(UTC)
                session.flush()
                session.add(RecordRevision(record_id=row.id, version=row.version, action="supersede",
                                           actor="ri:" + request["user_id"], snapshot=document(session, row)))
                data = {"id": "cra:" + row.id, "version": row.version, "status": row.status}
        else:
            raise ValueError("INVALID_OPERATION")
        print(json.dumps({"ok": True, "data": data}, ensure_ascii=False))
    finally:
        engine.dispose()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        known = {"NOT_FOUND", "ACCESS_DENIED", "VERSION_CONFLICT", "INVALID_REFERENCE", "EXPORT_CONFLICT", "DEPENDANTS_EXIST", "INCOMPLETE_RECORD", "EVIDENCE_REQUIRED", "INVALID_TRANSITION", "INVALID_INPUT"}
        code = str(error) if isinstance(error, ValueError) and str(error) in known else "SHARED_CONTEXT_ERROR"
        print(json.dumps({"ok": False, "code": code, "message": code + "; inspect administrator configuration or record status."}))
        sys.exit(1)
