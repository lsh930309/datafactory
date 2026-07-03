from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from .inpaint import InpaintResult, render_inpaint_comparison


def write_inpaint_result(result: InpaintResult, output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    mask_path = output_dir / "mask.png"
    overlay_path = output_dir / "mask_overlay.png"
    image_path = output_dir / f"inpainted_{result.method}.png"
    comparison_path = output_dir / f"comparison_{result.method}.png"
    summary_path = output_dir / "summary.json"

    original = Image.open(result.source_image).convert("RGB")
    result.mask.save(mask_path)
    result.mask_overlay.save(overlay_path)
    result.image.save(image_path)
    render_inpaint_comparison(original, result.mask, result.mask_overlay, result.image).save(comparison_path)

    paths = {
        "mask": mask_path,
        "mask_overlay": overlay_path,
        "inpainted": image_path,
        "comparison": comparison_path,
    }
    summary = result.summary(paths | {"summary": summary_path})
    with summary_path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    paths["summary"] = summary_path
    return paths
