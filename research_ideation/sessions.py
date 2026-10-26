"""Hermes owns transcripts; only enforce the application binding here."""

from .permissions import revalidate


def describe_session(registry, ctx):
    revalidate(registry, ctx)
    return {"user_id":ctx.user_id,"profile":ctx.profile,"project_id":ctx.project_id,"session_id":ctx.session_id,"platform":ctx.platform}
