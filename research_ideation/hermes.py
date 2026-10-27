"""Hermes scope check; per-container settings replace the global user registry."""

from pathlib import Path
from .context import Config
from .database import Database
from .models import require


class HermesRuntime:
    def __init__(self, plugin_context):
        from hermes_constants import get_hermes_home
        self.plugin_context = plugin_context
        self.home = Path(get_hermes_home()).resolve()
        self.profile = plugin_context.profile_name

    def database(self):
        from hermes_constants import get_hermes_home
        from gateway.session_context import get_session_env
        require(Path(get_hermes_home()).resolve() == self.home and self.plugin_context.profile_name == self.profile,
                "IDENTITY_DENIED", "Plugin registration differs from the executing Hermes Home or profile.")
        platform = get_session_env("HERMES_SESSION_PLATFORM", "") or "cli"
        require(platform in {"cli", "local", "terminal"}, "CHANNEL_NOT_CERTIFIED", "Use a deployment-launched CLI in the user's container; messaging ingress is not configured for this MVP.")
        root = self.plugin_context.get_config("data_root", "")
        require(isinstance(root, str) and root, "SETUP_REQUIRED", "Configure plugins.entries.research-ideation.settings.data_root in this Hermes Home.")
        return Database(Config.from_root(root))
