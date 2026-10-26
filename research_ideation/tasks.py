"""Persisted research lifecycle; identity and scope are inherited, not chosen by the model."""

import json
from .models import require,new_id,now,bounded_text
from .storage import Store,public_record
from .memory import snapshot
from .permissions import write_scope


def get_task(registry,ctx,task_id):
    store=Store(registry,ctx)
    task=store.task_get(task_id)
    if task["visibility"]=="project":
        from .models import ResearchError
        try:
            for source_id,version in task["payload"].get("observed",{}).items():
                store.get_version(source_id,version)
        except ResearchError as exc:
            raise ResearchError("DEPENDENCY_REVOKED","A source used by this shared task is no longer available. Start a new task with current inputs.") from exc
    return task


def start(registry,ctx,question):
    bounded_text(question,"question",5000)
    scope="project" if ctx.role=="service" else "private"
    write_scope(registry,ctx,scope)
    background=snapshot(registry,ctx,research=True)
    refs={item["id"]:item["version"] for entries in background["records"].values() for item in entries}
    task={"id":new_id("task"),"project_id":ctx.project_id,"owner_id":ctx.user_id,"visibility":scope,
          "kind":"ideation","status":"running","payload":{"question":question,"background":background,"observed":refs,"result":None},
          "created_at":now(),"updated_at":now()}
    Store(registry,ctx).task_create(task)
    return task


def observe(registry,ctx,task_id,records):
    task=get_task(registry,ctx,task_id)
    require(task["owner_id"]==ctx.user_id or (task["visibility"]=="project" and ctx.role=="user"),"ACCESS_DENIED","Only the author or an internal project user can advance this research.")
    require(task["status"]=="running","TASK_CLOSED","Research task is already closed.")
    require(all(task["visibility"]!="project" or r["visibility"]=="project" for r in records),"PRIVATE_DERIVATION","Shared tasks cannot ingest private records.")
    Store(registry,ctx).task_observe(task,records)


def finish(registry,ctx,task_id,candidates,review,check_scope,open_questions=""):
    task=get_task(registry,ctx,task_id)
    store=Store(registry,ctx)
    require(task["owner_id"]==ctx.user_id or (task["visibility"]=="project" and ctx.role=="user"),"ACCESS_DENIED","Only the author or an internal project user can finish this research.")
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
        refs=store.validate_refs(candidate["refs"],task["visibility"],research=True)
        require(refs,"EVIDENCE_REQUIRED","Each candidate needs at least one observed source.")
        require(all(task["payload"]["observed"].get(r["id"])==r["version"] for r in refs),"UNREAD_REFERENCE","Read or search each source within this task first.")
        prepared.append({**candidate,"refs":refs,"idea_id":new_id("idea")})
    result={"question":task["payload"]["question"],"candidates":prepared,"review":review,"check_scope":check_scope,"open_questions":open_questions}
    task=store.task_complete(task,result,prepared)
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
