"""Administrator-only Hermes CLI integration. No model credentials or other users' state are cloned."""

import json
import os
from pathlib import Path
import subprocess
import sys
from .models import require,identifier,ResearchError
from .artifacts import contained


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


def restricted_config(home,data_root,timezone="Asia/Shanghai"):
    path=Path(home)/"config.yaml"
    config=read_yaml(path)
    config.setdefault("plugins",{})
    config["plugins"].setdefault("entries",{}).setdefault("research-ideation",{})["settings"]={"data_root":str(data_root)}
    config["platform_toolsets"]={"cli":["research_ideation","skills"],"default":["research_ideation","skills"]}
    config["memory"]={"memory_enabled":False,"user_profile_enabled":False}
    config.setdefault("auxiliary",{})["background_review"]={"enabled":False}
    config["timezone"]=timezone
    config["skills"]={"creation_nudge_interval":0}
    # Config is JSON, which YAML loaders accept. Profiles here are newly created by this command.
    path.write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding="utf-8")


def provision(registry,command,source,user_id,profile,kind="user",resume=False):
    identifier(user_id);identifier(profile)
    existing=[u for u in registry.inspect()["users"] if u["profile"]==profile or u["user_id"]==user_id]
    if existing:
        require(len(existing)==1 and existing[0]["profile"]==profile and existing[0]["user_id"]==user_id,"IDENTITY_CONFLICT","User/profile is already bound differently.")
        return {"user_id":user_id,"profile":profile,"home":existing[0]["home"],"already_registered":True}
    home=contained(command.root,"profiles",profile)
    if home.exists():
        require(resume,"PROFILE_EXISTS","A profile already exists. Use --resume only for this administrator's interrupted installation.")
        settings=read_yaml(home/"config.yaml").get("plugins",{}).get("entries",{}).get("research-ideation",{}).get("settings",{})
        plugin=home/"plugins"/"research-ideation"
        require(settings.get("data_root")==str(registry.config.data_root) and plugin.exists() and plugin.resolve()==Path(source).resolve(),"INSTALL_CONFLICT","Existing profile does not match this managed installation.")
    else:
        command.run("profile","create",profile,"--no-alias","--no-skills")
    require(home.is_dir(),"PROFILE_MISSING","Hermes created the profile outside the configured root; inspect root configuration.")
    restricted_config(home,registry.config.data_root)
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
    allowed={"research_ideation","skills"}
    for surface,toolsets in config.get("platform_toolsets",{}).items():
        if not isinstance(toolsets,list) or not set(toolsets)<=allowed:
            issues.append("Unexpected toolsets on "+surface)
    if not config.get("platform_toolsets",{}).get("cli"):
        issues.append("Missing restricted CLI toolset.")
    if config.get("memory",{}).get("memory_enabled",True) or config.get("memory",{}).get("user_profile_enabled",True):
        issues.append("Native automatic memory is enabled; audit writeback scope first.")
    result=command.run("-p",profile,"plugins","doctor","research-ideation","--ci")
    return {"profile":profile,"configuration_ok":not issues,"issues":issues,"plugin_doctor":result,
            "deployment_boundary":"CLI-only certified. Messaging, host command gating and OS/filesystem isolation require separate live acceptance."}


def schedule(registry,command,profile,project_id,source):
    user=next((u for u in registry.inspect()["users"] if u["profile"]==profile and u["kind"]=="service" and u["active"]),None)
    require(user,"ACCESS_DENIED","Use a registered service profile.")
    require(registry.member(user["user_id"],project_id)=="service","ACCESS_DENIED","Service is not assigned to this project.")
    project=registry.project(project_id)
    home=Path(user["home"])
    require(read_yaml(home/"config.yaml").get("timezone")==project["timezone"],"TIMEZONE_CONFLICT","Service profile timezone must match the project schedule.")
    with registry.connection() as db:
        existing=db.execute("SELECT job_id FROM schedules WHERE project_id=?",(project_id,)).fetchone()
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
    from .models import now
    with registry.connection(admin=True) as db:
        db.execute("INSERT INTO schedules VALUES(?,?,?)",(project_id,job["id"],now()))
    return {"job_id":job["id"],"schedule":expression,"timezone":project["timezone"],"next_run_at":job.get("next_run_at"),"hermes_output":output,
            "scheduler_note":"Job configuration does not itself start a gateway/scheduler or prove a timed run occurred."}
