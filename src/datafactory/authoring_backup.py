from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROTECTED_AUTHORING_FILENAMES = {
    "schema.json",
    "stylesheet.json",
    "faker_profile.json",
    "semantic_schema.json",
}


def is_protected_authoring_file(path: Path) -> bool:
    """Return True for canonical authoring JSON files that must be backed up.

    Render artifacts under authoring/render_preview and backup copies themselves
    are intentionally excluded.  This keeps routine preview generation cheap
    while protecting the human-edited authoring source of truth.
    """

    parts = path.resolve().parts
    if path.name not in PROTECTED_AUTHORING_FILENAMES:
        return False
    if "authoring" not in parts:
        return False
    if "backups" in parts:
        return False
    if "render_preview" in parts:
        return False
    return True


def backup_dir_for_authoring_file(path: Path, *, timestamp: str | None = None) -> Path:
    resolved = path.resolve()
    parts = resolved.parts
    if "authoring" not in parts:
        raise ValueError(f"not an authoring path: {path}")
    idx = parts.index("authoring")
    authoring_dir = Path(*parts[: idx + 1])
    stamp = timestamp or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return authoring_dir / "backups" / stamp


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def backup_authoring_json_before_write(
    path: Path,
    *,
    next_payload: Any | None = None,
    next_text: str | None = None,
    reason: str = "overwrite",
) -> Path | None:
    """Backup an existing protected authoring JSON file before overwriting it.

    Returns the copied backup path, or None when the target is not a protected
    authoring file, does not exist yet, or the next content is byte-identical.
    The function is deliberately safe to call from every JSON writer.
    """

    path = Path(path)
    if not is_protected_authoring_file(path):
        return None
    if not path.exists() or not path.is_file():
        return None

    if next_text is None and next_payload is not None:
        next_text = json.dumps(next_payload, ensure_ascii=False, indent=2) + "\n"
    if next_text is not None:
        try:
            if path.read_text(encoding="utf-8") == next_text:
                return None
        except UnicodeDecodeError:
            pass

    backup_dir = backup_dir_for_authoring_file(path)
    backup_dir.mkdir(parents=True, exist_ok=False)
    backup_path = backup_dir / path.name
    shutil.copy2(path, backup_path)

    manifest = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "reason": reason,
        "source": str(path.resolve()),
        "backup": str(backup_path.resolve()),
        "source_size": path.stat().st_size,
        "source_sha256": _sha256(path),
    }
    (backup_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return backup_path
