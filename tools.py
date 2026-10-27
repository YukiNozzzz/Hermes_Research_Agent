"""Read-only input handler; no finish, upload or report operation."""

import json
from .research_ideation.models import ResearchError, require
from .research_ideation.ideation import start


def make_handler(name, runtime, parameters):
    allowed, required = set(parameters["properties"]), set(parameters["required"])

    def handler(args, **kwargs):
        try:
            require(name == "research_start", "UNKNOWN_OPERATION", "Only research_start is available.")
            require(isinstance(args, dict) and set(args) <= allowed and required <= set(args),
                    "INVALID_INPUT", "Missing or unsupported operation arguments.")
            data = start(runtime.database(), **args)
            return json.dumps({"ok": True, "data": data, "error": None}, ensure_ascii=False)
        except ResearchError as exc:
            error = {"code": exc.code, "message": str(exc), "retryable": exc.retryable}
        except (TypeError, ValueError, KeyError):
            error = {"code": "INVALID_INPUT", "message": "Invalid argument type or value.", "retryable": False}
        except Exception:
            error = {"code": "INTERNAL_ERROR", "message": "Research inputs could not be loaded. Ask the administrator to check the operation.", "retryable": False}
        return json.dumps({"ok": False, "data": None, "error": error}, ensure_ascii=False)

    return handler
