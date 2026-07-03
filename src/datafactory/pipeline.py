from __future__ import annotations

import random
from pathlib import Path

from .export import write_sample
from .fake_data import generate_value
from .models import RenderJob, SyntheticSample, TemplateSpec
from .render import render_template


def render_job(job: RenderJob) -> list[SyntheticSample]:
    job.output_dir.mkdir(parents=True, exist_ok=True)
    manifest = job.output_dir / "manifest.jsonl"
    if manifest.exists():
        manifest.unlink()
    return render_samples(
        template=job.template,
        output_dir=job.output_dir,
        count=job.count,
        seed=job.seed,
        image_ext=job.image_ext,
    )


def render_samples(
    *,
    template: TemplateSpec,
    output_dir: Path,
    count: int,
    seed: int = 1234,
    image_ext: str = "png",
) -> list[SyntheticSample]:
    if count <= 0:
        raise ValueError("count must be positive")
    samples: list[SyntheticSample] = []
    for index in range(1, count + 1):
        sample_id = f"sample_{index:06d}"
        rng = random.Random(seed + index)
        values = _values_for_template(template, rng)
        image, annotations = render_template(template, values)
        sample = write_sample(
            output_dir=output_dir,
            sample_id=sample_id,
            template=template,
            image=image,
            fields=values,
            annotations=annotations,
            image_ext=image_ext,
        )
        samples.append(sample)
    return samples


def _values_for_template(template: TemplateSpec, rng: random.Random) -> dict[str, str]:
    values: dict[str, str] = {}
    for field in template.fields:
        values[field.name] = field.value or generate_value(field.type, rng, choices=field.choices, fmt=field.format)
    return values
