from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import TemplateSpec


def load_template(path: Path | str) -> TemplateSpec:
    template_path = Path(path)
    with template_path.open("r", encoding="utf-8") as handle:
        raw: dict[str, Any] = json.load(handle)
    return TemplateSpec.from_dict(raw, base_dir=template_path.parent)


def save_template(template: TemplateSpec, path: Path | str) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        json.dump(template.to_dict(), handle, ensure_ascii=False, indent=2)
        handle.write("\n")
