import hashlib
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
    sources=[{key:value for key,value in source.items() if key in {"kind","uri","locator","sha256","coverage"} and value is not None} for source in original.get("sources",[])]
    record,_=store.create_once(original["kind"],original["title"],original["body"],"project",refs,attrs,
                               record_id=published_id,fields=original.get("fields"),sources=sources)
    result=public_record(record)
    if store.shared.enabled and original["kind"] in {"idea","proposal","experience","experiment","decision","diagnosis","online"}:
        result["shared_context"]=store.export_shared(record)
    return result


def withdraw(registry,ctx,record_id,version):
    store=Store(registry,ctx)
    if record_id.startswith("cra:"):
        require(not store.dependants(record_id),"DEPENDANTS_EXIST","Withdraw local shared dependants first.")
        return store.withdraw_remote(record_id,version)
    record=store.get(record_id)
    require(record["visibility"]=="project","INVALID_SCOPE","Withdraw a shared record.")
    # Refuse dangling shared derivations: users must withdraw dependants first.
    dependants=store.dependants(record_id)
    require(not dependants,"DEPENDANTS_EXIST","Withdraw shared dependent records before this source.")
    can_edit(registry,ctx,record)
    require(record["version"]==version,"VERSION_CONFLICT","Read the current record before withdrawing.")
    exported=store.export_for(record_id)
    if exported:
        store.withdraw_remote(exported["remote_id"],exported["remote_version"])
    return public_record(store.update(record_id,version,deleted=1))
