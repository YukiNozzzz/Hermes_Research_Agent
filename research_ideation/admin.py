"""Local administrator CLI. Never register these capabilities as agent tools."""

import argparse
import json
from pathlib import Path
import sys
from .config import Config
from .registry import Registry
from .models import ResearchError,require
from .context import resolve_context
from .profiles import HermesCommand,provision,doctor,schedule


def command_from(registry):
    path=registry.config.data_root/"control"/"runtime.json"
    require(path.is_file(),"SETUP_REQUIRED","Run init with the actual Hermes root.")
    data=json.loads(path.read_text(encoding="utf-8"))
    return HermesCommand(data["hermes_root"],data.get("hermes_python"),data.get("hermes_source"))


def parser():
    p=argparse.ArgumentParser(description="Administrator-only research project management; no secrets in output.")
    p.add_argument("--data-root",required=True)
    sub=p.add_subparsers(dest="command",required=True)
    init=sub.add_parser("init");init.add_argument("--hermes-root",required=True);init.add_argument("--hermes-python");init.add_argument("--hermes-source")
    project=sub.add_parser("project-add")
    for name in ("id","title","brief","query"):project.add_argument("--"+name,required=True)
    project.add_argument("--time",default="10:00");project.add_argument("--timezone",default="Asia/Shanghai")
    user=sub.add_parser("user-add");user.add_argument("--id",required=True);user.add_argument("--profile",required=True);user.add_argument("--service",action="store_true");user.add_argument("--resume",action="store_true")
    member=sub.add_parser("member");member.add_argument("--project",required=True);member.add_argument("--user",required=True);member.add_argument("--role",choices=["owner","editor","reader","service"],required=True)
    revoke=sub.add_parser("revoke");revoke.add_argument("--project",required=True);revoke.add_argument("--user",required=True)
    disable=sub.add_parser("disable");disable.add_argument("--user",required=True)
    binding=sub.add_parser("bind")
    for key in ("platform","account","sender","user"):binding.add_argument("--"+key,required=True)
    binding.add_argument("--tenant",default="")
    routes=sub.add_parser("routes");routes.add_argument("--platform",required=True);routes.add_argument("--account",required=True)
    for name in ("doctor","snapshot","update","schedule"):
        item=sub.add_parser(name);item.add_argument("--profile",required=True)
        if name!="doctor":item.add_argument("--project",required=True)
        if name=="update":item.add_argument("--force",action="store_true");item.add_argument("--lookback-days",type=int,default=30)
    local=sub.add_parser("import")
    for name in ("profile","project","file"):local.add_argument("--"+name,required=True)
    local.add_argument("--kind",choices=["note","experience","problem","experiment"],default="note")
    local.add_argument("--shared",action="store_true")
    auto=sub.add_parser("auto-explore");auto.add_argument("--project",required=True);auto.add_argument("--enabled",choices=["true","false"],required=True)
    sub.add_parser("inspect")
    return p


def main(argv=None):
    args=parser().parse_args(argv)
    registry=Registry(Config.from_root(args.data_root))
    source=Path(__file__).resolve().parents[1]
    try:
        if args.command=="init":
            registry.initialize()
            path=registry.config.data_root/"control"/"runtime.json"
            require(not path.exists(),"ALREADY_INITIALIZED","Runtime settings already exist; edit them explicitly as administrator.")
            settings={"hermes_root":str(Path(args.hermes_root).expanduser().resolve()),"hermes_python":args.hermes_python,"hermes_source":args.hermes_source}
            path.write_text(json.dumps(settings,ensure_ascii=False,indent=2),encoding="utf-8")
            data={"initialized":True,"data_root":str(registry.config.data_root)}
        elif args.command=="project-add":
            registry.add_project(args.id,args.title,args.brief,args.query,args.time,args.timezone);data=registry.project(args.id)
        elif args.command=="user-add":data=provision(registry,command_from(registry),source,args.id,args.profile,"service" if args.service else "user",args.resume)
        elif args.command=="member":registry.set_member(args.project,args.user,args.role);data={"updated":True}
        elif args.command=="revoke":registry.revoke(args.project,args.user);data={"revoked":True}
        elif args.command=="disable":registry.disable(args.user);data={"disabled":True}
        elif args.command=="bind":registry.bind(args.platform,args.account,args.tenant,args.sender,args.user);data={"bound":True}
        elif args.command=="routes":
            from .adapters.channels import routing_plan
            data=routing_plan(registry,args.account,args.platform)
        elif args.command=="doctor":data=doctor(registry,command_from(registry),args.profile)
        elif args.command=="schedule":data=schedule(registry,command_from(registry),args.profile,args.project,source)
        elif args.command=="auto-explore":
            with registry.connection(admin=True) as db:
                changed=db.execute("UPDATE projects SET auto_explore=? WHERE project_id=?",(int(args.enabled=="true"),args.project)).rowcount
                require(changed==1,"NOT_FOUND","Project not found.")
            data={"updated":True,"note":"Reconfigure the existing Hermes job to agent mode before enabling automatic ideation; existing schedules are not silently rewritten."}
        elif args.command=="inspect":data=registry.inspect()
        else:
            user=next((u for u in registry.inspect()["users"] if u["profile"]==args.profile),None)
            require(user,"NOT_FOUND","Registered profile not found.")
            ctx=resolve_context(registry,args.profile,user["home"],args.project)
            if args.command=="snapshot":
                from .memory import snapshot
                data=snapshot(registry,ctx)
            elif args.command=="update":
                from .workflows.daily_update import update
                data=update(registry,ctx,args.lookback_days,args.force)
            elif args.command=="import":
                from .adapters.local_files import read_from_inbox
                from .artifacts import Artifacts
                from .storage import Store,public_record
                scope="project" if args.shared else "private"
                inbox=Artifacts(registry,ctx).root(scope)/"inbox"
                text=read_from_inbox(inbox,args.file)
                data=public_record(Store(registry,ctx).create(args.kind,Path(args.file).stem,text,scope))
        print(json.dumps({"ok":True,"data":data},ensure_ascii=False,indent=2))
    except (ResearchError,ValueError,OSError) as exc:
        print(json.dumps({"ok":False,"error":{"code":getattr(exc,"code",type(exc).__name__),"message":str(exc)}},ensure_ascii=False),file=sys.stderr)
        raise SystemExit(1)


if __name__=="__main__":
    main()
