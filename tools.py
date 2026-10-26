"""Thin plugin handlers; identities and configuration never come from model parameters."""

import json
from .research_ideation.models import ResearchError,require
from .research_ideation import memory,knowledge,tasks,sharing
from .research_ideation.workflows.daily_update import update


def make_handler(name,runtime,parameters):
    allowed=set(parameters["properties"])
    required=set(parameters["required"])
    def handler(args,**kwargs):
        try:
            require(isinstance(args,dict) and set(args)<=allowed and required<=set(args),"INVALID_INPUT","Missing or unsupported operation arguments.")
            values=dict(args)
            registry,ctx=runtime.context(values.pop("project_id",None))
            if name=="research_project": data=memory.snapshot(registry,ctx)
            elif name=="research_record": data=memory.record(registry,ctx,**values)
            elif name=="research_search": data=knowledge.search(registry,ctx,**values)
            elif name=="research_read": data=knowledge.read(registry,ctx,**values)
            elif name=="research_start": data=tasks.start(registry,ctx,**values)
            elif name=="research_finish": data=tasks.finish(registry,ctx,**values)
            elif name=="research_publish":
                action=values.pop("action")
                require(action in {"publish","withdraw"},"INVALID_INPUT","Unknown publish action.")
                data=(sharing.publish if action=="publish" else sharing.withdraw)(registry,ctx,values["record_id"],values["version"])
            elif name=="research_feedback": data=tasks.feedback(registry,ctx,**values)
            elif name=="research_update_papers": data=update(registry,ctx,**values)
            else: raise ResearchError("UNKNOWN_OPERATION","Unknown operation.")
            return json.dumps({"ok":True,"data":data,"error":None},ensure_ascii=False)
        except ResearchError as exc:
            return json.dumps({"ok":False,"data":None,"error":{"code":exc.code,"message":str(exc),"retryable":exc.retryable}},ensure_ascii=False)
        except (TypeError,ValueError,KeyError):
            return json.dumps({"ok":False,"data":None,"error":{"code":"INVALID_INPUT","message":"Invalid argument type or value.","retryable":False}})
        except Exception as exc:
            # Do not echo filesystem paths, credentials or cross-profile exception contents to the model.
            return json.dumps({"ok":False,"data":None,"error":{"code":"INTERNAL_ERROR","message":"Operation failed ("+type(exc).__name__+"). Ask the administrator to inspect the operation.","retryable":False}})
    return handler
