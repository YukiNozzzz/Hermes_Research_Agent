from .models import ExecutionContext, require, identifier


def resolve_context(registry, profile, home, project_id=None, session_id="", platform="cli"):
    """Called by trusted host/administrator entrypoints, never with model-supplied identity."""
    user = registry.user(profile, home)
    if not project_id:
        policy = registry.require_selected(user["user_id"])
        projects = registry.project_ids(user["user_id"])
        project_id = policy["project_id"]
        require(project_id in projects, "ACCESS_DENIED", "The selected identity is not a member of the default project.")
    identifier(project_id)
    role = registry.member(user["user_id"], project_id)
    require((role == "service") == (user["kind"] == "service"), "ACCESS_DENIED", "Identity role mismatch.")
    return ExecutionContext(user["user_id"], profile, str(home), project_id, role, session_id, platform)
