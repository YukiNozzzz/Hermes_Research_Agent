from .permissions import revalidate


def describe(registry,ctx):
    revalidate(registry,ctx)
    return registry.project(ctx.project_id)
