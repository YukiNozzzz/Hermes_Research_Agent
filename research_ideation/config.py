"""Explicit data roots; private locations come from the active profile, never globals."""

from dataclasses import dataclass
from pathlib import Path
from .models import require


@dataclass(frozen=True)
class Config:
    data_root: Path

    @classmethod
    def from_root(cls, value):
        path = Path(value).expanduser()
        require(path.is_absolute(), "CONFIG_REQUIRED", "data_root must be an absolute administrator-configured path.")
        return cls(path.resolve())

    @property
    def registry_path(self):
        return self.data_root / "control" / "registry.sqlite"
