from .storage import Store,public_record
from .projects import describe
from .models import require
from .records import HUMAN_FIELDS,KIND_TO_TYPE


def snapshot(registry,ctx,research=False):
    store=Store(registry,ctx)
    kinds=("problem","decision","experiment","experience","note","idea","feedback","update","online","diagnosis")
    return {"project":describe(registry,ctx),"profile":ctx.profile,
            "records":{kind:[public_record(r,False) for r in store.list(kind=kind,limit=15,research=research)] for kind in kinds},
            "coverage":"Latest 15 visible entries per kind; retrieve individual records for complete evidence."}


def record(registry,ctx,title,body,kind="note",visibility="private",refs=None,record_id=None,version=None,fields=None,sources=None):
    require(kind in {"note","experience","problem","experiment","decision"},"INVALID_INPUT","Use the dedicated task/feedback workflow for generated ideas.")
    store=Store(registry,ctx)
    actual_kind=store.get(record_id)["kind"] if record_id else kind
    require(actual_kind in {"note","experience","problem","experiment","decision"},"INVALID_INPUT","Use the dedicated workflow for this record type.")
    if fields:
        human=HUMAN_FIELDS.get(KIND_TO_TYPE.get(actual_kind),set())
        require(not any(key in fields and fields[key] is not None for key in human),"HUMAN_REVIEW_REQUIRED","Human judgement fields must be supplied through the administrator review command.")
    if record_id:
        changes={"title":title,"body":body}
        if fields is not None:changes["fields"]=fields
        return public_record(store.update(record_id,version,**changes))
    return public_record(store.create(kind,title,body,visibility,refs,fields=fields,sources=sources))
