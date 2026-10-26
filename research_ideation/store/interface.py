"""按权限合并本地私有记录和单项目 CRA 共享库。"""

import sqlite3
from .local import LocalStore
from .shared import SharedContext, PREFIX
from ..models import require
from ..permissions import revalidate, write_scope, can_edit
from ..records import evidence_eligible, KIND_TO_TYPE, REQUIRED


class Store(LocalStore):
    def __init__(self, registry, ctx):
        super().__init__(registry, ctx)
        self.shared = SharedContext(registry, ctx)

    def get(self, record_id):
        revalidate(self.registry, self.ctx)
        if isinstance(record_id, str) and record_id.startswith(PREFIX):
            return self.shared.read(record_id)
        record = super().get(record_id)
        record["sources"] = self.sources_for(record)
        return record

    def get_version(self, record_id, version):
        revalidate(self.registry, self.ctx)
        require(type(version) is int and version >= 1, "INVALID_REFERENCE", "Version must be a positive integer.")
        if record_id.startswith(PREFIX):
            return self.shared.read(record_id, version)
        record = super().get_version(record_id, version)
        record.setdefault("sources", self.sources_for(record))
        return record

    def list(self, kind=None, query="", limit=30, research=False):
        require(type(limit) is int and 1 <= limit <= 100, "INVALID_INPUT", "limit must be 1..100.")
        local = super().list(kind, query, 100)
        if research:
            local = [r for r in local if evidence_eligible(r) or r["kind"] in {"note", "problem", "update", "feedback"}]
        remote = self.shared.search(query, kind, limit) if self.shared.enabled else []
        merged = local + remote
        merged.sort(key=lambda record: (record["updated_at"], record["id"]), reverse=True)
        return merged[:limit]

    def validate_refs(self, refs, visibility, research=False):
        clean = super().validate_refs(refs, visibility)
        if research:
            require(all(evidence_eligible(self.get_version(ref["id"], ref["version"])) and evidence_eligible(self.get(ref["id"])) for ref in clean),
                    "UNCONFIRMED_EVIDENCE", "Research evidence must be confirmed knowledge or a clearly labelled raw paper.")
        return clean

    def create_once(self, *args, **kwargs):
        try:
            return self.create(*args, **kwargs), True
        except sqlite3.IntegrityError:
            require(kwargs.get("record_id"), "DUPLICATE_RECORD", "Record already exists.")
            return self.get(kwargs["record_id"]), False

    def export_shared(self, record):
        write_scope(self.registry, self.ctx, "project")
        can_edit(self.registry,self.ctx,record)
        require(record["visibility"] == "project", "PRIVATE_DERIVATION", "Publish selected content before exporting it.")
        require(record["kind"] in KIND_TO_TYPE, "INVALID_INPUT", "Only typed research records can be exported.")
        fields = record.get("fields", {})
        require(all(key in fields and fields[key] is not None and fields[key] != "" for key in REQUIRED[KIND_TO_TYPE[record["kind"]]]),
                "INCOMPLETE_RECORD", "Complete the type-specific fields before exporting a shared draft.")
        evidence = []
        for ref in self.validate_refs(record["refs"], "project", research=True):
            source = self.get_version(ref["id"], ref["version"])
            evidence.append({**ref, "title": source["title"], "body": source["body"],
                             "status": source["status"], "sources": source.get("sources", [])})
        item = {key: record[key] for key in ("id", "kind", "title", "body", "version", "created_at", "fields")}
        item["task_id"] = record["attributes"].get("task_id")
        result=self.shared.call("export", record=item, evidence=evidence)
        self.save_export(record["id"],result)
        return result

    def review(self,record_id,version,status,fields=None):
        require(self.ctx.role == "user", "ACCESS_DENIED", "Review requires an internal user, not a background service.")
        require(type(version) is int and version>=1,"INVALID_INPUT","Review version must be a positive integer.")
        if record_id.startswith(PREFIX):
            write_scope(self.registry,self.ctx,"project")
            return self.shared.normalize(self.shared.call("review",record_id=record_id[4:],version=version,status=status,fields=fields))
        return super().review(record_id,version,status,fields)

    def withdraw_remote(self, record_id, version):
        write_scope(self.registry, self.ctx, "project")
        return self.shared.call("withdraw", record_id=record_id.removeprefix(PREFIX), version=version)
