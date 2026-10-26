"""Local administrator CLI. Never register these capabilities as agent tools."""

import argparse
import json
from pathlib import Path
import sys
from .config import Config
from .registry import Registry
from .models import ResearchError,require
from .context import resolve_context
from .profiles import HermesCommand,provision,doctor,schedule,sync_permissions


def command_from(registry):
    path=registry.config.data_root/"control"/"runtime.json"
    require(path.is_file(),"SETUP_REQUIRED","Run init with the actual Hermes root.")
    data=json.loads(path.read_text(encoding="utf-8"))
    return HermesCommand(data["hermes_root"],data.get("hermes_python"),data.get("hermes_source"))


def parser():
    p=argparse.ArgumentParser(description="Single-user research management: setup once, then omit profile/project for daily commands.")
    p.add_argument("--data-root",required=True)
    sub=p.add_subparsers(dest="command",required=True)
    init=sub.add_parser("init");init.add_argument("--hermes-root",required=True);init.add_argument("--hermes-python");init.add_argument("--hermes-source")
    project=sub.add_parser("project-add")
    for name in ("id","title","brief","query"):project.add_argument("--"+name,required=True)
    project.add_argument("--time",default="10:00");project.add_argument("--timezone",default="Asia/Shanghai")
    setup=sub.add_parser("setup",help="Select one personal Hermes profile and default project; keep all historical data")
    setup.add_argument("--profile");setup.add_argument("--project");setup.add_argument("--user-id")
    service=setup.add_mutually_exclusive_group()
    service.add_argument("--service-profile",help="Reuse an existing registered collector; not required for a new single-user install")
    service.add_argument("--no-service",action="store_true",help="Explicitly stop selecting a legacy collector; inspect its existing cron before doing this")
    current=sub.add_parser("current",help="Show the selected personal identity and default project, without secrets")
    current.add_argument("--profile");current.add_argument("--collector",action="store_true")
    user=sub.add_parser("user-add",help="Legacy compatibility; new single-user installs use setup instead");user.add_argument("--id",required=True);user.add_argument("--profile",required=True);user.add_argument("--service",action="store_true");user.add_argument("--resume",action="store_true")
    member=sub.add_parser("member",help="Legacy membership maintenance; setup assigns the selected user's default project");member.add_argument("--project",required=True);member.add_argument("--user",required=True)
    member.add_argument("--role",type=lambda value:{"owner":"user","editor":"user","reader":"user"}.get(value,value),choices=["user","service"],help="Defaults to the registered identity; legacy human roles map to user.")
    sync=sub.add_parser("permissions-sync",help="Preview/apply tool settings for the selected user; --all includes the selected legacy collector")
    targets=sync.add_mutually_exclusive_group()
    targets.add_argument("--profile");targets.add_argument("--all",action="store_true")
    sync.add_argument("--apply",action="store_true",help="Back up config.yaml, apply permissions and normalize legacy memberships")
    revoke=sub.add_parser("revoke");revoke.add_argument("--project",required=True);revoke.add_argument("--user",required=True)
    disable=sub.add_parser("disable");disable.add_argument("--user",required=True)
    binding=sub.add_parser("bind",help="Future channel identity metadata only; does not enable a messaging connector")
    for key in ("platform","account","sender","user"):binding.add_argument("--"+key,required=True)
    binding.add_argument("--tenant",default="")
    routes=sub.add_parser("routes",help="Preview future channel routes; live messaging ingress remains disabled");routes.add_argument("--platform",required=True);routes.add_argument("--account",required=True)
    for name in ("doctor","snapshot","update","schedule"):
        item=sub.add_parser(name);item.add_argument("--profile")
        if name!="doctor":item.add_argument("--project")
        if name=="update":item.add_argument("--force",action="store_true");item.add_argument("--lookback-days",type=int,default=30)
    local=sub.add_parser("import")
    for name in ("profile","project","file"):local.add_argument("--"+name,required=name=="file")
    local.add_argument("--kind",choices=["note","experience","problem","experiment"],default="note")
    local.add_argument("--shared",action="store_true")
    auto=sub.add_parser("auto-explore");auto.add_argument("--project");auto.add_argument("--enabled",choices=["true","false"],required=True)
    sub.add_parser("inspect")
    shared=sub.add_parser("shared-bind",help="Bind one explicitly shared CRA database to one project")
    for name in ("project","python","repository","env-file"):shared.add_argument("--"+name,required=name!="project")
    check=sub.add_parser("shared-check");check.add_argument("--profile");check.add_argument("--project")
    review=sub.add_parser("review",help="Local human review; never registered as an Agent tool")
    for name in ("profile","project","record"):review.add_argument("--"+name,required=name=="record")
    review.add_argument("--version",type=int,required=True);review.add_argument("--status",choices=["confirmed","rejected","superseded"],required=True)
    review.add_argument("--fields-json")
    structured=sub.add_parser("import-json")
    for name in ("profile","project","file"):structured.add_argument("--"+name,required=name=="file")
    structured.add_argument("--shared",action="store_true")
    export=sub.add_parser("export-shared")
    for name in ("profile","project","record"):export.add_argument("--"+name,required=name=="record")
    export.add_argument("--version",type=int,required=True)
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
        elif args.command=="setup":
            from .runtime.hermes.single_user import setup
            data=setup(registry,command_from(registry),source,args.profile,args.project,args.user_id,args.service_profile,args.no_service)
        elif args.command=="current":data=registry.current(args.profile,service=args.collector)
        elif args.command=="user-add":data=provision(registry,command_from(registry),source,args.id,args.profile,"service" if args.service else "user",args.resume)
        elif args.command=="member":registry.set_member(args.project,args.user,args.role);data={"updated":True}
        elif args.command=="permissions-sync":
            profiles=([u["profile"] for u in registry.selected_users()] if args.all else [registry.current(args.profile)["profile"]])
            command=command_from(registry)
            data={"applied":args.apply,"profiles":[sync_permissions(registry,command,profile,args.apply) for profile in profiles]}
        elif args.command=="revoke":registry.revoke(args.project,args.user);data={"revoked":True}
        elif args.command=="disable":registry.disable(args.user);data={"disabled":True}
        elif args.command=="bind":registry.bind(args.platform,args.account,args.tenant,args.sender,args.user);data={"bound":True}
        elif args.command=="routes":
            from .adapters.channels import routing_plan
            data=routing_plan(registry,args.account,args.platform)
        elif args.command=="doctor":data=doctor(registry,command_from(registry),registry.current(args.profile)["profile"])
        elif args.command=="schedule":
            current=registry.current(args.profile,service=True)
            data=schedule(registry,command_from(registry),current["profile"],args.project or current["project_id"],source)
        elif args.command=="auto-explore":
            registry.set_auto_explore(args.project or registry.current()["project_id"],args.enabled=="true")
            data={"updated":True,"note":"Reconfigure the existing Hermes job to agent mode before enabling automatic ideation; existing schedules are not silently rewritten."}
        elif args.command=="inspect":data={"mode":"single-user","selection":registry.single_user(),**registry.inspect()}
        elif args.command=="shared-bind":
            args.project=args.project or registry.current()["project_id"]
            registry.project(args.project)
            path=registry.config.data_root/"control"/"shared-context.json"
            values={"project_id":args.project,"python":str(Path(args.python).resolve()),"repository":str(Path(args.repository).resolve()),"env_file":str(Path(args.env_file).resolve())}
            require(Path(values["python"]).is_file() and Path(values["env_file"]).is_file() and (Path(values["repository"])/"src/cra/store/models.py").is_file(),"INVALID_CONFIG","Verify CRA interpreter, repository and env file.")
            if path.is_file():require(json.loads(path.read_text(encoding="utf-8"))["project_id"]==args.project,"SHARED_CONTEXT_BOUND","The unpartitioned public database is already bound to another project.")
            path.write_text(json.dumps(values,ensure_ascii=False,indent=2),encoding="utf-8")
            data={"bound":True,"project_id":args.project,"scope":"One explicitly shared CRA public database; not multi-project isolation."}
        else:
            user=registry.current(args.profile,service=args.command=="update")
            ctx=resolve_context(registry,user["profile"],user["home"],args.project)
            if args.command=="shared-check":
                from .store.shared import SharedContext
                data=SharedContext(registry,ctx).call("check")
            elif args.command=="review":
                from .storage import Store,public_record
                fields=json.loads(Path(args.fields_json).read_text(encoding="utf-8-sig")) if args.fields_json else None
                data=public_record(Store(registry,ctx).review(args.record,args.version,args.status,fields))
            elif args.command=="export-shared":
                from .storage import Store
                store=Store(registry,ctx);record=store.get(args.record)
                require(record["version"]==args.version,"VERSION_CONFLICT","Read the current record first.")
                data=store.export_shared(record)
            elif args.command=="import-json":
                from .storage import Store,public_record
                from .records import TYPE_TO_KIND
                path=Path(args.file)
                require(path.stat().st_size<=10_000_000,"INVALID_INPUT","Import file too large.")
                content=path.read_text(encoding="utf-8-sig")
                values=[json.loads(line) for line in content.splitlines() if line.strip()] if path.suffix==".jsonl" else json.loads(content)
                rows=values if isinstance(values,list) else [values]
                require(1<=len(rows)<=100,"INVALID_INPUT","Import 1..100 records.")
                store=Store(registry,ctx);items=[]
                for row in rows:
                    require(isinstance(row,dict),"INVALID_INPUT","Each record must be an object.")
                    require(row.get("status","draft")=="draft","HUMAN_REVIEW_REQUIRED","Import drafts, then review explicitly.")
                    kind=TYPE_TO_KIND.get(row.get("type"),row.get("kind","note"))
                    sources=[{**{key:value for key,value in s.items() if key in {"kind","sha256","coverage"}},"uri":s.get("uri",s.get("ref","")),"locator":s.get("locator") or ""} for s in row.get("sources",[])]
                    fields=row.get("fields",{key:value for key,value in row.items() if key not in {"type","kind","id","title","body","status","created_by","sources","refs","links","visibility"}})
                    refs=list(row.get("refs",[]))
                    for link in row.get("links",[]):
                        target=store.get(link["target_id"])
                        refs.append({"id":target["id"],"version":link.get("version",target["version"]),"quote":link.get("quote","")})
                    items.append({"kind":kind,"title":row["title"],"body":row.get("body") or row["title"],"visibility":"project" if args.shared else "private","refs":refs,"fields":fields,"sources":sources,"record_id":row.get("id")})
                data=[public_record(record) for record in store.import_drafts(items)]
            elif args.command=="snapshot":
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
