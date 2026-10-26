"""A shared update is executed once per project/window, never once per user."""

from datetime import datetime,timedelta,timezone
import hashlib
import json
from ..adapters.arxiv import fetch
from ..models import require,now
from ..storage import Store,public_record


def update(registry,ctx,lookback_days=30,force=False):
    policy=registry.require_selected(ctx.user_id)
    require(ctx.role=="service" or ctx.user_id==policy["owner_id"],"ACCESS_DENIED","Use the selected research user or its configured service for paper collection.")
    require(type(lookback_days) is int and 1<=lookback_days<=365,"INVALID_INPUT","lookback_days must be 1..365.")
    project=registry.project(ctx.project_id)
    from zoneinfo import ZoneInfo
    date=datetime.now(ZoneInfo(project["timezone"])).date().isoformat()
    key=ctx.project_id+":"+date+":"+hashlib.sha256(project["query"].encode()).hexdigest()[:12]
    store=Store(registry,ctx)
    previous=store.batch_claim(key,force)
    if previous:return previous
    try:
        cutoff=datetime.now(timezone.utc)-timedelta(days=lookback_days)
        # Request a bounded, newest-first feed and filter dates locally. arXiv's
        # sort field is not assumed to be a supported search-field predicate.
        query=project["query"]
        papers=fetch(query,project["max_results"])
        retrieved_count=len(papers)
        cap=retrieved_count>=project["max_results"]
        papers=[p for p in papers if datetime.fromisoformat(p["updated"].replace("Z","+00:00"))>=cutoff]
        collected=[]
        for paper in papers:
            if not paper["title"] or not paper["abstract"]:
                continue
            # Versioned external id plus actual content prevents duplicate updates and preserves revisions.
            digest=hashlib.sha256(json.dumps(paper,sort_keys=True).encode()).hexdigest()
            paper_id="paper_"+digest[:32]
            attrs={**paper,"content_coverage":"abstract","content_hash":digest,"batch_key":key}
            record,created=store.create_once("paper",paper["title"],paper["abstract"],"project",attributes=attrs,record_id=paper_id,
                sources=[{"kind":"paper","uri":paper["url"],"sha256":digest,"coverage":"abstract","locator":"abstract"}])
            if created:collected.append(record)
        result={"batch_key":key,"project_id":ctx.project_id,"new_count":len(collected),"retrieved_count":retrieved_count,
                "papers":[public_record(r,False) for r in collected],"query":query,"lookback_days":lookback_days,"window_start":cutoff.isoformat(),
                "coverage":"arXiv metadata and abstracts; not full text.","possibly_truncated":cap,
                "warnings":["Result cap reached. Increase the limit or narrow the query before claiming full coverage."] if cap else [],
                "auto_explore":bool(project["auto_explore"]),"completed_at":now()}
        store.batch_finish(key,"completed",result)
        store.create("update","论文更新 "+date,json.dumps({k:v for k,v in result.items() if k!="papers"},ensure_ascii=False),"project",
                     refs=[{"id":r["id"],"version":r["version"]} for r in collected],attributes={"batch_key":key})
        return result
    except Exception as exc:
        store.batch_finish(key,"failed",{"error":getattr(exc,"code",type(exc).__name__)})
        raise
