"""以受控子进程复用 CRA 的 Python/数据模型，避免修改 Hermes 的依赖环境。"""

import json
import os
from pathlib import Path
import subprocess

from ..models import ResearchError, require
from ..permissions import revalidate
from ..records import TYPE_TO_KIND

PREFIX = "cra:"


class SharedContext:
    def __init__(self, registry, ctx):
        self.registry, self.ctx = registry, ctx
        path = registry.config.data_root / "control" / "shared-context.json"
        self.settings = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None

    @property
    def enabled(self):
        return bool(self.settings and self.settings["project_id"] == self.ctx.project_id)

    def call(self, operation, **values):
        revalidate(self.registry, self.ctx)
        require(self.enabled, "SHARED_CONTEXT_UNBOUND", "This project has no shared context binding.")
        payload = {"operation": operation, "project_id": self.ctx.project_id,
                   "user_id": self.ctx.user_id, "role": self.ctx.role, **values}
        env = dict(os.environ)
        env.pop("CRA_DATABASE_URL", None)
        env["PYTHONUTF8"] = "1"
        command = [self.settings["python"], "-X", "utf8", "-B", str(Path(__file__).with_name("pg_worker.py")),
                   self.settings["repository"], self.settings["env_file"]]
        try:
            result = subprocess.run(command, input=json.dumps(payload, ensure_ascii=False),
                                    text=True, encoding="utf-8", capture_output=True,
                                    env=env, timeout=60, cwd=self.settings["repository"])
            response = json.loads(result.stdout)
        except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
            raise ResearchError("SHARED_CONTEXT_UNAVAILABLE", "Shared database bridge unavailable; no local-only success reported.", True) from exc
        revalidate(self.registry, self.ctx)
        require(result.returncode == 0 and response.get("ok"), response.get("code", "SHARED_CONTEXT_ERROR"),
                response.get("message", "Shared database operation failed."))
        return response["data"]

    def normalize(self, document):
        fields = document.get("fields", {})
        metadata = fields.pop("_ri", {})
        sources = document.get("sources", [])
        return {"id": PREFIX + document["id"], "project_id": self.ctx.project_id,
                "kind": TYPE_TO_KIND[document["type"]], "title": document["title"],
                "body": document["body"], "owner_id": document["created_by"],
                "visibility": "project", "version": document["version"], "status": document["status"],
                "fields": fields, "refs": [{"id": PREFIX + link["target_id"], "version": link.get("version", 1),
                                               "quote": link.get("quote", "")} for link in document.get("links", [])],
                "sources": sources, "attributes": {"backend": "cra", "native_id": document["id"],
                    "confirmed_by": document.get("confirmed_by"), "provenance": metadata,
                    "native_links":document.get("links",[])},
                "created_at": document["created_at"], "updated_at": document["updated_at"], "deleted": 0}

    def search(self, query, kind, limit):
        if not self.enabled:
            return []
        if kind is not None and kind not in {"idea", *TYPE_TO_KIND}:
            return []
        return [self.normalize(doc) for doc in self.call("search", query=query, kind=kind, limit=limit)]

    def read(self, record_id, version=None):
        return self.normalize(self.call("read", record_id=record_id.removeprefix(PREFIX), version=version))
