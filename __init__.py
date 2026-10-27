"""Hermes directory plugin entry point: registration only, no network or writes."""

from pathlib import Path
from .schemas import SCHEMAS
from .tools import make_handler
from .research_ideation.hermes import HermesRuntime


def register(ctx):
    runtime=HermesRuntime(ctx)
    for schema in SCHEMAS:
        ctx.register_tool(name=schema["name"],toolset="research_ideation",schema=schema,
                          handler=make_handler(schema["name"],runtime,schema["parameters"]))
    ctx.register_skill("problem-exploration",Path(__file__).parent/"skills"/"problem-exploration"/"SKILL.md")
