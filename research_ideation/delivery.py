"""No external sending in MVP. Persist explicit receivers; never infer the last active chat."""

from .models import require
from .adapters.channels import resolve_inbound
from .tasks import get_task


def prepare_delivery(registry,ctx,task_id,identity,verified=False):
    receiver=resolve_inbound(registry,identity,verified)
    require(receiver["user_id"]==ctx.user_id,"ACCESS_DENIED","A task cannot be delivered as another user.")
    task=get_task(registry,ctx,task_id)
    require(task["status"] in {"completed","no_candidate"},"TASK_NOT_READY","No completed result to deliver.")
    return {"task_id":task_id,"recipient":receiver["user_id"],"platform":identity.platform,"account":identity.account,
            "chat_id":identity.chat_id,"state":"not_sent","reason":"Live channel delivery is not enabled in MVP."}
