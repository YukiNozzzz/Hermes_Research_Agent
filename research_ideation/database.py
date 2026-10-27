"""Read-only CRA transport. Questions, user identities and ideas never enter SQL."""

import json
import os
from pathlib import Path
import subprocess
from .models import ResearchError, require, identifier


class Database:
    def __init__(self, config, settings=None):
        path = config.data_root / "control/database.json"
        require(settings is not None or path.is_file(), "DATABASE_CONFIG_REQUIRED", "Configure PostgreSQL with database-bind.")
        try:
            self.settings = dict(settings) if settings is not None else json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError, TypeError) as exc:
            raise ResearchError("INVALID_CONFIG", "Cannot read PostgreSQL connection settings.") from exc
        require(isinstance(self.settings, dict), "INVALID_CONFIG", "Connection settings must be an object.")
        for key in ("python", "repository", "env_file", "project_id", "user_id"):
            require(isinstance(self.settings.get(key), str) and self.settings[key].strip(), "INVALID_CONFIG", f"Configure {key} in database-bind; legacy registry settings are no longer used.")
        identifier(self.settings["project_id"])
        identifier(self.settings["user_id"])
        require(type(self.settings.get("include_unscoped", False)) is bool, "INVALID_CONFIG", "include_unscoped must be true or false.")

    @property
    def project(self):
        return {"project_id": self.settings["project_id"],
                "title": self.settings.get("project_title", self.settings["project_id"]),
                "brief": self.settings.get("project_brief", "")}

    def call(self, operation):
        require(operation in {"health", "inputs"}, "INVALID_OPERATION", "Only read-only health and inputs operations are available.")
        # Deployment scope is loaded locally, never from model arguments. Do not send
        # questions, user_id, profile paths, session histories or generated ideas.
        payload = {"operation": operation, "project_id": self.settings["project_id"],
                   "include_unscoped": self.settings.get("include_unscoped", False)}
        environment = dict(os.environ)
        for key in ("CRA_DATABASE_URL", "PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"):
            environment.pop(key, None)
        environment["PYTHONUTF8"] = "1"
        command = [self.settings["python"], "-X", "utf8", "-B", str(Path(__file__).with_name("pg_worker.py")),
                   self.settings["repository"], self.settings["env_file"]]
        try:
            result = subprocess.run(command, input=json.dumps(payload), text=True, encoding="utf-8",
                                    capture_output=True, timeout=120, env=environment, cwd=self.settings["repository"])
            response = json.loads(result.stdout)
            require(isinstance(response, dict), "DATABASE_ERROR", "Invalid PostgreSQL response.")
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            raise ResearchError("DATABASE_UNAVAILABLE", "PostgreSQL is unavailable; inputs were not loaded. No local fallback was used.", True) from exc
        if result.returncode != 0 or not response.get("ok"):
            raise ResearchError(response.get("code", "DATABASE_ERROR"), response.get("message", "PostgreSQL read failed."), response.get("retryable", False))
        return response["data"]
