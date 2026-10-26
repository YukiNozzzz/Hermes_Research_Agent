"""Small version-audited Hermes seam, with no global mutable current-user state."""

from pathlib import Path
from ..config import Config
from ..registry import Registry
from ..context import resolve_context
from ..models import require


class HermesRuntime:
    def __init__(self,plugin_context):
        self.plugin_context=plugin_context
        from hermes_constants import get_hermes_home
        self.home=Path(get_hermes_home()).resolve()
        self.profile=plugin_context.profile_name

    def context(self,project_id=None):
        from hermes_constants import get_hermes_home
        from gateway.session_context import get_session_env
        home=Path(get_hermes_home()).resolve()
        require(home==self.home and self.plugin_context.profile_name==self.profile,"IDENTITY_DENIED","Plugin registration scope differs from the executing profile.")
        platform=get_session_env("HERMES_SESSION_PLATFORM","") or "cli"
        # Native messaging sender/account provenance needs a certified ingress bridge.
        # Fail closed, rather than taking identity parameters from model arguments.
        require(platform in {"cli","local","terminal"},"CHANNEL_NOT_CERTIFIED","Messaging ingress is not certified for this MVP. Use an administrator-launched profile CLI.")
        root=self.plugin_context.get_config("data_root","")
        require(isinstance(root,str) and root,"SETUP_REQUIRED","Configure plugins.entries.research-ideation.settings.data_root in this profile.")
        registry=Registry(Config.from_root(root))
        ctx=resolve_context(registry,self.profile,home,project_id,get_session_env("HERMES_SESSION_ID","") or "",platform)
        return registry,ctx
