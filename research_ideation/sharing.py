import hashlib
import sqlite3
from .models import require,now
from .storage import Store,public_record
from .permissions import can_edit


def publish(registry,ctx,record_id,expected_version):
    store=Store(registry,ctx)
    original=store.get(record_id)
    require(original["owner_id"]==ctx.user_id and original["visibility"]=="private","ACCESS_DENIED","Publish only your own private record.")
    require(original["version"]==expected_version,"VERSION_CONFLICT","Read the current record before publishing.")
    # Dependencies must already be shareable; publishing a report never publishes its inputs implicitly.
    refs=store.validate_refs(original["refs"],"project")
    published_id="published_"+hashlib.sha256(f"{record_id}:{expected_version}".encode()).hexdigest()[:32]
    attrs={**original["attributes"],"_origin_id":record_id,"_origin_version":expected_version,"published_at":now()}
    try:
        return public_record(store.create(original["kind"],original["title"],original["body"],"project",refs,attrs,record_id=published_id))
    except sqlite3.IntegrityError:
        return public_record(store.get(published_id))


def withdraw(registry,ctx,record_id,version):
    store=Store(registry,ctx)
    record=store.get(record_id)
    require(record["visibility"]=="project","INVALID_SCOPE","Withdraw a shared record.")
    # Refuse dangling shared derivations: users must withdraw dependants first.
    import json
    with store.db("project") as db:
        dependants=[r["id"] for r in db.execute("SELECT id,refs FROM records WHERE project_id=? AND deleted=0",(ctx.project_id,)) if any(ref["id"]==record_id for ref in json.loads(r["refs"]))]
    require(not dependants,"DEPENDANTS_EXIST","Withdraw shared dependent records before this source.")
    return public_record(store.update(record_id,version,deleted=1))
