from __future__ import annotations

import pytest

from datafactory.ocr_detectors import PaddleOcrDetector, get_detector, normalize_paddleocr_preset, paddleocr_preset_params


def test_paddleocr_preset_params_keep_precise_as_current_default() -> None:
    assert normalize_paddleocr_preset(None) == "precise"
    assert paddleocr_preset_params(None) == {
        "text_det_limit_side_len": 1920,
        "text_det_limit_type": "max",
        "text_det_thresh": 0.25,
        "text_det_box_thresh": 0.5,
    }
    assert paddleocr_preset_params("balanced") == {
        "text_det_limit_side_len": 1280,
        "text_det_limit_type": "max",
    }


def test_paddleocr_precise_preset_lowers_thresholds_and_raises_resolution() -> None:
    params = paddleocr_preset_params("precise")
    assert params["text_det_limit_side_len"] == 1920
    assert params["text_det_limit_type"] == "max"
    assert params["text_det_thresh"] == 0.25
    assert params["text_det_box_thresh"] == 0.5


def test_paddleocr_unknown_preset_fails_fast() -> None:
    with pytest.raises(ValueError, match="unknown PaddleOCR preset"):
        normalize_paddleocr_preset("ultra")


def test_get_detector_passes_preset_to_paddle_detector_only() -> None:
    detector = get_detector("paddleocr", preset="fast")
    assert isinstance(detector, PaddleOcrDetector)
    assert detector.preset == "fast"
    assert detector.params["text_det_limit_side_len"] == 960

    projection = get_detector("projection", preset="precise")
    assert projection.engine == "projection"
