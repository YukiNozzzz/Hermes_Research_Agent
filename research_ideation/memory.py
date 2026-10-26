from .storage import Store,public_record
from .projects import describe
from .models import require


def snapshot(registry,ctx):
    store=Store(registry,ctx)
    kinds=("problem","decision","experiment","experience","note","idea","feedback","update")
    return {"project":describe(registry,ctx),"profile":ctx.profile,
            "records":{kind:[public_record(r,False) for r in store.list(kind=kind,limit=15)] for kind in kinds},
            "coverage":"Latest 15 visible entries per kind; retrieve individual records for complete evidence."}


def record(registry,ctx,title,body,kind="note",visibility="private",refs=None,record_id=None,version=None):
    require(kind in {"note","experience","problem","experiment","decision"},"INVALID_INPUT","Use the dedicated task/feedback workflow for generated ideas.")
    store=Store(registry,ctx)
    if record_id:
        return public_record(store.update(record_id,version,title=title,body=body))
    return public_record(store.create(kind,title,body,visibility,refs))
