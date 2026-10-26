"""Persisted research lifecycle; identity and scope are inherited, not chosen by the model."""

import json
from .models import require,new_id,now,bounded_text
from .storage import Store,public_record
from .memory import snapshot
from .permissions import write_scope


def get_task(registry,ctx,task_id):
    store=Store(registry,ctx)
    for scope in store.scopes:
        with store.db(scope) as db:
            row=db.execute("SELECT * FROM tasks WHERE id=? AND project_id=?",(task_id,ctx.project_id)).fetchone()
        if row and (row["owner_id"]==ctx.user_id or scope=="project"):
            task=dict(row);task["payload"]=json.loads(task["payload"])
            if scope=="project":
                # Shared snapshots must not become a back door to withdrawn sources.
                from .models import ResearchError
                try:
                    for source_id,version in task["payload"].get("observed",{}).items():
                        store.get_version(source_id,version)
                except ResearchError as exc:
                    raise ResearchError("DEPENDENCY_REVOKED","A source used by this shared task is no longer available. Start a new task with current inputs.") from exc
            return task
    require(False,"NOT_FOUND","Task not found.")


def start(registry,ctx,question):
    bounded_text(question,"question",5000)
    scope="project" if ctx.role=="service" else "private"
    write_scope(registry,ctx,scope)
    background=snapshot(registry,ctx)
    refs={item["id"]:item["version"] for entries in background["records"].values() for item in entries}
    task={"id":new_id("task"),"project_id":ctx.project_id,"owner_id":ctx.user_id,"visibility":scope,
          "kind":"ideation","status":"running","payload":{"question":question,"background":background,"observed":refs,"result":None},
          "created_at":now(),"updated_at":now()}
    with Store(registry,ctx).db(scope,write=True) as db:
        db.execute("INSERT INTO tasks VALUES(?,?,?,?,?,?,?,?,?)",tuple(json.dumps(task[k],ensure_ascii=False) if k=="payload" else task[k] for k in task))
    return task


def observe(registry,ctx,task_id,records):
    task=get_task(registry,ctx,task_id)
    require(task["owner_id"]==ctx.user_id or (task["visibility"]=="project" and ctx.role=="owner"),"ACCESS_DENIED","Only the task owner can advance this research.")
    require(task["status"]=="running","TASK_CLOSED","Research task is already closed.")
    require(all(task["visibility"]!="project" or r["visibility"]=="project" for r in records),"PRIVATE_DERIVATION","Shared tasks cannot ingest private records.")
    with Store(registry,ctx).db(task["visibility"],write=True) as db:
        latest=db.execute("SELECT status,payload FROM tasks WHERE id=?",(task_id,)).fetchone()
        require(latest and latest["status"]=="running","TASK_CLOSED","Research task is closed.")
        payload=json.loads(latest["payload"])
        payload["observed"].update({r["id"]:r["version"] for r in records})
        db.execute("UPDATE tasks SET payload=?,updated_at=? WHERE id=?",(json.dumps(payload,ensure_ascii=False),now(),task_id))


def finish(registry,ctx,task_id,candidates,review,check_scope,open_questions=""):
    task=get_task(registry,ctx,task_id)
    store=Store(registry,ctx)
    require(task["owner_id"]==ctx.user_id or (task["visibility"]=="project" and ctx.role=="owner"),"ACCESS_DENIED","Only the task owner can finish this research.")
    if task["status"] in {"completed","no_candidate"}:
        return render_saved(store,task)
    require(task["status"]=="running","TASK_CLOSED","Task cannot be finished.")
    require(isinstance(candidates,list) and len(candidates)<=3,"INVALID_INPUT","Keep at most three candidates; an empty list is allowed.")
    bounded_text(review,"review",15000);bounded_text(check_scope,"check_scope",5000)
    bounded_text(open_questions,"open_questions",10000,empty=True)
    prepared=[]
    required={"title","hypothesis","method","related_work","experiment","risks","refs"}
    for candidate in candidates:
        require(isinstance(candidate,dict) and set(candidate)==required,"INVALID_INPUT","Each candidate needs exactly title, hypothesis, method, related_work, experiment, risks, refs.")
        for key in required-{"refs"}:
            bounded_text(candidate[key],key,12000 if key!="title" else 500)
        refs=store.validate_refs(candidate["refs"],task["visibility"])
        require(refs,"EVIDENCE_REQUIRED","Each candidate needs at least one observed source.")
        require(all(task["payload"]["observed"].get(r["id"])==r["version"] for r in refs),"UNREAD_REFERENCE","Read or search each source within this task first.")
        prepared.append({**candidate,"refs":refs,"idea_id":new_id("idea")})
    result={"question":task["payload"]["question"],"candidates":prepared,"review":review,"check_scope":check_scope,"open_questions":open_questions}
    timestamp=now()
    with store.db(task["visibility"],write=True) as db:
        latest=db.execute("SELECT status,payload FROM tasks WHERE id=?",(task_id,)).fetchone()
        if latest["status"] in {"completed","no_candidate"}:
            task["payload"]=json.loads(latest["payload"]);task["status"]=latest["status"]
        else:
            require(latest["status"]=="running","TASK_CLOSED","Task is closed.")
            for c in prepared:
                body="\n\n".join(f"## {key}\n{c[key]}" for key in ("hypothesis","method","related_work","experiment","risks"))
                record={"id":c["idea_id"],"project_id":ctx.project_id,"kind":"idea","title":c["title"],"body":body,
                        "owner_id":ctx.user_id,"visibility":task["visibility"],"version":1,"refs":c["refs"],
                        "attributes":{"task_id":task_id,"status":"proposed","check_scope":check_scope},"deleted":0,"created_at":timestamp,"updated_at":timestamp}
                db.execute("INSERT INTO records VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",tuple(json.dumps(record[k],ensure_ascii=False) if k in {"refs","attributes"} else record[k] for k in record))
                db.execute("INSERT INTO history VALUES(?,?,?)",(record["id"],1,json.dumps(record,ensure_ascii=False)))
            payload=json.loads(latest["payload"]);payload["result"]=result
            task.update(status="completed" if prepared else "no_candidate",payload=payload,updated_at=timestamp)
            db.execute("UPDATE tasks SET status=?,payload=?,updated_at=? WHERE id=?",(task["status"],json.dumps(payload,ensure_ascii=False),timestamp,task_id))
    return render_saved(store,task)


def render_saved(store,task):
    result=task["payload"]["result"]
    lines=["# "+result["question"],"",f"Status: {task['status']}","", "## 检查范围",result["check_scope"],"", "## 评审",result["review"]]
    for c in result["candidates"]:
        lines.extend(["", "## "+c["title"],f"ID: {c['idea_id']}"])
        for key in ("hypothesis","method","related_work","experiment","risks"):
            lines.extend(["### "+key,c[key]])
        lines.extend(["### 依据",json.dumps(c["refs"],ensure_ascii=False)])
    lines.extend(["", "## 未解决问题",result["open_questions"] or "未记录额外问题；不代表已证明全部假设。"])
    files=store.artifacts.write_report(task["id"],task["visibility"],result,"\n\n".join(lines))
    return {"task_id":task["id"],"status":task["status"],"result":result,"report":files}


def feedback(registry,ctx,idea_id,evaluation,reason):
    require(ctx.role!="service","ACCESS_DENIED","Feedback requires a person.")
    require(evaluation in {"accepted","rejected","needs_revision","testing","supported","not_supported"},"INVALID_INPUT","Unknown feedback evaluation.")
    bounded_text(reason,"reason",15000)
    store=Store(registry,ctx);idea=store.get(idea_id)
    require(idea["kind"]=="idea","INVALID_INPUT","Feedback must target an idea.")
    # Personal feedback stays personal even when its target is shared; nobody silently edits a peer's idea.
    return public_record(store.create("feedback",evaluation+": "+idea["title"],reason,"private",
                                    [{"id":idea_id,"version":idea["version"]}],{"evaluation":evaluation,"idea_id":idea_id}))
