"""SQLite v1 → v2：保留已有记录，补审核字段与规范化来源、引用、审计表。"""

import json

VERSION = 2
EXTRA_SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
 id TEXT PRIMARY KEY,uri TEXT NOT NULL,kind TEXT NOT NULL,sha256 TEXT,coverage TEXT,
 owner_id TEXT NOT NULL,project_id TEXT NOT NULL,visibility TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS record_sources (
 record_id TEXT NOT NULL,source_id TEXT NOT NULL,locator TEXT NOT NULL,
 PRIMARY KEY(record_id,source_id,locator));
CREATE TABLE IF NOT EXISTS record_links (
 src_id TEXT NOT NULL,dst_id TEXT NOT NULL,dst_version INTEGER NOT NULL,quote TEXT NOT NULL,
 relation TEXT NOT NULL DEFAULT 'cites',PRIMARY KEY(src_id,dst_id,dst_version));
CREATE TABLE IF NOT EXISTS record_revisions (
 record_id TEXT NOT NULL,version INTEGER NOT NULL,action TEXT NOT NULL,actor TEXT NOT NULL,
 at TEXT NOT NULL,snapshot TEXT NOT NULL,PRIMARY KEY(record_id,version));
CREATE TABLE IF NOT EXISTS shared_exports (
 local_id TEXT PRIMARY KEY,remote_id TEXT NOT NULL,remote_version INTEGER NOT NULL,status TEXT NOT NULL);
"""


def migrate(db):
    version = db.execute("PRAGMA user_version").fetchone()[0]
    if version >= VERSION:
        return
    db.execute("BEGIN IMMEDIATE")
    try:
        columns = {row[1] for row in db.execute("PRAGMA table_info(records)")}
        if "status" not in columns:
            db.execute("ALTER TABLE records ADD COLUMN status TEXT NOT NULL DEFAULT 'draft'")
        if "fields" not in columns:
            db.execute("ALTER TABLE records ADD COLUMN fields TEXT NOT NULL DEFAULT '{}'")
        for statement in EXTRA_SCHEMA.split(";"):
            if statement.strip():
                db.execute(statement)
        for row in db.execute("SELECT record_id,version,snapshot FROM history").fetchall():
            data = json.loads(row["snapshot"])
            db.execute("INSERT OR IGNORE INTO record_revisions VALUES(?,?,?,?,?,?)",
                       (row["record_id"], row["version"], "legacy_snapshot", data["owner_id"],
                        data["updated_at"], row["snapshot"]))
            for ref in data.get("refs", []):
                if row["version"] == db.execute("SELECT version FROM records WHERE id=?", (row["record_id"],)).fetchone()[0]:
                    db.execute("INSERT OR IGNORE INTO record_links(src_id,dst_id,dst_version,quote) VALUES(?,?,?,?)",
                               (row["record_id"],ref["id"],ref["version"],ref.get("quote", "")))
        db.execute("PRAGMA user_version=2")
        db.commit()
    except Exception:
        db.rollback()
        raise
