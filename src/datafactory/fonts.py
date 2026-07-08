from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import re
from typing import Any

from PIL import ImageFont

ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_FONTS = ROOT / "fonts"
KOREAN_FONT_CANDIDATES = [
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/System/Library/Fonts/Supplemental/NotoSansCJK-Regular.ttc",
    "/Library/Fonts/NotoSansCJK-Regular.ttc",
    str(WORKSPACE_FONTS / "malgun.ttf"),
    str(WORKSPACE_FONTS / "batang.ttc"),
]
FONT_EXTENSIONS = {".ttf", ".otf", ".ttc", ".otc"}
SYSTEM_FONT_DIRS = [
    Path("/System/Library/Fonts"),
    Path("/System/Library/Fonts/Supplemental"),
    Path("/Library/Fonts"),
    Path.home() / "Library" / "Fonts",
]
KOREAN_FONT_TOKENS = (
    "apple sd gothic",
    "applesdgothic",
    "apple gothic",
    "applegothic",
    "malgun",
    "nanum",
    "noto sans cjk",
    "noto serif cjk",
    "notosanscjk",
    "notoserifcjk",
    "source han",
    "sourcehan",
    "pretendard",
    "spoqa",
    "kopub",
    "maruburi",
    "hana",
    "batang",
    "dotum",
    "gulim",
    "gungsuh",
    "gothic",
    "myeongjo",
    "고딕",
    "명조",
    "바탕",
    "돋움",
    "굴림",
    "궁서",
    "맑은",
    "나눔",
)


@dataclass(frozen=True)
class FontFace:
    id: str
    family: str
    style: str
    weight: str
    font_style: str
    source: str
    path: str
    absolute_path: str
    index: int
    label: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "family": self.family,
            "style": self.style,
            "weight": self.weight,
            "fontStyle": self.font_style,
            "source": self.source,
            "path": self.path,
            "absolutePath": self.absolute_path,
            "index": self.index,
            "label": self.label,
        }


def default_font_path() -> str | None:
    for candidate in KOREAN_FONT_CANDIDATES:
        if Path(candidate).exists():
            return str(Path(candidate).resolve())
    return None


def load_font(size: int, path: str | None = None, index: int | None = None) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    requested = _resolve_font_file(path) or default_font_path()
    font_index = max(0, int(index or 0))
    if requested:
        try:
            return ImageFont.truetype(requested, size=size, index=font_index)
        except (OSError, TypeError):
            try:
                return ImageFont.truetype(requested, size=size)
            except OSError:
                pass
    return ImageFont.load_default(size=size)


def list_font_faces(root: Path = ROOT, *, refresh: bool = False) -> list[dict[str, Any]]:
    if refresh:
        _scan_font_faces.cache_clear()
    return [face.to_dict() for face in _scan_font_faces(str(root.resolve()))]


def default_font_id(root: Path = ROOT) -> str | None:
    default = default_font_path()
    faces = _scan_font_faces(str(root.resolve()))
    if default:
        resolved = str(Path(default).resolve())
        for face in faces:
            if face.absolute_path == resolved and face.index == 0:
                return face.id
    return faces[0].id if faces else None


def resolve_font_path(
    *,
    font_path: str | None = None,
    font_family: str | None = None,
    font_weight: str | None = None,
    font_style: str | None = None,
    font_index: int | None = None,
    root: Path = ROOT,
) -> tuple[str | None, int]:
    explicit = _resolve_font_file(font_path, root=root)
    family_key = _font_family_key(font_family or "")
    if family_key:
        requested_weight = _normalize_weight(font_weight or "")
        requested_style = _normalize_font_style(font_style or "")
        candidates = [face for face in _scan_font_faces(str(root.resolve())) if _font_family_key(face.family) == family_key]
        if candidates:
            explicit_resolved = str(Path(explicit).resolve()) if explicit else ""
            candidates.sort(key=lambda face: _font_match_score(face, requested_weight, requested_style, explicit_resolved, max(0, int(font_index or 0))))
            best = candidates[0]
            return best.absolute_path, best.index
    if explicit:
        return explicit, max(0, int(font_index or 0))
    return default_font_path(), 0


def _font_match_score(face: FontFace, requested_weight: str, requested_style: str, explicit_path: str = "", explicit_index: int = 0) -> tuple[int, int, int, str]:
    weight_score = 0 if not requested_weight or face.weight == requested_weight else 1
    style_score = 0 if not requested_style or face.font_style == requested_style else 1
    explicit_score = 0 if explicit_path and face.absolute_path == explicit_path and face.index == explicit_index else 1
    return (weight_score, style_score, explicit_score, face.label.lower())


def _font_family_key(value: str) -> str:
    """Normalize UI/style family names for matching scanned font faces.

    macOS reports several families with spaces (for example
    ``Apple SD Gothic Neo``), while existing authoring data often stores the
    PostScript-like compact alias (``AppleSDGothicNeo``).  The renderer should
    still be able to resolve the requested bold face from that alias.
    """

    text = str(value or "").strip().lower().lstrip(".")
    return re.sub(r"[^0-9a-z가-힣]+", "", text)


@lru_cache(maxsize=4)
def _scan_font_faces(root_str: str) -> tuple[FontFace, ...]:
    root = Path(root_str)
    files: list[tuple[Path, str]] = []
    workspace = root / "fonts"
    if workspace.exists():
        files.extend((path, "workspace") for path in _iter_font_files([workspace]))
    files.extend((path, "system") for path in _iter_font_files(SYSTEM_FONT_DIRS))

    faces: list[FontFace] = []
    seen: set[tuple[str, int]] = set()
    for path, source in files:
        resolved = path.resolve()
        for index in _iter_font_indices(resolved):
            key = (str(resolved), index)
            if key in seen:
                continue
            seen.add(key)
            face = _read_font_face(resolved, index, source=source, root=root)
            if face and _is_korean_capable_face(face):
                faces.append(face)
    faces.sort(key=lambda face: (face.source != "workspace", face.family.lower(), face.style.lower(), face.path.lower(), face.index))
    return tuple(faces)


def _iter_font_files(dirs: list[Path]) -> list[Path]:
    files: list[Path] = []
    for directory in dirs:
        if not directory.exists():
            continue
        files.extend(path for path in directory.rglob("*") if path.is_file() and path.suffix.lower() in FONT_EXTENSIONS)
    return sorted(files, key=lambda path: str(path).lower())


def _iter_font_indices(path: Path) -> list[int]:
    indices: list[int] = []
    limit = 64 if path.suffix.lower() in {".ttc", ".otc"} else 1
    for index in range(limit):
        try:
            ImageFont.truetype(str(path), size=12, index=index)
        except (OSError, TypeError):
            if index == 0:
                return []
            break
        indices.append(index)
    return indices or [0]


def _read_font_face(path: Path, index: int, *, source: str, root: Path) -> FontFace | None:
    try:
        font = ImageFont.truetype(str(path), size=12, index=index)
        family, style = font.getname()
    except (OSError, TypeError, ValueError):
        return None
    family = (family or path.stem).strip() or path.stem
    style = (style or "Regular").strip() or "Regular"
    rel_path = _display_path(path, root) if source == "workspace" else str(path)
    font_id = f"{source}:{rel_path}#{index}"
    label = f"{family} {style} · {rel_path}"
    return FontFace(
        id=font_id,
        family=family,
        style=style,
        weight=_normalize_weight(style),
        font_style=_normalize_font_style(style),
        source=source,
        path=rel_path,
        absolute_path=str(path),
        index=index,
        label=label,
    )


def _is_korean_capable_face(face: FontFace) -> bool:
    """Keep the UI font selector focused on fonts likely to render Korean text.

    PIL does not expose a reliable glyph-coverage API for every font backend, so
    the registry uses the workspace font folder plus conservative family/path
    tokens for well-known Korean/CJK fonts. The renderer can still load an
    explicit font path directly through ``load_font``/``resolve_font_path`` even
    if it is not shown in this authoring selector.
    """

    if face.source == "workspace":
        return True
    haystack = " ".join([face.family, face.style, face.path, face.label]).lower()
    compact = re.sub(r"[^0-9a-z가-힣]+", "", haystack)
    return any(token in haystack or re.sub(r"[^0-9a-z가-힣]+", "", token) in compact for token in KOREAN_FONT_TOKENS)


def _display_path(path: Path, root: Path = ROOT) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def _resolve_font_file(path: str | None, *, root: Path = ROOT) -> str | None:
    if not path:
        return None
    candidate = Path(str(path)).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    if candidate.exists() and candidate.is_file() and candidate.suffix.lower() in FONT_EXTENSIONS:
        return str(candidate.resolve())
    return None


def _normalize_weight(value: str) -> str:
    text = str(value or "").lower()
    if any(token in text for token in ("black", "heavy", "extrabold", "extra bold", "ultrabold", "ultra bold")):
        return "black"
    if any(token in text for token in ("bold", "semibold", "semi bold", "demibold", "demi bold")):
        return "bold"
    if any(token in text for token in ("light", "thin")):
        return "light"
    return "normal"


def _normalize_font_style(value: str) -> str:
    text = str(value or "").lower()
    if any(token in text for token in ("italic", "oblique", "slanted")):
        return "italic"
    return "normal"
