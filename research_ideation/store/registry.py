"""Administrator-owned identity registry. Runtime connections are read-only."""

from contextlib import contextmanager
from pathlib import Path
import sqlite3
from ..models import identifier, require, now, bounded_text


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
 user_id TEXT PRIMARY KEY, profile TEXT UNIQUE NOT NULL, home TEXT UNIQUE NOT NULL,
 kind TEXT NOT NULL CHECK(kind IN ('user','service')), active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS projects (
 project_id TEXT PRIMARY KEY, title TEXT NOT NULL, brief TEXT NOT NULL, query TEXT NOT NULL,
 timezone TEXT NOT NULL DEFAULT 'Asia/Shanghai', daily_time TEXT NOT NULL DEFAULT '10:00',
 max_results INTEGER NOT NULL DEFAULT 10, auto_explore INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS members (
 project_id TEXT NOT NULL, user_id TEXT NOT NULL, role TEXT NOT NULL,
 PRIMARY KEY(project_id,user_id), FOREIGN KEY(project_id) REFERENCES projects,
 FOREIGN KEY(user_id) REFERENCES users);
CREATE TABLE IF NOT EXISTS bindings (
 platform TEXT NOT NULL, account TEXT NOT NULL, tenant TEXT NOT NULL, sender TEXT NOT NULL,
 user_id TEXT NOT NULL, PRIMARY KEY(platform,account,tenant,sender), FOREIGN KEY(user_id) REFERENCES users);
CREATE TABLE IF NOT EXISTS schedules (
 project_id TEXT PRIMARY KEY, job_id TEXT NOT NULL, created_at TEXT NOT NULL);
"""


class Registry:
    def __init__(self, config):
        self.config = config

    @contextmanager
    def connection(self, admin=False):
        path = self.config.registry_path
        if admin:
            path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(path, timeout=20)
        else:
            require(path.is_file(), "SETUP_REQUIRED", "The administrator must initialize the research registry first.")
            connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=20)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            yield connection
            if admin:
                connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self):
        with self.connection(admin=True) as db:
            db.executescript(SCHEMA)

    def add_user(self, user_id, profile, home, kind="user"):
        identifier(user_id); identifier(profile)
        require(profile != "default", "INVALID_PROFILE", "The default profile cannot be a research user.")
        require(kind in {"user", "service"}, "INVALID_INPUT", "Unknown user kind.")
        home = Path(home).expanduser().resolve()
        require(home.is_dir() and (home / "config.yaml").is_file(), "PROFILE_MISSING", "Create a real Hermes profile first.")
        with self.connection(admin=True) as db:
            db.execute("INSERT INTO users VALUES (?,?,?,?,1)", (user_id, profile, str(home), kind))

    def user(self, profile, home):
        with self.connection() as db:
            row = db.execute("SELECT * FROM users WHERE profile=? AND active=1", (profile,)).fetchone()
        require(row and Path(row["home"]).resolve() == Path(home).resolve(), "IDENTITY_DENIED", "Unregistered, disabled, or mismatched profile.")
        return dict(row)

    def member(self, user_id, project_id):
        with self.connection() as db:
            row = db.execute("SELECT m.role FROM members m JOIN users u USING(user_id) WHERE m.user_id=? AND m.project_id=? AND u.active=1", (user_id, project_id)).fetchone()
        require(row, "ACCESS_DENIED", "No active membership for this project.")
        return row["role"]

    def project(self, project_id):
        identifier(project_id)
        with self.connection() as db:
            row = db.execute("SELECT * FROM projects WHERE project_id=?", (project_id,)).fetchone()
        require(row, "NOT_FOUND", "Project not found.")
        return dict(row)

    def project_ids(self, user_id):
        with self.connection() as db:
            return [r[0] for r in db.execute("SELECT project_id FROM members WHERE user_id=? ORDER BY project_id", (user_id,))]

    def add_project(self, project_id, title, brief, query, daily_time="10:00", timezone="Asia/Shanghai"):
        from zoneinfo import ZoneInfo
        import re
        identifier(project_id); bounded_text(title, "title", 300); bounded_text(brief, "brief")
        bounded_text(query, "query", 2000)
        require(re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", daily_time), "INVALID_TIME", "Use HH:MM.")
        ZoneInfo(timezone)
        with self.connection(admin=True) as db:
            db.execute("INSERT INTO projects(project_id,title,brief,query,daily_time,timezone) VALUES(?,?,?,?,?,?)", (project_id,title,brief,query,daily_time,timezone))

    def set_member(self, project_id, user_id, role):
        require(role in {"owner", "editor", "reader", "service"}, "INVALID_ROLE", "Unknown project role.")
        with self.connection(admin=True) as db:
            user = db.execute("SELECT kind FROM users WHERE user_id=?", (user_id,)).fetchone()
            require(user and ((role == "service") == (user["kind"] == "service")), "INVALID_ROLE", "Service roles require a service identity, and vice versa.")
            db.execute("INSERT INTO members VALUES(?,?,?) ON CONFLICT(project_id,user_id) DO UPDATE SET role=excluded.role", (project_id,user_id,role))

    def revoke(self, project_id, user_id):
        with self.connection(admin=True) as db:
            db.execute("DELETE FROM members WHERE project_id=? AND user_id=?", (project_id,user_id))

    def disable(self, user_id):
        with self.connection(admin=True) as db:
            db.execute("UPDATE users SET active=0 WHERE user_id=?", (user_id,))

    def bind(self, platform, account, tenant, sender, user_id):
        for name, value in (("platform",platform),("account",account),("sender",sender)):
            bounded_text(value,name,300)
        with self.connection(admin=True) as db:
            db.execute("INSERT INTO bindings VALUES(?,?,?,?,?)", (platform,account,tenant,sender,user_id))

    def binding(self, platform, account, tenant, sender):
        with self.connection() as db:
            row = db.execute("SELECT u.* FROM bindings b JOIN users u USING(user_id) WHERE platform=? AND account=? AND tenant=? AND sender=? AND active=1", (platform,account,tenant,sender)).fetchone()
        require(row, "IDENTITY_DENIED", "No verified channel binding.")
        return dict(row)

    def inspect(self):
        with self.connection() as db:
            return {table:[dict(r) for r in db.execute(f"SELECT * FROM {table}")] for table in ("users","projects","members","bindings","schedules")}

    def schedule_for(self,project_id):
        with self.connection() as db:
            row=db.execute("SELECT job_id FROM schedules WHERE project_id=?",(project_id,)).fetchone()
        return dict(row) if row else None

    def save_schedule(self,project_id,job_id):
        with self.connection(admin=True) as db:
            db.execute("INSERT INTO schedules VALUES(?,?,?)",(project_id,job_id,now()))

    def set_auto_explore(self,project_id,enabled):
        with self.connection(admin=True) as db:
            changed=db.execute("UPDATE projects SET auto_explore=? WHERE project_id=?",(int(enabled),project_id)).rowcount
            require(changed==1,"NOT_FOUND","Project not found.")
