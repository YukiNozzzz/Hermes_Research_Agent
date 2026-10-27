"""Local connection configuration and read-only health checks only."""

import argparse
import json
from pathlib import Path
import sys
from .context import Config
from .database import Database
from .models import ResearchError, require


def parser():
    p = argparse.ArgumentParser(description="Configure the six-type PostgreSQL reader. No identity registry or result storage.")
    p.add_argument("--data-root", default=str(Path(__file__).resolve().parents[2] / "research-data"))
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("current", help="Show this deployment's local identity and input scope")
    sub.add_parser("database-check", help="Check the existing CRA tables in a read-only transaction")
    bind = sub.add_parser("database-bind", help="Save local connection and shared dataset configuration")
    for key in ("python", "repository", "env-file", "project", "user-id"):
        bind.add_argument("--" + key, required=True)
    bind.add_argument("--title", default="")
    bind.add_argument("--brief", default="")
    bind.add_argument("--include-unscoped", action="store_true", help="Explicitly authorize shared legacy records without project metadata")
    return p


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = parser().parse_args(argv)
    try:
        config = Config.from_root(args.data_root)
        if args.command == "database-bind":
            settings = {"python": str(Path(args.python).resolve()), "repository": str(Path(args.repository).resolve()),
                "env_file": str(Path(args.env_file).resolve()), "project_id": args.project, "user_id": args.user_id,
                "project_title": args.title or args.project, "project_brief": args.brief,
                "include_unscoped": args.include_unscoped}
            require(Path(settings["python"]).is_file() and Path(settings["env_file"]).is_file()
                    and (Path(settings["repository"]) / "src/cra/config.py").is_file(),
                    "INVALID_CONFIG", "Verify the configured interpreter, CRA source and credentials file.")
            data = Database(config, settings=settings).call("health")
            require(data["ready"] and data["read_only"], "DATABASE_NOT_READY", "Prepare the existing CRA source tables before binding.")
            path = config.data_root / "control/database.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(".tmp")
            temporary.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
            temporary.replace(path)
        else:
            database = Database(config)
            if args.command == "current":
                data = {"user_id": database.settings["user_id"], "project": database.project,
                        "source": "public.records", "include_unscoped": database.settings.get("include_unscoped", False),
                        "identity_storage": "local deployment configuration", "result_storage": "conversation or user-requested local document"}
            else:
                data = database.call("health")
        print(json.dumps({"ok": True, "data": data}, ensure_ascii=False, indent=2))
    except (ResearchError, OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({"ok": False, "error": {"code": getattr(exc, "code", type(exc).__name__),
            "message": str(exc) if isinstance(exc, ResearchError) else "Invalid local configuration or connection request."}}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
