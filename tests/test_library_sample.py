from __future__ import annotations

import json
import os
from pathlib import Path

from PIL import Image

from datafactory import final_results_export as fre
from datafactory.library_sample import (
    build_cleanroom_artifacts,
    privacy_payload,
    resolve_pii_keys,
    save_cleanroom_annotation,
)


TEST_POLICY = {
    "schema_version": 1,
    "include_exact_keys": ["성명"],
    "include_key_patterns": ["(주소|연락처)$"],
    "include_value_types": ["person.rrn"],
    "include_generators": ["person.email"],
}


def _write_review(path: Path, image_path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source_detections": str(path.parent / "detections.json"),
                "source_image": str(image_path),
                "image": {"width": 1000, "height": 1500},
                "labels": [
                    {
                        "id": "label-1",
                        "text": "홍길동",
                        "confidence": 0.99,
                        "bbox": [100, 300, 200, 80],
                        "polygon": [],
                        "status": "use",
                        "auto_type": "field_value",
                        "reason": "test",
                    },
                    {
                        "id": "label-2",
                        "text": "고정 문구",
                        "confidence": 0.99,
                        "bbox": [100, 100, 200, 50],
                        "polygon": [],
                        "status": "keep",
                        "auto_type": "static_label",
                        "reason": "test",
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_pii_policy_resolves_common_rules_and_document_exceptions() -> None:
    schema = {"성명": "", "배송": {"주소": ""}, "환자번호": "", "담당자": {"이메일": ""}}
    fields = [
        {"semantic_path": ["환자번호"], "value_type": "person.rrn"},
        {"semantic_path": ["담당자", "이메일"], "generator": "person.email"},
    ]

    payload = privacy_payload(
        schema,
        fields=fields,
        privacy={"include_keys": ["환자번호"], "exclude_keys": ["주소"]},
        policy=TEST_POLICY,
    )

    assert payload["defaultKeys"] == ["성명", "주소", "환자번호", "이메일"]
    assert payload["resolvedKeys"] == ["성명", "환자번호", "이메일"]
    assert payload["fieldStates"]["주소"]["mode"] == "exclude"


def test_pii_policy_rejects_unknown_or_conflicting_document_keys() -> None:
    schema = {"성명": "", "주소": ""}

    payload = privacy_payload(
        schema,
        privacy={"include_keys": ["없는키", "성명"], "exclude_keys": ["성명"]},
        policy=TEST_POLICY,
    )

    assert payload["validation"]["ready"] is False
    assert {error["code"] for error in payload["validation"]["errors"]} == {
        "privacy_unknown_key",
        "privacy_conflicting_override",
    }


def test_cleanroom_annotation_round_trip_builds_flat_artifacts(tmp_path: Path) -> None:
    pages_dir = tmp_path / "cleanroom" / "pages"
    pages_dir.mkdir(parents=True)
    image_path = pages_dir / "page_001.png"
    Image.new("RGB", (1000, 1500), "white").save(image_path)
    review_path = tmp_path / "review" / "review.json"
    _write_review(review_path, image_path)
    annotation_path = tmp_path / "document" / "library_sample" / "annotation.json"

    saved = save_cleanroom_annotation(
        annotation_path,
        {
            "sourceImage": str(image_path),
            "reviewPath": str(review_path),
            "fields": [{"key": "성명", "value": "홍길동", "bboxLabelId": "label-1"}],
            "privacy": {"include_keys": [], "exclude_keys": []},
        },
        pages_dir=pages_dir,
        policy=TEST_POLICY,
    )
    artifacts = build_cleanroom_artifacts(annotation_path, policy=TEST_POLICY)

    assert saved["fields"] == [{"key": "성명", "value": "홍길동", "bbox_label_id": "label-1"}]
    assert artifacts["schema"] == {"성명": ""}
    assert artifacts["gt"] == {"성명": "홍길동"}
    assert artifacts["bbox"] == {"성명": {"l": 0.1, "t": 0.2, "r": 0.3, "b": 0.2533}}
    assert artifacts["pii_keys"] == ["성명"]


def test_cleanroom_annotation_rejects_non_cleanroom_source(tmp_path: Path) -> None:
    pages_dir = tmp_path / "cleanroom" / "pages"
    pages_dir.mkdir(parents=True)
    allowed = pages_dir / "page_001.png"
    outside = tmp_path / "original.png"
    Image.new("RGB", (100, 100), "white").save(allowed)
    Image.new("RGB", (100, 100), "white").save(outside)
    review_path = tmp_path / "review.json"
    _write_review(review_path, outside)

    try:
        save_cleanroom_annotation(
            tmp_path / "annotation.json",
            {
                "sourceImage": str(outside),
                "reviewPath": str(review_path),
                "fields": [{"key": "성명", "bboxLabelId": "label-1"}],
            },
            pages_dir=pages_dir,
            policy=TEST_POLICY,
        )
    except ValueError as exc:
        assert "generated cleanroom pages" in str(exc)
    else:
        raise AssertionError("expected original/non-cleanroom source to be rejected")


def test_write_jpg_preserves_resolution_and_reports_recommendations(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    target = tmp_path / "target.jpg"
    Image.new("RGB", (800, 600), "white").save(source)

    report = fre._write_jpg(source, target)

    with Image.open(target) as image:
        assert image.size == (800, 600)
    assert report["sizeBytes"] <= 500 * 1024
    assert {warning["code"] for warning in report["warnings"]} == {"jpg_long_side_below_recommended"}


def test_write_jpg_warns_when_quality_reduction_cannot_meet_500kb(tmp_path: Path) -> None:
    source = tmp_path / "noise.png"
    target = tmp_path / "noise.jpg"
    Image.frombytes("RGB", (1600, 1600), os.urandom(1600 * 1600 * 3)).save(source)

    report = fre._write_jpg(source, target)

    assert report["quality"] == 60
    assert report["sizeBytes"] > 500 * 1024
    assert "jpg_over_recommended_size" in {warning["code"] for warning in report["warnings"]}


def test_resolve_pii_keys_omits_optional_file_when_no_keys_resolve() -> None:
    assert resolve_pii_keys({"금액": ""}, policy=TEST_POLICY) == []
