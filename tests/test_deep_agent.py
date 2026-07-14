from __future__ import annotations

import io
import json
from pathlib import Path
from urllib.error import HTTPError

from datafactory.deep_agent import (
    DeepAgentCredentials,
    DeepAgentError,
    call_deep_agent_ocr,
    deep_agent_credential_status,
    load_deep_agent_credentials,
    match_deep_ocr_fields,
    normalize_deep_ocr_response,
)
from datafactory import web_api


class _Response:
    def __init__(self, payload: dict, status: int = 200) -> None:
        self.status = status
        self._raw = json.dumps(payload).encode()

    def __enter__(self):  # noqa: ANN204
        return self

    def __exit__(self, *args):  # noqa: ANN002, ANN204
        return None

    def read(self) -> bytes:
        return self._raw


def test_load_credentials_supports_quoted_values_and_reports_permissions(tmp_path: Path) -> None:
    credential_path = tmp_path / "deep_agent_api_key"
    credential_path.write_text('API_KEY="test-key"\nWEBHOOK_SECRET=\'hook-secret\'\n', encoding="utf-8")
    credential_path.chmod(0o600)

    credentials = load_deep_agent_credentials(credential_path)
    status = deep_agent_credential_status(credential_path)

    assert credentials == DeepAgentCredentials(api_key="test-key", webhook_secret="hook-secret")
    assert status["ready"] is True
    assert status["permissionSafe"] is True
    assert status["permissionMode"] == "600"
    assert "test-key" not in json.dumps(status)


def test_call_deep_agent_ocr_uses_x_api_key_and_multipart_without_exposing_key(tmp_path: Path) -> None:
    image = tmp_path / "page.png"
    image.write_bytes(b"png-data")
    captured: dict[str, object] = {}

    def fake_open(request, *, timeout):  # noqa: ANN001
        captured["request"] = request
        captured["timeout"] = timeout
        return _Response({"status": "success", "results": {"elements": []}})

    payload = call_deep_agent_ocr(
        image,
        credentials=DeepAgentCredentials(api_key="secret-api-key"),
        open_request=fake_open,
    )

    request = captured["request"]
    assert payload["status"] == "success"
    assert request.get_header("X-api-key") == "secret-api-key"
    assert "multipart/form-data" in request.get_header("Content-type")
    assert b'name="file"' in request.data
    assert b"png-data" in request.data
    assert captured["timeout"] == 180


def test_call_deep_agent_ocr_maps_api_error_without_secret(tmp_path: Path) -> None:
    image = tmp_path / "page.png"
    image.write_bytes(b"png-data")

    def fake_open(request, *, timeout):  # noqa: ANN001, ARG001
        raw = json.dumps({"error_code": "INSUFFICIENT_CREDIT", "error_message": "credit required for secret-api-key"}).encode()
        raise HTTPError(request.full_url, 400, "bad request", {}, io.BytesIO(raw))

    try:
        call_deep_agent_ocr(
            image,
            credentials=DeepAgentCredentials(api_key="secret-api-key"),
            open_request=fake_open,
        )
    except DeepAgentError as exc:
        assert exc.status == 400
        assert exc.code == "INSUFFICIENT_CREDIT"
        assert "secret-api-key" not in str(exc)
        assert "[REDACTED]" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("expected DeepAgentError")


def test_normalize_response_preserves_null_bbox_and_flat_key_values(tmp_path: Path) -> None:
    image = tmp_path / "page.png"
    image.write_bytes(b"png-data")
    payload = {
        "status": "success",
        "results": {
            "elements": [
                {
                    "page_number": 1,
                    "key_value_list": [
                        {
                            "key": "회사명",
                            "value": ["라온그린에너지 주식회사"],
                            "type": "string",
                            "confidence_score": 0.7,
                            "bbox": None,
                        }
                    ],
                }
            ]
        },
        "metadata": {"total_time": 5.6},
    }

    normalized = normalize_deep_ocr_response(payload, source_image=image, source_sha256="abc")

    assert normalized["sourceSha256"] == "abc"
    assert normalized["fields"] == [
        {
            "index": 0,
            "elementIndex": 0,
            "pageNumber": 1,
            "key": "회사명",
            "value": "라온그린에너지 주식회사",
            "values": ["라온그린에너지 주식회사"],
            "type": "string",
            "confidence": 0.7,
            "bbox": None,
        }
    ]


def test_match_only_auto_selects_unique_normalized_exact_values() -> None:
    normalized = {
        "sourceImage": "page.png",
        "sourceSha256": "abc",
        "fields": [
            {"index": 0, "key": "회사명", "value": "라온그린에너지 주식회사", "bbox": None},
            {"index": 1, "key": "documentTitle", "value": "재무제표에 대한 감사의견서", "bbox": None},
            {"index": 2, "key": "기준일", "value": "2025년 12월 31일", "bbox": None},
            {"index": 3, "key": "중복", "value": "동일 값", "bbox": None},
        ],
    }
    policy = {
        "source_image": "page.png",
        "labels": [
            {"id": "company", "text": "라온그린에너지주식회사", "bbox": [1, 2, 3, 4]},
            {"id": "title-1", "text": "재무제표에 대한", "bbox": [1, 2, 3, 4]},
            {"id": "title-2", "text": "감사의견서", "bbox": [1, 2, 3, 4]},
            {"id": "date-2025", "text": "2025년12월31일", "bbox": [1, 2, 3, 4]},
            {"id": "date-2024", "text": "2024년12월31일", "bbox": [1, 2, 3, 4]},
            {"id": "duplicate-1", "text": "동일값", "bbox": [1, 2, 3, 4]},
            {"id": "duplicate-2", "text": "동일 값", "bbox": [5, 6, 7, 8]},
        ],
    }

    payload = match_deep_ocr_fields(normalized, policy)
    by_key = {match["key"]: match for match in payload["matches"]}

    assert by_key["회사명"]["status"] == "exact"
    assert by_key["회사명"]["bboxLabelId"] == "company"
    assert by_key["documentTitle"]["status"] == "unmatched"
    assert by_key["documentTitle"]["bboxLabelId"] is None
    assert by_key["기준일"]["status"] == "exact"
    assert by_key["기준일"]["bboxLabelId"] == "date-2025"
    assert by_key["중복"]["status"] == "ambiguous"
    assert by_key["중복"]["bboxLabelId"] is None
    assert payload["summary"] == {"fieldCount": 4, "exactCount": 2, "ambiguousCount": 1, "unmatchedCount": 1}


def _review_policy(source_image: Path) -> dict:
    return {
        "schema_version": 1,
        "source_detections": str(source_image.parent / "detections.json"),
        "source_image": str(source_image),
        "image": {"width": 100, "height": 100},
        "labels": [
            {
                "id": "company",
                "text": "라온그린에너지 주식회사",
                "bbox": [1, 2, 30, 10],
                "status": "keep",
                "auto_type": "unknown",
            }
        ],
    }


def test_deep_ocr_cleanroom_job_persists_raw_normalized_matches_and_reuses_sha_cache(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    source_image = tmp_path / "pages" / "page_001.png"
    source_image.parent.mkdir()
    source_image.write_bytes(b"png-data")
    document_root = tmp_path / "workbench" / "documents" / "FIN-11"
    context = {
        "registry": object(),
        "pagesDir": source_image.parent,
        "pages": [source_image],
        "documentRoot": document_root,
    }
    api_calls: list[Path] = []

    monkeypatch.setattr(web_api, "ROOT", tmp_path)
    monkeypatch.setattr(web_api, "_library_sample_cleanroom_context", lambda doc_id: context)
    monkeypatch.setattr(web_api, "update_manifest_artifact", lambda *args, **kwargs: None)

    def fake_call(path: Path) -> dict:
        api_calls.append(path)
        return {
            "status": "success",
            "results": {
                "elements": [
                    {
                        "page_number": 1,
                        "key_value_list": [
                            {
                                "key": "회사명",
                                "value": ["라온그린에너지 주식회사"],
                                "confidence_score": 0.91,
                                "bbox": None,
                            }
                        ],
                    }
                ]
            },
            "metadata": {"total_time": 1.2},
        }

    monkeypatch.setattr(web_api, "call_deep_agent_ocr", fake_call)
    request = {"docId": "FIN-11", "sourceImage": str(source_image), "policy": _review_policy(source_image)}

    first = web_api.deep_ocr_start_payload(request, async_run=False)
    second = web_api.deep_ocr_start_payload(request, async_run=False)

    assert first["status"] == "completed"
    assert first["result"]["summary"]["cacheHit"] is False
    assert first["result"]["matches"][0]["bboxLabelId"] == "company"
    assert second["status"] == "completed"
    assert second["result"]["summary"]["cacheHit"] is True
    assert len(api_calls) == 1
    for name in ("raw", "normalized", "matches"):
        assert (tmp_path / first["result"]["paths"][name]).exists()
    assert (tmp_path / second["result"]["paths"]["matches"]).exists()


def test_deep_ocr_cleanroom_job_rejects_non_cleanroom_source(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    page = tmp_path / "pages" / "page.png"
    page.parent.mkdir()
    page.write_bytes(b"page")
    outside = tmp_path / "outside.png"
    outside.write_bytes(b"outside")
    context = {"registry": object(), "pagesDir": page.parent, "pages": [page], "documentRoot": tmp_path / "document"}
    monkeypatch.setattr(web_api, "ROOT", tmp_path)
    monkeypatch.setattr(web_api, "_library_sample_cleanroom_context", lambda doc_id: context)

    try:
        web_api.deep_ocr_start_payload(
            {"docId": "FIN-11", "sourceImage": str(outside), "policy": _review_policy(outside)},
            async_run=False,
        )
    except ValueError as exc:
        assert "cleanroom pages" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("expected source validation error")
