from .storage import Store,public_record
from .tasks import observe


def search(registry,ctx,query,kind=None,limit=10,task_id=None):
    records=Store(registry,ctx).list(kind=kind,query=query,limit=limit)
    if task_id:
        observe(registry,ctx,task_id,records)
    return {"records":[public_record(r,False) for r in records],"coverage":"Simple keyword OR ranking over latest 1000 accessible records per scope; not an exhaustive novelty search."}


def read(registry,ctx,record_id,task_id=None,version=None):
    if isinstance(record_id,str) and record_id.startswith("task_"):
        from .tasks import get_task
        return get_task(registry,ctx,record_id)
    store=Store(registry,ctx)
    record=store.get_version(record_id,version) if version is not None else store.get(record_id)
    if task_id:
        observe(registry,ctx,task_id,[record])
    return public_record(record)
