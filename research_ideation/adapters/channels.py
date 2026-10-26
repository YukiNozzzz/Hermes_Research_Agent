"""Channel binding seam. Only a trusted ingress adapter may attest an identity."""

from dataclasses import dataclass
from ..models import require


@dataclass(frozen=True)
class InboundIdentity:
    platform: str
    account: str
    tenant: str
    sender: str
    chat_id: str
    profile: str


def resolve_inbound(registry,identity,verified=False):
    require(verified,"IDENTITY_DENIED","A trusted channel adapter must authenticate the inbound identity.")
    user=registry.binding(identity.platform,identity.account,identity.tenant,identity.sender)
    require(user["profile"]==identity.profile,"IDENTITY_DENIED","Inbound sender was routed to the wrong profile.")
    return user


def routing_plan(registry,account,platform):
    """Administrator preview only; never silently writes a live gateway configuration."""
    state=registry.inspect()
    users={u["user_id"]:u for u in state["users"] if u["active"]}
    bindings=[b for b in state["bindings"] if b["platform"]==platform and b["account"]==account and b["user_id"] in users]
    return {"routes":[{"name":"research-"+users[b["user_id"]]["profile"],"platform":platform,"user_id":b["sender"],
                       "profile":users[b["user_id"]]["profile"],**({"guild_id":b["tenant"]} if b["tenant"] else {})} for b in bindings],
            "allowed_senders":[b["sender"] for b in bindings],
            "warnings":["Merge into the receiving bot's configuration, verify bot_profile/account scope, command gating and allowlist first.",
                        "Sender routes do not authorize cron delivery. Add verified location routes for outbound delivery.",
                        "Live non-CLI ingress remains disabled in this MVP until its authenticated metadata integration is certified."]}
