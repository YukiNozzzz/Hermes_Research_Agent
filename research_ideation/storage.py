"""Per-profile private DBs and project DBs, with no unscoped runtime query API."""

from contextlib import contextmanager
import json
import sqlite3
import time
from .artifacts import Artifacts, contained
from .models import require, new_id, now, bounded_text, RECORD_KINDS
from .permissions import can_read, can_edit, revalidate, write_scope


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
            if db.execute("PRAGMA user_version").fetchone()[0]!=1:
                db.executescript(SCHEMA+"\nPRAGMA user_version=1;")
            return db
        except Exception as exc:
            if db is not None:
                db.close()
            if isinstance(exc,sqlite3.OperationalError) and any(word in str(exc).lower() for word in ("locked","busy")) and attempt<11:
                time.sleep(0.03*(attempt+1))
                continue
            raise


class Store:
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
        return json.loads(row["snapshot"])

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

    def create(self,kind,title,body,visibility="private",refs=None,attributes=None,record_id=None):
        require(kind in RECORD_KINDS,"INVALID_INPUT","Unknown record kind.")
        bounded_text(title,"title",500); bounded_text(body,"body")
        refs=self.validate_refs(refs or [],visibility)
        require(isinstance(attributes or {},dict),"INVALID_INPUT","attributes must be an object.")
        timestamp=now()
        record={"id":record_id or new_id(kind),"project_id":self.ctx.project_id,"kind":kind,"title":title,"body":body,
                "owner_id":self.ctx.user_id,"visibility":visibility,"version":1,"refs":refs,
                "attributes":attributes or {},"deleted":0,"created_at":timestamp,"updated_at":timestamp}
        with self.db(visibility,write=True) as db:
            db.execute("INSERT INTO records VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",tuple(json.dumps(record[k],ensure_ascii=False) if k in {"refs","attributes"} else record[k] for k in record))
            db.execute("INSERT INTO history VALUES(?,?,?)",(record["id"],1,json.dumps(record,ensure_ascii=False)))
        return record

    def update(self,record_id,expected_version,**changes):
        old=self.get(record_id)
        can_edit(self.registry,self.ctx,old)
        require(type(expected_version) is int,"VERSION_REQUIRED","Provide the version you read.")
        require(set(changes)<={"title","body","attributes","deleted"},"INVALID_INPUT","Unsupported update.")
        record={**old,**changes,"version":old["version"]+1,"updated_at":now()}
        bounded_text(record["title"],"title",500);bounded_text(record["body"],"body")
        with self.db(old["visibility"],write=True) as db:
            changed=db.execute("UPDATE records SET title=?,body=?,attributes=?,deleted=?,version=?,updated_at=? WHERE id=? AND version=? AND project_id=?",
                (record["title"],record["body"],json.dumps(record["attributes"],ensure_ascii=False),record["deleted"],record["version"],record["updated_at"],record_id,expected_version,self.ctx.project_id)).rowcount
            require(changed==1,"VERSION_CONFLICT","The record changed; read and merge before retrying.")
            db.execute("INSERT INTO history VALUES(?,?,?)",(record_id,record["version"],json.dumps(record,ensure_ascii=False)))
        return record


def public_record(record,full=True):
    result={k:v for k,v in record.items() if k not in {"deleted"}}
    result["attributes"]={k:v for k,v in result["attributes"].items() if not k.startswith("_")}
    if not full:
        result["body"]=result["body"][:700]
        result["truncated"]=len(record["body"])>700
    return result
