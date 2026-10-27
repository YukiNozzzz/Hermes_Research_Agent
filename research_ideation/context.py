"""Local deployment configuration; no PostgreSQL identity registry."""

from dataclasses import dataclass
from pathlib import Path
from .models import require


@dataclass(frozen=True)
class Config:
    data_root: Path

    @classmethod
    def from_root(cls, value):
        path = Path(value).expanduser()
        require(path.is_absolute(), "CONFIG_REQUIRED", "data_root must be an absolute deployment-configured path.")
        return cls(path.resolve())
