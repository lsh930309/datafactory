"""Synthetic document image generation toolkit."""

from .models import BBox, FieldSpec, RenderJob, RenderedAnnotation, SyntheticSample, TemplateSpec
from .pipeline import render_job, render_samples

__all__ = [
    "BBox",
    "FieldSpec",
    "RenderJob",
    "RenderedAnnotation",
    "SyntheticSample",
    "TemplateSpec",
    "render_job",
    "render_samples",
]
