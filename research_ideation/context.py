from .models import ExecutionContext, require, identifier


def resolve_context(registry, profile, home, project_id=None, session_id="", platform="cli"):
    """Called by trusted host/administrator entrypoints, never with model-supplied identity."""
    user = registry.user(profile, home)
    if not project_id:
        projects = registry.project_ids(user["user_id"])
        require(len(projects) == 1, "PROJECT_REQUIRED", "Specify one project you belong to.")
        project_id = projects[0]
    identifier(project_id)
    role = registry.member(user["user_id"], project_id)
    require((role == "service") == (user["kind"] == "service"), "ACCESS_DENIED", "Identity role mismatch.")
    return ExecutionContext(user["user_id"], profile, str(home), project_id, role, session_id, platform)
