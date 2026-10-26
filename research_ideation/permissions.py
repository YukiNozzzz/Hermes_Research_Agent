from .models import require


def revalidate(registry, ctx):
    user = registry.user(ctx.profile, ctx.profile_home)
    role = registry.member(user["user_id"], ctx.project_id)
    require(user["user_id"] == ctx.user_id and role == ctx.role, "ACCESS_DENIED", "Identity or membership changed; start a fresh request.")


def can_read(registry, ctx, record):
    revalidate(registry, ctx)
    return record["project_id"] == ctx.project_id and (
        record["visibility"] == "project" or (ctx.role != "service" and record["owner_id"] == ctx.user_id))


def write_scope(registry, ctx, visibility):
    revalidate(registry, ctx)
    require(visibility in {"private", "project"}, "INVALID_SCOPE", "Use private or project.")
    require(ctx.role != "reader" or visibility == "private", "ACCESS_DENIED", "Read-only members cannot change shared records.")
    require(ctx.role != "service" or visibility == "project", "ACCESS_DENIED", "Service tasks cannot access personal storage.")


def can_edit(registry, ctx, record):
    write_scope(registry, ctx, record["visibility"])
    require(record["owner_id"] == ctx.user_id or (record["visibility"] == "project" and ctx.role == "owner"), "ACCESS_DENIED", "Only the author or project owner can edit this record.")
