"""Per-profile private DBs and project DBs, with no unscoped runtime query API."""

from contextlib import contextmanager
import json
import sqlite3
import time
from ..artifacts import Artifacts, contained
from ..models import require, new_id, now, bounded_text, RECORD_KINDS, identifier
from ..permissions import can_read, can_edit, revalidate, write_scope
from ..records import validate_fields, normalize_sources, STATUSES
from .migrations import migrate


SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
 id TEXT PRIMARY KEY,project_id TEXT NOT NULL,kind TEXT NOT NULL,title TEXT NOT NULL,
 body TEXT NOT NULL,owner_id TEXT NOT NULL,visibility TEXT NOT NULL,version INTEGER NOT NULL,
 refs TEXT NOT NULL,attributes TEXT NOT NULL,deleted INTEGER NOT NULL DEFAULT 0,
 created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS history (
 record_id TEXT NOT NULL,version INTEGER NOT NULL,snapshot TEXT NOT NULL,
 PRIMARY KEY(record_id,version));
CREATE TABLE IF NOT EXISTS tasks (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL,owner_id TEXT NOT NULL,visibility TEXT NOT NULL,
 kind TEXT NOT NULL, status TEXT NOT NULL,payload TEXT NOT NULL,
 created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS batches (
 batch_key TEXT PRIMARY KEY,status TEXT NOT NULL,payload TEXT NOT NULL,updated_at TEXT NOT NULL);
"""


def open_database(path):
    """WAL transitions may return SQLITE_BUSY immediately during first-open races.

    Close failed initializers before retrying; otherwise Windows retains a file
    handle and the losing initializer can itself keep the winner locked.
    """
    for attempt in range(12):
        db=None
        try:
            db=sqlite3.connect(path,timeout=30)
            db.row_factory=sqlite3.Row
            if db.execute("PRAGMA journal_mode").fetchone()[0].lower()!="wal":
                db.execute("PRAGMA journal_mode=WAL").fetchone()
            if db.execute("PRAGMA user_version").fetchone()[0]==0:
                db.executescript(SCHEMA)
            migrate(db)
            return db
        except Exception as exc:
            if db is not None:
                db.close()
            if isinstance(exc,sqlite3.OperationalError) and any(word in str(exc).lower() for word in ("locked","busy")) and attempt<11:
                time.sleep(0.03*(attempt+1))
                continue
            raise


class LocalStore:
    def __init__(self,registry,ctx):
        self.registry,self.ctx = registry,ctx
        self.artifacts = Artifacts(registry,ctx)

    @contextmanager
    def db(self,visibility,write=False):
        revalidate(self.registry,self.ctx)
        if write:
            write_scope(self.registry,self.ctx,visibility)
        path = contained(self.artifacts.root(visibility),"records.sqlite")
        path.parent.mkdir(parents=True,exist_ok=True)
        db = open_database(path)
        try:
            if write:
                db.execute("BEGIN IMMEDIATE")
            yield db
            if write:
                revalidate(self.registry,self.ctx)
                db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @property
    def scopes(self):
        return ["project"] if self.ctx.role == "service" else ["private","project"]

    @staticmethod
    def decode(row):
        record = dict(row)
        for key in ("refs","attributes"):
            record[key] = json.loads(record[key])
        record["status"] = record.get("status", "draft")
        record["fields"] = json.loads(record.get("fields", "{}"))
        return record

    def get(self,record_id):
        for scope in self.scopes:
            with self.db(scope) as db:
                row = db.execute("SELECT * FROM records WHERE id=? AND project_id=? AND deleted=0",(record_id,self.ctx.project_id)).fetchone()
            if row:
                record = self.decode(row)
                require(can_read(self.registry,self.ctx,record),"NOT_FOUND","Record not found.")
                return record
        require(False,"NOT_FOUND","Record not found.")

    def list(self,kind=None,query="",limit=30):
        require(type(limit) is int and 1 <= limit <= 100,"INVALID_INPUT","limit must be 1..100.")
        import re
        terms = [t.lower() for t in re.findall(r"[\w-]+",query) if t][:12]
        results=[]
        for scope in self.scopes:
            sql="SELECT * FROM records WHERE project_id=? AND deleted=0"
            args=[self.ctx.project_id]
            if kind:
                sql+=" AND kind=?"; args.append(kind)
            if scope == "private":
                sql+=" AND owner_id=?"; args.append(self.ctx.user_id)
            # Apply authorization scope before bounded matching, never fetch other profiles.
            with self.db(scope) as db:
                rows=db.execute(sql+" ORDER BY updated_at DESC LIMIT 1000",args).fetchall()
            for row in rows:
                item=self.decode(row)
                text=(item["title"]+" "+item["body"]).lower()
                score=sum(t in text for t in terms)
                if (not terms or score) and can_read(self.registry,self.ctx,item):
                    results.append((score,item))
        results.sort(key=lambda pair:(pair[0],pair[1]["updated_at"]),reverse=True)
        return [item for _,item in results[:limit]]

    def get_version(self,record_id,version):
        current=self.get(record_id)  # Revocation/deletion applies even to historical versions.
        require(type(version) is int and version>=1,"INVALID_REFERENCE","Version must be a positive integer.")
        if current["version"]==version:
            return current
        with self.db(current["visibility"]) as db:
            row=db.execute("SELECT snapshot FROM history WHERE record_id=? AND version=?",(record_id,version)).fetchone()
        require(row,"NOT_FOUND","Record version not found.")
        record=json.loads(row["snapshot"])
        record.setdefault("status", "draft");record.setdefault("fields", {})
        return record

    def validate_refs(self,refs,visibility):
        require(isinstance(refs,list) and len(refs)<=50,"INVALID_INPUT","refs must be an array of at most 50 references.")
        clean=[]
        for ref in refs:
            require(isinstance(ref,dict) and set(ref)<= {"id","version","quote"} and {"id","version"}<=set(ref),"INVALID_REFERENCE","Each reference needs id and version; quote is optional.")
            record=self.get_version(ref["id"],ref["version"])
            require(visibility!="project" or record["visibility"]=="project","PRIVATE_DERIVATION","A shared result cannot cite private input. Rework with shared inputs or authorize the source first.")
            quote=ref.get("quote","")
            require(isinstance(quote,str) and len(quote)<=2000 and (not quote or quote in record["body"]),"INVALID_REFERENCE","Quoted evidence must occur verbatim in the referenced record.")
            clean.append({"id":record["id"],"version":record["version"],"quote":quote})
        return clean

    def create(self,kind,title,body,visibility="private",refs=None,attributes=None,record_id=None,fields=None,sources=None):
        record,sources=self.prepare_record(kind,title,body,visibility,refs,attributes,record_id,fields,sources)
        with self.db(visibility,write=True) as db:
            self.insert_record(db,record,sources)
        return record

    def prepare_record(self,kind,title,body,visibility="private",refs=None,attributes=None,record_id=None,fields=None,sources=None):
        if record_id is not None:identifier(record_id)
        require(kind in RECORD_KINDS,"INVALID_INPUT","Unknown record kind.")
        bounded_text(title,"title",500); bounded_text(body,"body")
        refs=self.validate_refs(refs or [],visibility)
        require(isinstance(attributes or {},dict),"INVALID_INPUT","attributes must be an object.")
        fields=validate_fields(kind,fields or {})
        sources=normalize_sources(sources or [])
        timestamp=now()
        record={"id":record_id or new_id(kind),"project_id":self.ctx.project_id,"kind":kind,"title":title,"body":body,
                "owner_id":self.ctx.user_id,"visibility":visibility,"version":1,"refs":refs,
                "attributes":attributes or {},"deleted":0,"created_at":timestamp,"updated_at":timestamp,
                "status":"draft","fields":fields}
        return record,sources

    def import_drafts(self,items):
        require(isinstance(items,list) and 1<=len(items)<=100,"INVALID_INPUT","Import 1..100 records.")
        prepared=[self.prepare_record(**item) for item in items]
        require(len({record["visibility"] for record,_ in prepared})==1,"INVALID_INPUT","One import has one visibility scope.")
        require(len({record["id"] for record,_ in prepared})==len(prepared),"INVALID_INPUT","Duplicate record IDs in input.")
        with self.db(prepared[0][0]["visibility"],write=True) as db:
            for record,sources in prepared:
                require(not db.execute("SELECT 1 FROM records WHERE id=?",(record["id"],)).fetchone(),"DUPLICATE_RECORD","Import cannot overwrite an existing record.")
                self.insert_record(db,record,sources)
        return [record for record,_ in prepared]

    def insert_record(self,db,record,sources=None):
        columns=list(record)
        db.execute("INSERT INTO records ("+",".join(columns)+") VALUES("+",".join("?" for _ in columns)+")",
                   tuple(json.dumps(record[k],ensure_ascii=False) if k in {"refs","attributes","fields"} else record[k] for k in columns))
        self.audit(db,record,"create")
        for ref in record["refs"]:
            db.execute("INSERT OR IGNORE INTO record_links(src_id,dst_id,dst_version,quote) VALUES(?,?,?,?)",
                       (record["id"],ref["id"],ref["version"],ref.get("quote","")))
        for source in sources or []:
            import hashlib
            source_id="source_"+hashlib.sha256(json.dumps([record["project_id"],record["owner_id"],record["visibility"],source["uri"],source.get("sha256")]).encode()).hexdigest()[:32]
            db.execute("INSERT OR IGNORE INTO sources VALUES(?,?,?,?,?,?,?,?)",
                       (source_id,source["uri"],source["kind"],source.get("sha256"),source.get("coverage"),record["owner_id"],record["project_id"],record["visibility"]))
            db.execute("INSERT INTO record_sources VALUES(?,?,?)",(record["id"],source_id,source.get("locator","")))

    def audit(self,db,record,action):
        snapshot=json.dumps(record,ensure_ascii=False)
        db.execute("INSERT INTO history VALUES(?,?,?)",(record["id"],record["version"],snapshot))
        db.execute("INSERT INTO record_revisions VALUES(?,?,?,?,?,?)",
                   (record["id"],record["version"],action,self.ctx.user_id,record["updated_at"],snapshot))

    def sources_for(self,record):
        require(can_read(self.registry,self.ctx,record),"ACCESS_DENIED","Source access denied.")
        with self.db(record["visibility"]) as db:
            rows=db.execute("SELECT s.*,rs.locator FROM sources s JOIN record_sources rs ON rs.source_id=s.id WHERE rs.record_id=?",(record["id"],)).fetchall()
        if not rows and record["kind"]=="paper" and record["attributes"].get("url"):
            attributes=record["attributes"]
            return [{"kind":"paper","uri":attributes["url"],"sha256":attributes.get("content_hash"),
                     "coverage":attributes.get("content_coverage","abstract"),"locator":"abstract"}]
        return [dict(row) for row in rows]

    def update(self,record_id,expected_version,**changes):
        old=self.get(record_id)
        can_edit(self.registry,self.ctx,old)
        require(type(expected_version) is int,"VERSION_REQUIRED","Provide the version you read.")
        require(set(changes)<={"title","body","attributes","deleted","fields"},"INVALID_INPUT","Unsupported update.")
        record={**old,**changes,"version":old["version"]+1,"updated_at":now()}
        if set(changes)&{"title","body","fields"}:record["status"]="draft"
        validate_fields(record["kind"],record["fields"])
        bounded_text(record["title"],"title",500);bounded_text(record["body"],"body")
        with self.db(old["visibility"],write=True) as db:
            changed=db.execute("UPDATE records SET title=?,body=?,attributes=?,deleted=?,version=?,updated_at=?,status=?,fields=? WHERE id=? AND version=? AND project_id=?",
                (record["title"],record["body"],json.dumps(record["attributes"],ensure_ascii=False),record["deleted"],record["version"],record["updated_at"],record["status"],json.dumps(record["fields"],ensure_ascii=False),record_id,expected_version,self.ctx.project_id)).rowcount
            require(changed==1,"VERSION_CONFLICT","The record changed; read and merge before retrying.")
            self.audit(db,record,"withdraw" if record["deleted"] else "update")
        return record

    def review(self,record_id,version,status,fields=None):
        record=self.get(record_id);can_edit(self.registry,self.ctx,record)
        require(status in STATUSES and status!="draft","INVALID_INPUT","Use confirmed, rejected or superseded.")
        require(record["version"]==version,"VERSION_CONFLICT","Read the current record first.")
        allowed={"draft":{"confirmed","rejected"},"confirmed":{"superseded"},"rejected":set(),"superseded":set()}
        require(status in allowed[record["status"]],"INVALID_TRANSITION","Invalid review transition.")
        if status=="superseded":require(not self.dependants(record_id,record["visibility"]),"DEPENDANTS_EXIST","Supersede dependant records first.")
        if fields is not None:
            require(isinstance(fields,dict),"INVALID_INPUT","Review fields must be an object.")
            record["fields"]=validate_fields(record["kind"],{**record["fields"],**fields})
        if status=="confirmed":
            validate_fields(record["kind"],record["fields"],complete=True)
            require(record["refs"] or self.sources_for(record),"EVIDENCE_REQUIRED","A confirmed record needs sources or references.")
        record={**record,"status":status,"version":version+1,"updated_at":now()}
        with self.db(record["visibility"],write=True) as db:
            changed=db.execute("UPDATE records SET status=?,version=?,updated_at=?,fields=? WHERE id=? AND version=?",
                               (status,version+1,record["updated_at"],json.dumps(record["fields"],ensure_ascii=False),record_id,version)).rowcount
            require(changed==1,"VERSION_CONFLICT","Record changed during review.")
            self.audit(db,record,status)
        return record

    def dependants(self,record_id,scope="project"):
        with self.db(scope) as db:
            return [r["id"] for r in db.execute("SELECT id,refs FROM records WHERE project_id=? AND deleted=0",(self.ctx.project_id,))
                    if any(ref["id"]==record_id for ref in json.loads(r["refs"]))]

    def save_export(self,record_id,result):
        with self.db("project",write=True) as db:
            db.execute("INSERT INTO shared_exports VALUES(?,?,?,?) ON CONFLICT(local_id) DO UPDATE SET remote_id=excluded.remote_id,remote_version=excluded.remote_version,status=excluded.status",
                       (record_id,result["id"],result["version"],result["status"]))

    def export_for(self,record_id):
        with self.db("project") as db:
            row=db.execute("SELECT * FROM shared_exports WHERE local_id=?",(record_id,)).fetchone()
        return dict(row) if row else None

    def task_get(self,task_id):
        for scope in self.scopes:
            with self.db(scope) as db:
                row=db.execute("SELECT * FROM tasks WHERE id=? AND project_id=?",(task_id,self.ctx.project_id)).fetchone()
            if row and (row["owner_id"]==self.ctx.user_id or scope=="project"):
                task=dict(row);task["payload"]=json.loads(task["payload"])
                return task
        require(False,"NOT_FOUND","Task not found.")

    def task_create(self,task):
        with self.db(task["visibility"],write=True) as db:
            db.execute("INSERT INTO tasks VALUES(?,?,?,?,?,?,?,?,?)",tuple(json.dumps(task[k],ensure_ascii=False) if k=="payload" else task[k] for k in task))

    def task_observe(self,task,records):
        with self.db(task["visibility"],write=True) as db:
            latest=db.execute("SELECT status,payload FROM tasks WHERE id=?",(task["id"],)).fetchone()
            require(latest and latest["status"]=="running","TASK_CLOSED","Research task is closed.")
            payload=json.loads(latest["payload"])
            payload["observed"].update({r["id"]:r["version"] for r in records})
            db.execute("UPDATE tasks SET payload=?,updated_at=? WHERE id=?",(json.dumps(payload,ensure_ascii=False),now(),task["id"]))

    def task_complete(self,task,result,prepared):
        timestamp=now()
        with self.db(task["visibility"],write=True) as db:
            latest=db.execute("SELECT status,payload FROM tasks WHERE id=?",(task["id"],)).fetchone()
            if latest["status"] in {"completed","no_candidate"}:
                task["payload"]=json.loads(latest["payload"]);task["status"]=latest["status"]
                return task
            require(latest["status"]=="running","TASK_CLOSED","Task is closed.")
            for candidate in prepared:
                body="\n\n".join(f"## {key}\n{candidate[key]}" for key in ("hypothesis","method","related_work","experiment","risks"))
                fields={"bottleneck":task["payload"]["question"],"change":candidate["method"],
                        "hypothesis":candidate["hypothesis"],"related_work":candidate["related_work"],
                        "experiment":candidate["experiment"],"risks":candidate["risks"],
                        "adopted":None,"adoption_reason":None}
                record={"id":candidate["idea_id"],"project_id":self.ctx.project_id,"kind":"idea","title":candidate["title"],"body":body,
                        "owner_id":self.ctx.user_id,"visibility":task["visibility"],"version":1,"refs":candidate["refs"],
                        "attributes":{"task_id":task["id"],"check_scope":result["check_scope"]},"deleted":0,"created_at":timestamp,"updated_at":timestamp,
                        "status":"draft","fields":fields}
                self.insert_record(db,record)
            payload=json.loads(latest["payload"]);payload["result"]=result
            task.update(status="completed" if prepared else "no_candidate",payload=payload,updated_at=timestamp)
            db.execute("UPDATE tasks SET status=?,payload=?,updated_at=? WHERE id=?",(task["status"],json.dumps(payload,ensure_ascii=False),timestamp,task["id"]))
        return task

    def batch_claim(self,key,force=False):
        from datetime import datetime,timedelta,timezone
        with self.db("project",write=True) as db:
            previous=db.execute("SELECT * FROM batches WHERE batch_key=?",(key,)).fetchone()
            if previous and previous["status"]=="completed" and not force:
                return {**json.loads(previous["payload"]),"already_completed":True}
            if previous and previous["status"]=="running":
                require(datetime.now(timezone.utc)-datetime.fromisoformat(previous["updated_at"])>timedelta(minutes=10),
                        "UPDATE_BUSY","This project's update is already running.")
            db.execute("INSERT INTO batches VALUES(?,?,?,?) ON CONFLICT(batch_key) DO UPDATE SET status=excluded.status,payload=excluded.payload,updated_at=excluded.updated_at",
                       (key,"running","{}",now()))
        return None

    def batch_finish(self,key,status,payload):
        with self.db("project",write=True) as db:
            db.execute("UPDATE batches SET status=?,payload=?,updated_at=? WHERE batch_key=?",(status,json.dumps(payload,ensure_ascii=False),now(),key))


def public_record(record,full=True):
    result={k:v for k,v in record.items() if k not in {"deleted"}}
    result["attributes"]={k:v for k,v in result["attributes"].items() if not k.startswith("_")}
    if not full:
        result["body"]=result["body"][:700]
        result["truncated"]=len(record["body"])>700
    return result
