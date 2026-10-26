from pathlib import Path
from ..artifacts import contained
from ..models import require,bounded_text


def read_from_inbox(root,relative_name):
    name=Path(relative_name)
    require(not name.is_absolute() and ".." not in name.parts and name.suffix.lower() in {".md",".txt"},"INVALID_PATH","Import only relative .md/.txt files under the configured inbox.")
    path=contained(root,*name.parts)
    require(path.is_file() and path.stat().st_size<=500_000,"INVALID_INPUT","Missing or oversized local document.")
    return bounded_text(path.read_text(encoding="utf-8"),"document")
