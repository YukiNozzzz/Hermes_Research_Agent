"""Bounded, scoped file operations. OS-level isolation is still a deployment requirement."""

import json
import os
from pathlib import Path
from .models import identifier, require
from .permissions import revalidate, write_scope


def contained(root, *parts):
    root = Path(root).absolute()
    candidate = root.joinpath(*parts)
    require(candidate.is_relative_to(root), "INVALID_PATH", "Path is outside the configured root.")
    for part in (root, *candidate.parents, candidate):
        require(not part.is_symlink() and not (hasattr(part,"is_junction") and part.is_junction()),
                "INVALID_PATH", "Data paths cannot traverse symlinks or junctions.")
    # On Windows a concurrently materialized directory can change the long/short
    # spelling returned by GetFinalPathName. Resolve only after the trusted root exists.
    root.mkdir(parents=True,exist_ok=True)
    resolved_root=root.resolve()
    require(candidate.resolve().is_relative_to(resolved_root), "INVALID_PATH", "Resolved path is outside the root.")
    return candidate


class Artifacts:
    def __init__(self, registry, ctx):
        self.registry, self.ctx = registry, ctx

    def root(self, visibility):
        revalidate(self.registry,self.ctx)
        if visibility == "private":
            require(self.ctx.role != "service", "ACCESS_DENIED", "Service has no private data area.")
            return contained(self.ctx.profile_home,"plugin-data","research-ideation")
        require(visibility == "project", "INVALID_SCOPE", "Unknown data scope.")
        return contained(self.registry.config.data_root,"projects",identifier(self.ctx.project_id))

    def write_report(self, task_id, visibility, data, markdown):
        write_scope(self.registry,self.ctx,visibility)
        identifier(task_id)
        folder = contained(self.root(visibility),"reports",task_id)
        folder.mkdir(parents=True,exist_ok=True)
        for name, content in (("result.json",json.dumps(data,ensure_ascii=False,indent=2)),("report.md",markdown)):
            target = contained(folder,name)
            temporary = target.with_suffix(target.suffix + ".tmp")
            require(not temporary.is_symlink(),"INVALID_PATH","Unsafe temporary file.")
            temporary.write_text(content,encoding="utf-8")
            os.replace(temporary,target)
        return {"task_id":task_id,"scope":visibility,"files":["result.json","report.md"]}
