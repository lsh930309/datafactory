from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps

from .manual_cleanup import combine_masks
from .models import BBox

InpaintMethod = Literal["telea", "ns", "fill", "lama"]
MaskShape = Literal["bbox", "polygon"]


@dataclass(frozen=True)
class InpaintConfig:
    method: InpaintMethod = "lama"
    mask_shape: MaskShape = "bbox"
    padding: int = 2
    dilation: int = 1
    radius: float = 3.0
    lama_max_side: int = 2400
    extra_mask_path: Path | None = None


@dataclass(frozen=True)
class InpaintResult:
    source_image: Path
    detections_path: Path
    image_width: int
    image_height: int
    detection_count: int
    mask_pixels: int
    mask_ratio: float
    method: InpaintMethod
    mask_shape: MaskShape
    padding: int
    dilation: int
    radius: float
    lama_max_side: int
    image: Image.Image
    mask: Image.Image
    mask_overlay: Image.Image

    def summary(self, paths: dict[str, Path]) -> dict[str, Any]:
        return {
            "source_image": str(self.source_image),
            "detections": str(self.detections_path),
            "image": {"width": self.image_width, "height": self.image_height},
            "detection_count": self.detection_count,
            "mask_pixels": self.mask_pixels,
            "mask_ratio": self.mask_ratio,
            "method": self.method,
            "mask_shape": self.mask_shape,
            "padding": self.padding,
            "dilation": self.dilation,
            "radius": self.radius,
            "lama_max_side": self.lama_max_side,
            "outputs": {name: str(path) for name, path in paths.items()},
        }


@dataclass(frozen=True)
class _DetectionRegion:
    bbox: BBox
    polygon: list[list[int]]


def inpaint_from_detections(detections_path: Path, config: InpaintConfig) -> InpaintResult:
    payload = json.loads(detections_path.read_text(encoding="utf-8"))
    source_image = Path(payload["source_image"])
    regions = [_region_from_detection(item) for item in payload.get("detections", [])]
    return _inpaint_regions(source_image, detections_path, regions, config)


def inpaint_from_review_policy(review_path: Path, config: InpaintConfig) -> InpaintResult:
    from .policy import load_review_policy, use_labels

    policy = load_review_policy(review_path)
    regions = [_DetectionRegion(bbox=label.bbox, polygon=label.polygon) for label in use_labels(policy)]
    return _inpaint_regions(policy.source_image, review_path, regions, config)


def _inpaint_regions(source_image: Path, detections_path: Path, regions: list[_DetectionRegion], config: InpaintConfig) -> InpaintResult:
    image = Image.open(source_image).convert("RGB")
    mask = build_detection_mask(image.size, regions, config)
    if config.extra_mask_path is not None:
        extra_mask = Image.open(config.extra_mask_path).convert("L")
        mask = combine_masks(mask, extra_mask)
    inpainted = apply_inpaint(image, mask, regions, config)
    mask_overlay = render_mask_overlay(image, mask)
    mask_pixels = int(np.count_nonzero(np.asarray(mask)))
    image_width, image_height = image.size
    return InpaintResult(
        source_image=source_image,
        detections_path=detections_path,
        image_width=image_width,
        image_height=image_height,
        detection_count=len(regions),
        mask_pixels=mask_pixels,
        mask_ratio=mask_pixels / float(image_width * image_height),
        method=config.method,
        mask_shape=config.mask_shape,
        padding=config.padding,
        dilation=config.dilation,
        radius=config.radius,
        lama_max_side=config.lama_max_side,
        image=inpainted,
        mask=mask,
        mask_overlay=mask_overlay,
    )


def build_detection_mask(size: tuple[int, int], regions: list[_DetectionRegion], config: InpaintConfig) -> Image.Image:
    width, height = size
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    for region in regions:
        if config.mask_shape == "polygon" and len(region.polygon) >= 3:
            points = [(int(x), int(y)) for x, y in region.polygon]
            draw.polygon(points, fill=255)
            if config.padding > 0:
                padded = region.bbox.padded(config.padding).clipped(width, height)
                draw.rectangle([padded.x, padded.y, padded.right, padded.bottom], fill=255)
        else:
            bbox = region.bbox.padded(config.padding).clipped(width, height)
            draw.rectangle([bbox.x, bbox.y, bbox.right, bbox.bottom], fill=255)
    if config.dilation > 0:
        kernel = config.dilation * 2 + 1
        mask = mask.filter(ImageFilter.MaxFilter(kernel))
    return mask


def apply_inpaint(image: Image.Image, mask: Image.Image, regions: list[_DetectionRegion], config: InpaintConfig) -> Image.Image:
    if config.method == "fill":
        return local_background_fill(image, mask, regions, padding=max(config.padding, 1))
    if config.method == "lama":
        return lama_inpaint(image, mask, max_side=config.lama_max_side)
    try:
        import cv2  # type: ignore
    except Exception as exc:  # pragma: no cover - exercised only when optional cv2 is absent
        raise RuntimeError("OpenCV is required for Telea/Navier-Stokes inpainting. Use --method fill or run in .venv-ocr.") from exc
    source = np.asarray(image.convert("RGB"), dtype=np.uint8)
    mask_array = np.asarray(mask.convert("L"), dtype=np.uint8)
    flag = cv2.INPAINT_TELEA if config.method == "telea" else cv2.INPAINT_NS
    output = cv2.inpaint(source, mask_array, float(config.radius), flag)
    return Image.fromarray(output, mode="RGB")


def lama_inpaint(image: Image.Image, mask: Image.Image, *, max_side: int = 2400) -> Image.Image:
    """Run LaMa inpainting through an optional, bounded-resolution backend.

    Full A4 scans can be 8-20M pixels, which makes interactive LaMa inference look
    frozen on CPU/MPS.  For GUI comparison runs we cap the inference canvas, then
    upscale LaMa's prediction and composite it only into the original masked pixels
    so unmasked document detail remains untouched.
    """
    try:
        from simple_lama_inpainting import SimpleLama  # type: ignore  # noqa: F401
    except Exception as exc:  # pragma: no cover - optional runtime path
        raise RuntimeError(
            "LaMa inpainting requires the optional simple-lama-inpainting runtime. "
            "Install it in .venv-ocr with scripts/install_lama_runtime.sh, "
            "or choose fill/telea/ns."
        ) from exc

    source = image.convert("RGB")
    source_size = source.size
    binary_mask = mask.convert("L").point(lambda value: 255 if value > 0 else 0)
    inference_image, inference_mask, scale = _resize_for_lama(source, binary_mask, max_side=max_side)

    lama = _get_lama_model()
    result = lama(inference_image, inference_mask).convert("RGB")
    if result.size != inference_image.size:
        result = result.crop((0, 0, inference_image.width, inference_image.height))
    if scale != 1.0:
        result = result.resize(source_size, Image.Resampling.BICUBIC)
    # Preserve every unmasked source pixel exactly; compare only the filled area.
    return Image.composite(result, source, binary_mask)


def _resize_for_lama(image: Image.Image, mask: Image.Image, *, max_side: int) -> tuple[Image.Image, Image.Image, float]:
    if max_side <= 0:
        return image, mask, 1.0
    width, height = image.size
    longest = max(width, height)
    if longest <= max_side:
        return image, mask, 1.0
    scale = max_side / float(longest)
    resized_size = (max(8, round(width * scale)), max(8, round(height * scale)))
    return (
        image.resize(resized_size, Image.Resampling.LANCZOS),
        mask.resize(resized_size, Image.Resampling.NEAREST),
        scale,
    )


def _get_lama_model():
    global _LAMA_MODEL
    try:
        return _LAMA_MODEL
    except NameError:
        pass
    from simple_lama_inpainting import SimpleLama  # type: ignore

    _LAMA_MODEL = SimpleLama(device=_select_lama_device())
    return _LAMA_MODEL


def _select_lama_device():
    import torch  # type: ignore

    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return torch.device("mps")
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def local_background_fill(image: Image.Image, mask: Image.Image, regions: list[_DetectionRegion], *, padding: int = 2) -> Image.Image:
    """Simple no-OpenCV fallback: fill each masked bbox with the median color of its surrounding ring."""
    source = np.asarray(image.convert("RGB"), dtype=np.uint8)
    mask_array = np.asarray(mask.convert("L"), dtype=np.uint8)
    output = source.copy()
    height, width = source.shape[:2]
    for region in regions:
        box = region.bbox.padded(padding).clipped(width, height)
        x1, y1, x2, y2 = box.x, box.y, box.right, box.bottom
        ring = _sample_ring(source, mask_array, x1, y1, x2, y2, grow=max(4, padding * 3))
        if ring.size == 0:
            color = np.array([255, 255, 255], dtype=np.uint8)
        else:
            color = np.median(ring.reshape(-1, 3), axis=0).astype(np.uint8)
        region_mask = mask_array[y1:y2, x1:x2] > 0
        output[y1:y2, x1:x2][region_mask] = color
    return Image.fromarray(output, mode="RGB")


def render_mask_overlay(image: Image.Image, mask: Image.Image) -> Image.Image:
    base = image.convert("RGBA")
    red = Image.new("RGBA", base.size, (255, 0, 0, 0))
    alpha = ImageOps.autocontrast(mask.convert("L")).point(lambda v: 110 if v > 0 else 0)
    red.putalpha(alpha)
    return Image.alpha_composite(base, red).convert("RGB")


def render_inpaint_comparison(original: Image.Image, mask: Image.Image, mask_overlay: Image.Image, inpainted: Image.Image) -> Image.Image:
    panels = [
        ("original", original.convert("RGB")),
        ("mask", Image.merge("RGB", [mask, mask, mask])),
        ("mask overlay", mask_overlay.convert("RGB")),
        ("inpainted", inpainted.convert("RGB")),
    ]
    max_w = max(panel.width for _, panel in panels)
    max_h = max(panel.height for _, panel in panels)
    label_h = max(32, round(max_h * 0.018))
    gap = max(8, round(max_w * 0.006))
    canvas = Image.new("RGB", (max_w * 2 + gap, (max_h + label_h) * 2 + gap), (245, 245, 245))
    draw = ImageDraw.Draw(canvas)
    for idx, (label, panel) in enumerate(panels):
        x = (idx % 2) * (max_w + gap)
        y = (idx // 2) * (max_h + label_h + gap)
        canvas.paste(panel, (x, y + label_h))
        draw.rectangle([x, y, x + max_w, y + label_h], fill=(30, 30, 30))
        draw.text((x + 10, y + 8), label, fill=(255, 255, 255))
    return canvas


def _region_from_detection(raw: dict[str, Any]) -> _DetectionRegion:
    return _DetectionRegion(
        bbox=BBox.from_list(raw["bbox"]),
        polygon=[[int(round(point[0])), int(round(point[1]))] for point in raw.get("polygon", [])],
    )


def _sample_ring(source: np.ndarray, mask: np.ndarray, x1: int, y1: int, x2: int, y2: int, *, grow: int) -> np.ndarray:
    height, width = source.shape[:2]
    rx1 = max(0, x1 - grow)
    ry1 = max(0, y1 - grow)
    rx2 = min(width, x2 + grow)
    ry2 = min(height, y2 + grow)
    if rx1 >= rx2 or ry1 >= ry2:
        return np.empty((0, 3), dtype=np.uint8)
    ring_mask = np.ones((ry2 - ry1, rx2 - rx1), dtype=bool)
    inner_x1 = max(0, x1 - rx1)
    inner_y1 = max(0, y1 - ry1)
    inner_x2 = max(inner_x1, min(rx2 - rx1, x2 - rx1))
    inner_y2 = max(inner_y1, min(ry2 - ry1, y2 - ry1))
    ring_mask[inner_y1:inner_y2, inner_x1:inner_x2] = False
    local_mask = mask[ry1:ry2, rx1:rx2] > 0
    valid = ring_mask & ~local_mask
    return source[ry1:ry2, rx1:rx2][valid]
