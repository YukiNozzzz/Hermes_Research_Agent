"""Administrator-only Hermes CLI integration. No model credentials or other users' state are cloned."""

import json
import os
from pathlib import Path
import subprocess
import shutil
import uuid
from ...models import require,identifier,ResearchError
from ...artifacts import contained


def read_yaml(path):
    text=Path(path).read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            from ruamel.yaml import YAML
            return YAML(typ="safe").load(text) or {}
        except ImportError:
            import yaml
            return yaml.safe_load(text) or {}


class HermesCommand:
    def __init__(self,root,python=None,source=None):
        self.root=Path(root).expanduser().resolve()
        self.python=python
        self.source=source

    def run(self,*args):
        env=dict(os.environ)
        env["HERMES_HOME"]=str(self.root)
        env["PYTHONUTF8"]="1"
        env["PYTHONIOENCODING"]="utf-8"
        if self.source:
            env["HERMES_PYTHON_SRC_ROOT"]=str(self.source)
            env["PYTHONPATH"]=str(self.source)
        command=[self.python,"-B","-m","hermes_cli.main"] if self.python else ["hermes"]
        try:
            result=subprocess.run(command+list(args),env=env,cwd=self.source or self.root,text=True,encoding="utf-8",capture_output=True,timeout=600)
        except subprocess.TimeoutExpired as exc:
            raise ResearchError("HERMES_TIMEOUT","Hermes command timed out. Inspect package-manager/gateway activity before retrying.",True) from exc
        if result.returncode:
            # Administrative diagnostic, not exposed through agent tools.
            raise ResearchError("HERMES_COMMAND_FAILED",("STDOUT:\n"+result.stdout+"\nSTDERR:\n"+result.stderr)[-6000:])
        return result.stdout


def link_plugin(profile_home,source):
    link=Path(profile_home)/"plugins"/"research-ideation"
    target=Path(source).resolve()
    link.parent.mkdir(parents=True,exist_ok=True)
    if link.exists():
        require(link.resolve()==target,"INSTALL_CONFLICT","Plugin path already belongs to another installation.")
        return
    if os.name=="nt":
        literal=lambda value:"'"+str(value).replace("'","''")+"'"
        command="New-Item -ItemType Junction -Path "+literal(link)+" -Target "+literal(target)+" | Out-Null"
        subprocess.run(["powershell","-NoProfile","-NonInteractive","-Command",command],check=True,capture_output=True)
    else:
        link.symlink_to(target,target_is_directory=True)


USER_TOOLSETS = ["hermes-cli", "research_ideation", "skills"]
SERVICE_TOOLSETS = ["research_ideation", "skills"]


def profile_config(config, data_root, kind="user", timezone=None):
    """仅调整两种运行身份的策略，保留模型、凭据引用和其他用户设置。"""
    require(kind in {"user", "service"}, "INVALID_ROLE", "Use user or service.")
    config = json.loads(json.dumps(config))
    require(isinstance(config, dict), "INVALID_CONFIG", "Profile config must be an object.")

    def section(parent, name):
        if parent.get(name) is None:
            parent[name] = {}
        require(isinstance(parent[name], dict), "INVALID_CONFIG", name + " must be an object.")
        return parent[name]

    settings = section(section(section(section(config, "plugins"), "entries"),
                               "research-ideation"), "settings")
    settings["data_root"] = str(data_root)
    surfaces = section(config, "platform_toolsets")
    for surface in set(surfaces) | {"cli", "default"}:
        if kind == "service":
            surfaces[surface] = list(SERVICE_TOOLSETS)
        else:
            existing = surfaces.get(surface, [])
            require(isinstance(existing, list) and all(isinstance(name, str) for name in existing),
                    "INVALID_CONFIG", "Each platform toolset setting must be a list of names.")
            surfaces[surface] = list(dict.fromkeys([*USER_TOOLSETS, *existing]))
    memory = section(config, "memory")
    memory.update(memory_enabled=kind == "user", user_profile_enabled=kind == "user")
    # The platform allowlist is authoritative; stale global blank-slate suppression
    # must not cancel the user's native tools or the service's required skills.
    section(config, "agent")["disabled_toolsets"] = []
    if kind == "user":
        skills = section(config, "skills")
        if skills.get("creation_nudge_interval") == 0:
            skills.pop("creation_nudge_interval")
    else:
        section(config, "skills")["creation_nudge_interval"] = 0
        section(section(config, "auxiliary"), "background_review")["enabled"] = False
    if timezone is not None:
        config["timezone"] = timezone
    else:
        config.setdefault("timezone", "Asia/Shanghai")
    return config


def configure_profile(home, data_root, kind="user", *, apply=True, timezone=None):
    path = Path(home) / "config.yaml"
    original = read_yaml(path)
    updated = profile_config(original, data_root, kind, timezone)
    changed = updated != original
    backup = None
    if apply and changed:
        backup = path.with_name("config.yaml.permissions-backup-" + uuid.uuid4().hex[:12])
        shutil.copy2(path, backup)
        temporary = path.with_name("config.yaml.permissions-tmp-" + uuid.uuid4().hex[:12])
        try:
            temporary.write_text(json.dumps(updated, ensure_ascii=False, indent=2), encoding="utf-8")
            temporary.chmod(path.stat().st_mode)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
    return {"kind": kind, "changed": changed, "applied": apply,
            "backup": str(backup) if backup else None,
            "platform_toolsets": updated["platform_toolsets"]}


def restricted_config(home, data_root, timezone="Asia/Shanghai"):
    """兼容旧管理代码；显式调用此名称仍表示受限后台服务。"""
    return configure_profile(home, data_root, "service", timezone=timezone)


def sync_permissions(registry, command, profile, apply=False):
    user = next((u for u in registry.inspect()["users"] if u["profile"] == profile), None)
    require(user and user["active"], "NOT_FOUND", "Active profile is not registered.")
    home = Path(user["home"])
    registry.user(profile, home)
    # The administrator registry owns the exact native home binding. Windows MSIX
    # and non-virtualized profiles can legitimately coexist under different roots.
    require(home.name == profile and (home / "config.yaml").is_file(),
            "IDENTITY_DENIED", "Registered native profile home is invalid.")
    result = configure_profile(home, registry.config.data_root, user["kind"], apply=apply)
    migrated = registry.normalize_members(user["user_id"]) if apply else 0
    return {"profile": profile, **result, "memberships_migrated": migrated,
            "new_session_required": True}


def provision(registry,command,source,user_id,profile,kind="user",resume=False):
    identifier(user_id);identifier(profile)
    existing=[u for u in registry.inspect()["users"] if u["profile"]==profile or u["user_id"]==user_id]
    if existing:
        require(len(existing)==1 and existing[0]["profile"]==profile and existing[0]["user_id"]==user_id and existing[0]["kind"]==kind,"IDENTITY_CONFLICT","User/profile is already bound differently.")
        return {"user_id":user_id,"already_registered":True,
                **sync_permissions(registry,command,profile,apply=True)}
    home=contained(command.root,"profiles",profile)
    if home.exists():
        require(resume,"PROFILE_EXISTS","A profile already exists. Use --resume only for this administrator's interrupted installation.")
        settings=read_yaml(home/"config.yaml").get("plugins",{}).get("entries",{}).get("research-ideation",{}).get("settings",{})
        plugin=home/"plugins"/"research-ideation"
        require(settings.get("data_root")==str(registry.config.data_root) and plugin.exists() and plugin.resolve()==Path(source).resolve(),"INSTALL_CONFLICT","Existing profile does not match this managed installation.")
    else:
        arguments=["profile","create",profile,"--no-alias"]
        if kind=="service":arguments.append("--no-skills")
        command.run(*arguments)
    require(home.is_dir(),"PROFILE_MISSING","Hermes created the profile outside the configured root; inspect root configuration.")
    configure_profile(home,registry.config.data_root,kind)
    link_plugin(home,source)
    command.run("-p",profile,"plugins","enable","research-ideation")
    # Register only after native creation and plugin admission succeeded.
    registry.add_user(user_id,profile,home,kind)
    return {"user_id":user_id,"profile":profile,"home":str(home),"created":True}


def doctor(registry,command,profile):
    user=next((u for u in registry.inspect()["users"] if u["profile"]==profile),None)
    require(user,"NOT_FOUND","Profile is not registered.")
    config=read_yaml(Path(user["home"])/"config.yaml")
    issues=[]
    kind=user["kind"]
    surfaces=config.get("platform_toolsets",{})
    for surface in set(surfaces) | {"cli", "default"}:
        toolsets=surfaces.get(surface,[])
        if not isinstance(toolsets,list) or not all(isinstance(name,str) for name in toolsets):
            issues.append("Invalid toolsets on "+surface)
        elif kind=="service" and (not set(toolsets)<=set(SERVICE_TOOLSETS) or not set(SERVICE_TOOLSETS)<=set(toolsets)):
            issues.append("Service requires only research_ideation and skills on "+surface)
        elif kind=="user" and not (set(SERVICE_TOOLSETS)<=set(toolsets) and set(toolsets)&{"hermes-cli","all","*"}):
            issues.append("Internal user is missing the full native tools or research tools on "+surface)
    disabled=config.get("agent",{}).get("disabled_toolsets",[])
    if kind=="user" and disabled:
        issues.append("Global agent.disabled_toolsets suppresses full-user tools.")
    if kind=="service":
        if any(name in disabled for name in [*SERVICE_TOOLSETS,"all","*"]):
            issues.append("Service tools are globally disabled.")
        if config.get("memory",{}).get("memory_enabled",True) or config.get("memory",{}).get("user_profile_enabled",True):
            issues.append("Service automatic personal memory must be disabled.")
    home=Path(user["home"])
    if command.root.resolve()!=home.parent.parent.resolve():
        command=HermesCommand(home.parent.parent,command.python,command.source)
    result=command.run("-p",profile,"plugins","doctor","research-ideation","--ci")
    return {"profile":profile,"kind":kind,"configuration_ok":not issues,"issues":issues,"plugin_doctor":result,
            "deployment_boundary":"Trusted internal user with full tools, or restricted background service. Profiles separate sessions, not OS/file permissions. Messaging ingress still requires certification."}


def schedule(registry,command,profile,project_id,source):
    user=next((u for u in registry.inspect()["users"] if u["profile"]==profile and u["kind"]=="service" and u["active"]),None)
    require(user,"ACCESS_DENIED","Use a registered service profile.")
    require(registry.member(user["user_id"],project_id)=="service","ACCESS_DENIED","Service is not assigned to this project.")
    project=registry.project(project_id)
    home=Path(user["home"])
    require(read_yaml(home/"config.yaml").get("timezone")==project["timezone"],"TIMEZONE_CONFLICT","Service profile timezone must match the project schedule.")
    existing=registry.schedule_for(project_id)
    if existing:
        return {"job_id":existing["job_id"],"already_registered":True,"note":"Use Hermes cron list to inspect whether an administrator changed or removed the job."}
    script=home/"scripts"/("research_update_"+identifier(project_id)+".py")
    script.parent.mkdir(parents=True,exist_ok=True)
    # Source checkout is administrator controlled, never a model-provided command.
    content="import sys\nsys.path.insert(0, "+repr(str(Path(source).resolve()))+")\nfrom research_ideation.admin import main\nmain("+repr(["--data-root",str(registry.config.data_root),"update","--profile",profile,"--project",project_id])+ ")\n"
    script.write_text(content,encoding="utf-8")
    hour,minute=project["daily_time"].split(":")
    expression=f"{int(minute)} {int(hour)} * * *"
    name="research-papers-"+project_id
    if project["auto_explore"]:
        prompt=f"Use project {project_id}. Load research-ideation:problem-exploration. First call research_update_papers. Only if auto_explore is true and new_count > 0, explore ONE existing shared open problem and save the result. Otherwise stop. No external messages."
        output=command.run("-p",profile,"cron","create",expression,prompt,"--name",name,"--deliver","local","--skill","research-ideation:problem-exploration")
    else:
        interpreter_args=["--interpreter",command.python] if command.python else []
        output=command.run("-p",profile,"cron","create",expression,"--name",name,"--script",script.name,"--no-agent","--deliver","local",*interpreter_args)
    # Read-only discovery of the native job Hermes just wrote; never hand-write native jobs.
    jobs_path=home/"cron"/"jobs.json"
    require(jobs_path.is_file(),"SCHEDULE_INSPECT_REQUIRED","Hermes created a job but its metadata location differs. Inspect native cron list before retrying.")
    data=json.loads(jobs_path.read_text(encoding="utf-8"))
    jobs=data.get("jobs",[]) if isinstance(data,dict) else data
    matches=[j for j in jobs if j.get("name")==name]
    require(len(matches)==1,"SCHEDULE_INSPECT_REQUIRED","Native schedule identity is ambiguous; inspect before retrying.")
    job=matches[0]
    registry.save_schedule(project_id,job["id"])
    return {"job_id":job["id"],"schedule":expression,"timezone":project["timezone"],"next_run_at":job.get("next_run_at"),"hermes_output":output,
            "scheduler_note":"Job configuration does not itself start a gateway/scheduler or prove a timed run occurred."}
