from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from datafactory import web_api


def test_paddle_ocr_worker_runs_in_subprocess_and_reads_metadata(tmp_path: Path, monkeypatch) -> None:
    image = tmp_path / "sample.jpg"
    image.write_bytes(b"not a real image for this subprocess-contract test")

    captured: dict[str, object] = {}

    def fake_run(cmd, *, cwd, env, text, capture_output, check):  # noqa: ANN001
        captured["cmd"] = cmd
        captured["cwd"] = cwd
        captured["env"] = env
        result_path = Path(cmd[cmd.index("--result-json") + 1])
        result_path.write_text(
            json.dumps(
                {
                    "summary": {
                        "engine": "paddleocr",
                        "preset": "precise",
                        "source_image": str(image),
                        "image": {"width": 100, "height": 50},
                        "detection_count": 3,
                        "elapsed_seconds": 1.2,
                    },
                    "paths": {
                        "detections": str(tmp_path / "detections.json"),
                        "raw": str(tmp_path / "raw.json"),
                        "overlay": str(tmp_path / "overlay.png"),
                        "summary": str(tmp_path / "summary.json"),
                    },
                }
            ),
            encoding="utf-8",
        )
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(web_api.subprocess, "run", fake_run)

    payload = web_api._run_paddle_ocr_subprocess(image, preset="precise", out_dir=tmp_path / "ocr")

    assert payload["summary"]["preset"] == "precise"
    assert payload["summary"]["detection_count"] == 3
    assert captured["cmd"][:3] == [web_api.sys.executable, "-m", "datafactory.ocr_worker"]
    assert "--preset" in captured["cmd"]
    assert captured["cmd"][captured["cmd"].index("--preset") + 1] == "precise"
    assert str(web_api.ROOT / "src") in captured["env"]["PYTHONPATH"]


def test_paddle_ocr_worker_failure_reports_tail(tmp_path: Path, monkeypatch) -> None:
    image = tmp_path / "sample.jpg"
    image.write_bytes(b"x")

    def fake_run(*args, **kwargs):  # noqa: ANN002, ANN003
        return SimpleNamespace(returncode=7, stdout="", stderr="native failure")

    monkeypatch.setattr(web_api.subprocess, "run", fake_run)

    try:
        web_api._run_paddle_ocr_subprocess(image, preset="precise", out_dir=tmp_path / "ocr")
    except RuntimeError as exc:
        assert "exit code 7" in str(exc)
        assert "native failure" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("expected RuntimeError")


def test_paddle_crop_worker_runs_in_subprocess_and_reads_candidates(tmp_path: Path, monkeypatch) -> None:
    manifest = tmp_path / "crop_manifest.json"
    manifest.write_text(json.dumps({"crops": []}), encoding="utf-8")
    captured: dict[str, object] = {}

    def fake_run(cmd, *, cwd, env, text, capture_output, check):  # noqa: ANN001
        captured["cmd"] = cmd
        captured["cwd"] = cwd
        captured["env"] = env
        result_path = Path(cmd[cmd.index("--result-json") + 1])
        result_path.write_text(
            json.dumps(
                {
                    "summary": {"engine": "paddleocr", "preset": "precise", "count": 1, "recognized": 1, "elapsed_seconds": 0.5},
                    "candidates": [
                        {
                            "id": "det_1",
                            "oldText": "기존",
                            "text": "재인식",
                            "confidence": 0.98,
                            "cropPath": str(tmp_path / "crop.png"),
                            "detections": [],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(web_api.subprocess, "run", fake_run)

    payload = web_api._run_paddle_crop_recognition_subprocess(manifest, preset="precise", out_dir=tmp_path / "ocr")

    assert payload["summary"]["count"] == 1
    assert payload["candidates"][0]["text"] == "재인식"
    assert "--crops-json" in captured["cmd"]
    assert captured["cmd"][captured["cmd"].index("--crops-json") + 1] == str(manifest)
    assert str(web_api.ROOT / "src") in captured["env"]["PYTHONPATH"]


def test_recognize_review_crops_payload_creates_manifest_and_display_paths(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(web_api, "ROOT", tmp_path)
    image_path = tmp_path / "source.png"
    Image.new("RGB", (100, 60), (255, 255, 255)).save(image_path)
    detections_path = tmp_path / "detections.json"
    detections_path.write_text("{}", encoding="utf-8")
    captured: dict[str, object] = {}

    def fake_worker(crops_json: Path, *, preset: str, out_dir: Path):  # noqa: ANN001
        captured["preset"] = preset
        captured["out_dir"] = out_dir
        manifest = json.loads(crops_json.read_text(encoding="utf-8"))
        captured["manifest"] = manifest
        crop_path = Path(manifest["crops"][0]["cropPath"])
        assert crop_path.exists()
        return {
            "summary": {"engine": "paddleocr", "preset": preset, "count": 1, "recognized": 1, "elapsed_seconds": 0.1},
            "candidates": [{"id": "det_1", "oldText": "기존", "text": "신규", "confidence": 0.99, "cropPath": str(crop_path), "detections": []}],
        }

    monkeypatch.setattr(web_api, "_run_paddle_crop_recognition_subprocess", fake_worker)
    payload = web_api.recognize_review_crops_payload(
        {
            "preset": "precise",
            "padding": 2,
            "policy": {
                "schema_version": 1,
                "source_detections": str(detections_path),
                "source_image": str(image_path),
                "image": {"width": 100, "height": 60},
                "labels": [
                    {
                        "id": "det_1",
                        "text": "기존",
                        "confidence": 0.9,
                        "bbox": [10, 10, 20, 12],
                        "polygon": [[10, 10], [30, 10], [30, 22], [10, 22]],
                        "status": "use",
                        "auto_type": "field_value",
                        "reason": "test",
                        "ocr_text_stale": True,
                    }
                ],
            },
        }
    )

    assert captured["preset"] == "precise"
    assert captured["manifest"]["crops"][0]["bbox"] == [8, 8, 24, 16]
    assert payload["candidates"][0]["cropPath"].startswith("outputs/ocr_recrop/")
    assert payload["summary"]["manifest"].startswith("outputs/ocr_recrop/")


def test_authoring_agent_request_includes_research_and_draft_contract(tmp_path: Path, monkeypatch) -> None:
    class FakeDoc:
        doc_id = "APP-14"
        title = "카드발급신청서"

        def to_dict(self) -> dict[str, object]:
            return {"docId": self.doc_id, "title": self.title, "poDomains": ["금융"], "workflowDomains": ["금융 - 카드"]}

    fake_doc = FakeDoc()
    fake_registry = SimpleNamespace(documents={fake_doc.doc_id: fake_doc})

    def fake_workbench_subdir(doc_id: str, subdir: str):
        target = tmp_path / "workbench" / doc_id / subdir
        target.mkdir(parents=True, exist_ok=True)
        return target

    manifest_updates: list[tuple[str, str, str]] = []

    monkeypatch.setattr(web_api, "ROOT", tmp_path)
    monkeypatch.setattr(web_api, "load_registry", lambda: fake_registry)
    monkeypatch.setattr(
        web_api,
        "list_work_items",
        lambda registry: [
            {
                "docId": fake_doc.doc_id,
                "samples": ["samples/card.png"],
                "latestReview": "review.json",
                "latestInpainted": "inpainted.png",
            }
        ],
    )
    monkeypatch.setattr(web_api, "workbench_subdir", fake_workbench_subdir)
    monkeypatch.setattr(web_api, "update_manifest_artifact", lambda doc_id, key, path: manifest_updates.append((doc_id, key, str(path))))

    payload = web_api.authoring_agent_request_payload({"docId": fake_doc.doc_id, "instruction": "체크박스 의미를 보수적으로 판단"})

    request_path = tmp_path / payload["paths"]["request"]
    prompt_path = tmp_path / payload["paths"]["prompt"]
    request = json.loads(request_path.read_text(encoding="utf-8"))
    prompt = prompt_path.read_text(encoding="utf-8")

    assert request["schema_version"] == 2
    assert "research_report.json" in request["contract"]["outputs"]
    assert "faker_profile_draft.json" in request["contract"]["outputs"]
    assert any("웹 검색" in rule for rule in request["contract"]["web_research_rules"])
    assert any("템플릿에 없는 필드" in rule for rule in request["contract"]["web_research_rules"])
    assert any("literal:" in rule and "임의 생성" in rule for rule in request["contract"]["faker_profile_rules"])
    assert "웹 리서치 필수 규칙" in prompt
    assert "체크박스 의미를 보수적으로 판단" in prompt
    assert ("APP-14", "authoring_agent_request", str(request_path)) in manifest_updates
    assert ("APP-14", "authoring_agent_prompt", str(prompt_path)) in manifest_updates
