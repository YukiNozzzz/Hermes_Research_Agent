"""选择一个真实 Hermes Home；不删除旧 profile，也不复制凭据和历史。"""

from contextlib import closing
from pathlib import Path
import sqlite3
import uuid

from ...models import identifier, require
from .profiles import HermesCommand, configure_profile, link_plugin


def setup(registry, command, source, profile=None, project_id=None, user_id=None,
          service_profile=None, no_service=False):
    original = registry.inspect()
    policy = registry.single_user()
    if profile is None:
        profile = registry.current()["profile"] if policy else "default"
    identifier(profile)
    if project_id is None:
        projects = [item["project_id"] for item in original["projects"]]
        project_id = policy["project_id"] if policy else (projects[0] if len(projects) == 1 else None)
    require(project_id, "PROJECT_REQUIRED", "Choose --project for the initial single-user setup.")
    project = registry.project(project_id)
    existing = next((u for u in original["users"] if u["profile"] == profile), None)
    if existing:
        require(existing["active"] and existing["kind"] == "user", "IDENTITY_CONFLICT", "Select an active personal profile.")
        require(user_id is None or user_id == existing["user_id"], "IDENTITY_CONFLICT", "Keep the existing user ID; private data is not reassigned.")
    if user_id is not None:
        identifier(user_id)
    target_id = existing["user_id"] if existing else (user_id or "local-user")
    require(not any(u["user_id"] == target_id and u["profile"] != profile for u in original["users"]),
            "IDENTITY_CONFLICT", "This user already has a profile; select it to keep its private data.")

    require(not (no_service and service_profile), "INVALID_INPUT", "Choose --service-profile or --no-service.")
    if no_service:
        service_profile = None
    elif service_profile is None:
        # Keep an existing project's sole collector so a code upgrade does not
        # silently invalidate its already registered cron job.
        candidates = [u for u in original["users"] if u["active"] and u["kind"] == "service" and
                      any(m["project_id"] == project_id and m["user_id"] == u["user_id"] for m in original["members"])]
        if policy:
            candidates = [u for u in original["users"] if u["active"] and u["user_id"] == policy["service_id"]]
        require(len(candidates) <= 1, "SERVICE_REQUIRED", "Choose the existing collector with --service-profile, or explicitly use --no-service.")
        service_profile = candidates[0]["profile"] if candidates else None
    service = next((u for u in original["users"] if u["profile"] == service_profile and
                    u["kind"] == "service" and u["active"]), None) if service_profile else None
    require(service_profile is None or service, "INVALID_SERVICE", "The service profile must already be registered and active.")

    home = Path(existing["home"]) if existing else (command.root if profile == "default" else command.root / "profiles" / profile)
    desired = {"owner_id": target_id, "project_id": project_id,
               "service_id": service["user_id"] if service else None}
    changed = policy is None or any(policy[key] != value for key, value in desired.items())
    backup = None
    if changed:
        backup = registry.config.registry_path.with_name("registry.sqlite.before-single-user-" + uuid.uuid4().hex[:12])
        with closing(sqlite3.connect(registry.config.registry_path)) as db, closing(sqlite3.connect(backup)) as saved:
            db.backup(saved)
    registry.initialize()

    if not home.exists() and profile != "default":
        command.run("profile", "create", profile, "--no-alias")
    require((home / "config.yaml").is_file(), "PROFILE_MISSING", "Run Hermes setup first, or select an existing configured profile.")
    config = configure_profile(home, registry.config.data_root, "user", timezone=project["timezone"])
    link_plugin(home, source)
    native_root = home if profile == "default" else home.parent.parent
    native = HermesCommand(native_root, command.python, command.source) if native_root.resolve() != command.root.resolve() else command
    native.run("-p", profile, "plugins", "enable", "research-ideation")
    if service:
        configure_profile(service["home"], registry.config.data_root, "service", timezone=project["timezone"])
    current = registry.select_single_user(profile, home, project_id, target_id, service_profile)
    return {"mode": "single-user", "changed": changed, "current": current,
            "collector_profile": service_profile or profile,
            "registry_backup": str(backup) if backup else None,
            "profile_configuration": config,
            "historical_users_preserved": len([u for u in original["users"] if u["kind"] == "user" and u["user_id"] != target_id]),
            "new_session_required": True,
            "note": "No history was merged or deleted. Existing schedules are preserved; no gateway or model run was started."}
