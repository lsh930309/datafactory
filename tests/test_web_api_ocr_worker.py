from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from PIL import Image
import pytest

from datafactory import web_api


def test_authoring_agent_capabilities_follow_local_model_cache(tmp_path: Path) -> None:
    (tmp_path / "models_cache.json").write_text(
        json.dumps(
            {
                "fetched_at": "2026-07-14T00:43:57Z",
                "models": [
                    {
                        "slug": "gpt-5.6-sol",
                        "display_name": "GPT-5.6-Sol",
                        "description": "frontier",
                        "visibility": "list",
                        "default_reasoning_level": "low",
                        "supported_reasoning_levels": [{"effort": value} for value in ("low", "medium", "high", "xhigh", "max", "ultra")],
                        "additional_speed_tiers": ["fast"],
                    },
                    {
                        "slug": "gpt-5.6-luna",
                        "display_name": "GPT-5.6-Luna",
                        "description": "fast",
                        "visibility": "list",
                        "default_reasoning_level": "medium",
                        "supported_reasoning_levels": [{"effort": value} for value in ("low", "medium", "high", "xhigh", "max")],
                        "additional_speed_tiers": ["fast"],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "config.toml").write_text('model = "gpt-5.6-sol"\n', encoding="utf-8")

    payload = web_api.authoring_agent_capabilities(codex_home=tmp_path)

    assert payload["defaultModel"] == "gpt-5.6-terra"
    assert payload["source"] == "models_cache"
    luna = next(model for model in payload["models"] if model["id"] == "gpt-5.6-luna")
    assert luna["reasoningEfforts"] == ["low", "medium", "high", "xhigh", "max"]
    assert luna["supportsFastMode"] is True


def test_authoring_agent_options_support_new_reasoning_and_optional_budget(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(
        web_api,
        "authoring_agent_capabilities",
        lambda: {
            "defaultModel": "gpt-5.6-terra",
            "models": [
                {
                    "id": "gpt-5.6-terra",
                    "reasoningEfforts": ["low", "medium", "high", "xhigh", "max", "ultra"],
                    "supportsFastMode": True,
                },
                {"id": "gpt-5.6-luna", "reasoningEfforts": ["low", "medium", "high", "xhigh", "max"], "supportsFastMode": True},
            ],
        },
    )

    options = web_api._authoring_agent_options(
        {"options": {"model": "gpt-5.6-terra", "reasoningEffort": "ultra", "executionMode": "single_pass", "timeBudgetMinutes": 15}}
    )

    assert options["model"] == "gpt-5.6-terra"
    assert options["reasoningEffort"] == "ultra"
    assert options["executionMode"] == "single_pass"
    assert options["timeBudgetMinutes"] == 15
    with pytest.raises(ValueError, match="not supported"):
        web_api._authoring_agent_options({"options": {"model": "gpt-5.6-luna", "reasoningEffort": "ultra"}})


def test_authoring_agent_execution_modes_have_bounded_stage_sequences() -> None:
    assert web_api._authoring_agent_execution_stages("two_pass") == ["schema", "faker"]
    assert web_api._authoring_agent_execution_stages("single_pass") == ["full"]
    assert web_api._authoring_agent_execution_stages("schema_only") == ["schema"]
    assert web_api._authoring_agent_execution_stages("faker_only") == ["faker"]
    assert web_api._authoring_agent_execution_stages("validation_repair") == ["validation_repair"]


def test_agent_job_payload_streams_terminal_by_cursor(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(web_api, "ROOT", tmp_path)
    run_dir = tmp_path / "workbench" / "documents" / "doc" / "authoring" / "agent_runs" / "run1"
    run_dir.mkdir(parents=True)
    terminal = run_dir / "terminal.log"
    terminal.write_text("first\nsecond\n", encoding="utf-8")
    job_path = run_dir / "job.json"
    web_api._write_agent_job(job_path, {"status": "running", "terminalPath": web_api._display_path(terminal, tmp_path)})

    first = web_api._agent_job_payload(job_path, terminal_offset=0)
    second = web_api._agent_job_payload(job_path, terminal_offset=len("first\n".encode()))

    assert first["terminal"]["text"] == "first\nsecond\n"
    assert second["terminal"]["text"] == "second\n"


def test_run_codex_process_streams_stdout_and_stderr_to_terminal(tmp_path: Path) -> None:
    job_path = tmp_path / "job.json"
    stdout_path = tmp_path / "stdout.log"
    stderr_path = tmp_path / "stderr.log"
    terminal_path = tmp_path / "terminal.log"
    web_api._write_agent_job(job_path, {"status": "running"})

    result = web_api._run_codex_process(
        [
            web_api.sys.executable,
            "-u",
            "-c",
            "import sys; data=sys.stdin.read(); print('stdout:'+data); print('stderr:mirror', file=sys.stderr)",
        ],
        "prompt-body",
        cwd=tmp_path,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        terminal_path=terminal_path,
        job_path=job_path,
        deadline=None,
    )

    assert result.returncode == 0
    assert "stdout:prompt-body" in stdout_path.read_text(encoding="utf-8")
    assert "stderr:mirror" in stderr_path.read_text(encoding="utf-8")
    terminal_text = terminal_path.read_text(encoding="utf-8")
    assert "stdout:prompt-body" in terminal_text
    assert "stderr:mirror" in terminal_text


def test_cancel_authoring_agent_run_marks_request_and_terminates_process(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(web_api, "ROOT", tmp_path)
    run_dir = tmp_path / "workbench" / "documents" / "doc" / "authoring" / "agent_runs" / "run1"
    run_dir.mkdir(parents=True)
    job_path = run_dir / "job.json"
    web_api._write_agent_job(job_path, {"status": "running", "pid": 321})
    terminated: list[tuple[object, bool]] = []
    monkeypatch.setattr(web_api, "_terminate_process_group", lambda pid, *, force: terminated.append((pid, force)))

    payload = web_api.cancel_authoring_agent_run_payload({"jobPath": str(job_path)})

    assert payload["status"] == "cancelling"
    assert payload["cancelRequestedAt"]
    assert terminated == [(321, False)]


def test_visual_line_detection_flag_is_explicit_opt_in() -> None:
    assert not web_api._visual_line_detection_requested({})
    assert not web_api._visual_line_detection_requested({"includeVisualLineDetection": False})
    assert not web_api._visual_line_detection_requested({"includeVisualLineDetection": "false"})
    assert web_api._visual_line_detection_requested({"includeVisualLineDetection": True})
    assert web_api._visual_line_detection_requested({"includeVisualLineDetection": "true"})
    assert web_api._visual_line_detection_requested({"includeVisualLineDetection": "1"})


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



def test_ocr_detection_start_payload_writes_pollable_job(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(web_api, "ROOT", tmp_path)
    monkeypatch.setattr(web_api, "update_manifest_artifact", lambda *args, **kwargs: None)
    monkeypatch.setattr(web_api, "workbench_subdir", lambda doc_id, name: tmp_path / "workbench" / doc_id / name)
    image = tmp_path / "source.png"
    Image.new("RGB", (120, 80), (255, 255, 255)).save(image)

    def fake_worker(image_path: Path, *, preset: str, out_dir: Path):  # noqa: ANN001
        return {
            "summary": {
                "engine": "paddleocr",
                "preset": preset,
                "source_image": str(image_path),
                "image": {"width": 120, "height": 80},
                "detection_count": 2,
                "elapsed_seconds": 0.1,
            },
            "paths": {
                "detections": str(out_dir / "detections.json"),
                "raw": str(out_dir / "raw.json"),
                "overlay": str(out_dir / "overlay.png"),
                "summary": str(out_dir / "summary.json"),
            },
        }

    monkeypatch.setattr(web_api, "_run_paddle_ocr_subprocess", fake_worker)

    job = web_api.ocr_detection_start_payload({"docId": "DOC-1", "imagePath": str(image), "engine": "paddleocr", "preset": "fast"}, async_run=False)

    assert job["status"] == "completed"
    assert job["result"]["summary"]["detection_count"] == 2
    assert job["result"]["paths"]["detections"].endswith("detections.json")
    status = web_api.ocr_detection_status_payload({"jobPath": job["jobPath"]})
    assert status["jobId"] == job["jobId"]
    assert status["status"] == "completed"


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




def test_faker_profile_contract_validates_relational_constraints() -> None:
    fields = [
        {"field_id": "a"},
        {"field_id": "b"},
        {"field_id": "total"},
        {"field_id": "start_y"},
        {"field_id": "start_m"},
        {"field_id": "start_d"},
        {"field_id": "end_y"},
        {"field_id": "end_m"},
        {"field_id": "end_d"},
    ]
    valid_profile = {
        "field_generators": {field["field_id"]: "free_text.short" for field in fields},
        "constraints": [
            {"type": "sum", "sources": ["a", "b"], "target": "total"},
            {"type": "date_order", "start": {"year": "start_y", "month": "start_m", "day": "start_d"}, "end": {"year": "end_y", "month": "end_m", "day": "end_d"}},
            {"type": "exclusive_choice", "targets": ["a", "b"]},
        ],
    }

    assert web_api._validate_faker_profile_contract(valid_profile, fields) == []

    invalid_profile = {
        "field_generators": {field["field_id"]: "free_text.short" for field in fields},
        "constraints": [
            {"type": "formula", "expression": "total=a+b"},
            {"type": "sum", "sources": ["a", "missing"], "target": "total"},
        ],
    }

    errors = web_api._validate_faker_profile_contract(invalid_profile, fields)
    assert any(error["code"] == "faker_constraint_unsupported_type" for error in errors)
    assert any(error["code"] == "faker_constraint_unknown_field" and error["field"] == "missing" for error in errors)


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


def test_authoring_visual_evidence_manifest_crops_use_value_regions(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(web_api, "ROOT", tmp_path)
    source = tmp_path / "source.png"
    Image.new("RGB", (100, 60), (255, 255, 255)).save(source)
    inpainted = tmp_path / "inpainted.png"
    Image.new("RGB", (100, 60), (240, 240, 240)).save(inpainted)
    detections = tmp_path / "detections.json"
    detections.write_text("{}", encoding="utf-8")
    review = tmp_path / "review.json"
    review.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source_detections": str(detections),
                "source_image": str(source),
                "image": {"width": 100, "height": 60},
                "labels": [
                    {
                        "id": "value_1",
                        "text": "면적",
                        "confidence": 0.9,
                        "bbox": [10, 10, 20, 12],
                        "polygon": [[10, 10], [30, 10], [30, 22], [10, 22]],
                        "status": "use",
                        "auto_type": "field_value",
                        "reason": "test",
                    },
                    {
                        "id": "label_1",
                        "text": "㎡",
                        "confidence": 0.9,
                        "bbox": [40, 10, 10, 12],
                        "polygon": [[40, 10], [50, 10], [50, 22], [40, 22]],
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

    manifest_path = web_api._write_authoring_visual_evidence_manifest(
        doc_id="DOC-1",
        review_path=review,
        request_dir=tmp_path / "request",
        visual_source_path=inpainted,
        padding=2,
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["visual_source"] == "inpainted.png"
    assert manifest["crops"][0]["anchor_id"] == "value_1"
    assert manifest["crops"][0]["padded_bbox"] == [8, 8, 24, 16]
    assert Path(tmp_path / manifest["crops"][0]["crop_path"]).exists()
    assert len(manifest["crops"]) == 1
    assert "source_of_truth_policy" in manifest


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
    assert any("field_generators" in rule and "반드시 포함" in rule for rule in request["contract"]["faker_profile_rules"])
    assert any("date_between:" in rule and "쓰지 않는다" in rule for rule in request["contract"]["faker_profile_rules"])
    assert any("field_id -> data_pools" in rule for rule in request["contract"]["constraint_rules"])
    assert any("constraint 내부 `records`" in rule for rule in request["contract"]["constraint_rules"])
    assert any("전체 템플릿 이미지가 최상위 source of truth" in rule for rule in request["contract"]["visual_source_of_truth_rules"])
    assert "웹 리서치 필수 규칙" in prompt
    assert "시각 근거 우선 규칙" in prompt
    assert "지원 Faker relationship constraint 문법" in prompt
    assert "pick_record" in prompt
    assert "constraint 내부 `records`" in prompt
    assert "지원 Faker rule 문법" in prompt
    assert "field_generators" in prompt
    assert "date_between:-365d:+0d" in prompt
    assert "체크박스 의미를 보수적으로 판단" in prompt
    assert ("APP-14", "authoring_agent_request", str(request_path)) in manifest_updates
    assert ("APP-14", "authoring_agent_prompt", str(prompt_path)) in manifest_updates


def test_authoring_agent_run_invokes_codex_and_validates_draft_outputs(tmp_path: Path, monkeypatch) -> None:
    class FakeDoc:
        doc_id = "APP-14"
        title = "카드발급신청서"

        def to_dict(self) -> dict[str, object]:
            return {"docId": self.doc_id, "title": self.title, "poDomains": ["금융"], "workflowDomains": ["금융 - 카드"]}

    fake_doc = FakeDoc()
    fake_registry = SimpleNamespace(documents={fake_doc.doc_id: fake_doc})
    manifest_updates: list[tuple[str, str, str]] = []
    captured: dict[str, object] = {}
    calls: list[str] = []

    def fake_workbench_subdir(doc_id: str, subdir: str):
        target = tmp_path / "workbench" / doc_id / subdir
        target.mkdir(parents=True, exist_ok=True)
        return target

    def fake_run(cmd, prompt, **kwargs):  # noqa: ANN001
        calls.append(str(prompt))
        captured["cmd"] = cmd
        captured["input"] = prompt
        request_dirs = sorted((tmp_path / "workbench" / fake_doc.doc_id / "authoring" / "agent_requests").glob("*"))
        request_dir = request_dirs[-1]
        for name in web_api.AUTHORING_AGENT_REQUIRED_OUTPUTS:
            path = request_dir / name
            if name.endswith(".json"):
                payload = {"schema_version": 1, "name": name}
                if name == "schema_draft.json":
                    if len(calls) == 2:
                        payload.update({"semantic_schema": {"변조된 필드": ""}, "fields": [{"field_id": "mutated", "key": "변조된 필드", "semantic_path": ["변조된 필드"], "anchor_id": "det_name", "value": ""}]})
                    else:
                        payload.update({"semantic_schema": {"환자 성명": ""}, "fields": [{"field_id": "patient_name", "key": "환자 성명", "semantic_path": ["환자 성명"], "anchor_id": "det_name", "value": ""}]})
                elif name == "faker_profile_draft.json":
                    payload.update({"field_generators": {"patient_name": "person.name_ko"}})
                elif name == "anchor_map_draft.json":
                    payload.update({"anchors": [{"anchor_id": "det_name", "status": "use", "role": "value_region"}]})
                elif name == "research_report.json":
                    payload.update({"sources": []})
                path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            else:
                path.write_text("생성 완료\n", encoding="utf-8")
        kwargs["stdout_path"].write_text("ok", encoding="utf-8")
        kwargs["stderr_path"].write_text("tokens used\n123\n", encoding="utf-8")
        Path(cmd[cmd.index("--output-last-message") + 1]).write_text("ok", encoding="utf-8")
        return web_api._AgentProcessResult(returncode=0, stdout_tail="ok", stderr_tail="", pid=123)

    monkeypatch.setattr(web_api, "ROOT", tmp_path)
    monkeypatch.setattr(web_api, "load_registry", lambda: fake_registry)
    monkeypatch.setattr(web_api, "workbench_subdir", fake_workbench_subdir)
    monkeypatch.setattr(web_api, "list_work_items", lambda registry: [{"docId": fake_doc.doc_id, "samples": [], "latestReview": "", "latestInpainted": ""}])
    monkeypatch.setattr(web_api, "update_manifest_artifact", lambda doc_id, key, path: manifest_updates.append((doc_id, key, str(path))))
    monkeypatch.setattr(web_api, "_run_codex_process", fake_run)

    payload = web_api.authoring_agent_run_payload({"docId": fake_doc.doc_id, "instruction": "원클릭 추론"}, async_run=False)

    assert payload["status"] == "succeeded"
    assert payload["validation"]["ready"] is True
    assert payload["validation"]["summary"]["present"] == len(web_api.AUTHORING_AGENT_REQUIRED_OUTPUTS)
    assert captured["cmd"][:4] == ["codex", "--search", "--ask-for-approval", "never"]
    assert captured["cmd"][captured["cmd"].index("--model") + 1] == "gpt-5.6-terra"
    assert "-c" in captured["cmd"]
    assert 'model_reasoning_effort="medium"' in captured["cmd"]
    assert "--disable" in captured["cmd"]
    assert captured["cmd"][captured["cmd"].index("--disable") + 1] == "fast_mode"
    assert "exec" in captured["cmd"]
    assert "--output-last-message" in captured["cmd"]
    assert "Supported relationships" in str(captured["input"])
    assert "pick_record" in str(captured["input"])
    assert "constraint 내부 `records`" in str(captured["input"])
    assert len(calls) == 2
    assert "schema pass" in calls[0]
    assert "faker pass" in calls[1]
    assert "Do not browse the web" in calls[1]
    assert payload["stages"][1]["frozenArtifactViolations"] == ["schema_draft.json"]
    restored_request_dir = sorted((tmp_path / "workbench" / fake_doc.doc_id / "authoring" / "agent_requests").glob("*"))[-1]
    restored_schema = json.loads((restored_request_dir / "schema_draft.json").read_text(encoding="utf-8"))
    assert restored_schema["semantic_schema"] == {"환자 성명": ""}
    assert any(key == "authoring_agent_schema_draft" for _doc_id, key, _path in manifest_updates)
    status = web_api.authoring_agent_run_status_payload({"jobPath": payload["jobPath"]})
    assert status["status"] == "succeeded"


def test_apply_authoring_agent_drafts_writes_final_authoring_bundle(tmp_path: Path, monkeypatch) -> None:
    class FakeDoc:
        doc_id = "APP-14"
        title = "카드발급신청서"

        def to_dict(self) -> dict[str, object]:
            return {"docId": self.doc_id, "title": self.title}

    fake_doc = FakeDoc()
    fake_registry = SimpleNamespace(documents={fake_doc.doc_id: fake_doc})
    manifest_updates: list[tuple[str, str, str]] = []
    request_dir = tmp_path / "workbench" / fake_doc.doc_id / "authoring" / "agent_requests" / "run1"
    request_dir.mkdir(parents=True)
    request_path = request_dir / "request.json"
    request_path.write_text(json.dumps({"docId": fake_doc.doc_id, "title": fake_doc.title}), encoding="utf-8")
    (request_dir / "schema_draft.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "doc_id": fake_doc.doc_id,
                "title": fake_doc.title,
                "semantic_schema": {"환자 성명": ""},
                "fields": [{"field_id": "patient_name", "label": "환자 성명", "key": "환자 성명", "anchor_id": "det_name", "value": "", "value_type": "person.name_ko"}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (request_dir / "stylesheet_draft.json").write_text(json.dumps({"schema_version": 1, "style_classes": [{"style_class": "body_default", "font_size": 18}]}), encoding="utf-8")
    (request_dir / "faker_profile_draft.json").write_text(json.dumps({"schema_version": 1, "field_generators": {"patient_name": "person.name_ko"}, "constraints": []}), encoding="utf-8")
    (request_dir / "anchor_map_draft.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source_review": "review.json",
                "source_image": "source.png",
                "image": {"width": 100, "height": 60},
                "anchors": [{"anchor_id": "det_name", "text": "홍길동", "bbox": [10, 12, 30, 14], "status": "use", "auto_type": "field_value"}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    def fake_workbench_subdir(doc_id: str, subdir: str):
        target = tmp_path / "workbench" / doc_id / subdir
        target.mkdir(parents=True, exist_ok=True)
        return target

    monkeypatch.setattr(web_api, "ROOT", tmp_path)
    monkeypatch.setattr(web_api, "load_registry", lambda: fake_registry)
    monkeypatch.setattr(web_api, "workbench_subdir", fake_workbench_subdir)
    monkeypatch.setattr(web_api, "list_work_items", lambda registry: [{"docId": fake_doc.doc_id, "latestReview": "review.json", "latestInpainted": "inpainted.png", "samples": []}])
    monkeypatch.setattr(web_api, "update_manifest_artifact", lambda doc_id, key, path: manifest_updates.append((doc_id, key, str(path))))

    authoring_dir = tmp_path / "workbench" / fake_doc.doc_id / "authoring"
    (authoring_dir / "schema.json").write_text(
        json.dumps(
            {
                "fields": [
                    {
                        "field_id": "previous_patient_name",
                        "bbox_label_id": "det_name",
                        "style_class": "previous_name_style",
                        "render_mode": "handwriting",
                        "render_policy": {"align": "right", "valign": "bottom"},
                    }
                ],
                "handwriting": {"qr_bbox": [70, 5, 20, 20], "default_sample_count": 1},
            }
        ),
        encoding="utf-8",
    )
    (authoring_dir / "stylesheet.json").write_text(
        json.dumps({"style_classes": [{"style_class": "previous_name_style", "font_size": 13, "align": "right"}]}),
        encoding="utf-8",
    )

    payload = web_api.apply_authoring_agent_drafts_payload({"docId": fake_doc.doc_id, "requestPath": str(request_path)})

    assert payload["summary"]["field_count"] == 1
    assert Path(tmp_path / payload["paths"]["schema"]).exists()
    assert Path(tmp_path / payload["paths"]["stylesheet"]).exists()
    assert Path(tmp_path / payload["paths"]["faker_profile"]).exists()
    saved_schema = json.loads((tmp_path / payload["paths"]["schema"]).read_text(encoding="utf-8"))
    assert saved_schema["fields"][0]["bbox_label_id"] == "det_name"
    assert saved_schema["fields"][0]["label"] == "환자 성명"
    assert saved_schema["fields"][0]["style_class"] == "previous_name_style"
    assert saved_schema["fields"][0]["render_mode"] == "handwriting"
    assert saved_schema["fields"][0]["render_policy"]["align"] == "right"
    assert saved_schema["handwriting"] == {"qr_bbox": [70, 5, 20, 20], "default_sample_count": 1}
    assert json.loads((authoring_dir / "semantic_schema.json").read_text(encoding="utf-8")) == {"환자 성명": ""}
    saved_stylesheet = json.loads((tmp_path / payload["paths"]["stylesheet"]).read_text(encoding="utf-8"))
    assert saved_stylesheet["style_classes"][0]["font_size"] == 13
    assert payload["styleRemap"]["methods"]["anchor"] == 1
    assert saved_schema["source_review"].endswith("/authoring/agent_applied_reviews/run1/review.json")
    assert payload["schema"]["fields"][0]["bbox"] == [10, 12, 30, 14]
    assert any(key == "authoring_agent_applied_request" for _doc_id, key, _path in manifest_updates)
    assert any(key == "authoring_anchor_map" for _doc_id, key, _path in manifest_updates)
    assert any(key == "authoring_agent_applied_review" for _doc_id, key, _path in manifest_updates)


def test_authoring_agent_apply_regression_rejects_source_page_change(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(web_api, "ROOT", tmp_path)
    previous = {
        "source_image": str(tmp_path / "page_001.png"),
        "fields": [{"field_id": "name", "bbox_label_id": "det_name"}],
    }
    candidate = {
        "source_image": str(tmp_path / "page_002.png"),
        "fields": [{"field_id": "name", "bbox_label_id": "det_name"}],
    }

    result = web_api._validate_authoring_agent_apply_regression(previous, candidate)

    assert result["ready"] is False
    assert result["errors"][0]["code"] == "authoring_agent_source_image_changed"


def test_authoring_agent_apply_regression_rejects_large_field_drop(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(web_api, "ROOT", tmp_path)
    source = str(tmp_path / "page_001.png")
    previous = {
        "source_image": source,
        "fields": [
            {"field_id": "name", "bbox_label_id": "det_name"},
            {"field_id": "date", "bbox_label_id": "det_date"},
            {"field_id": "total", "bbox_label_id": "det_total"},
        ],
    }
    candidate = {
        "source_image": source,
        "fields": [{"field_id": "name", "bbox_label_id": "det_name"}],
    }

    result = web_api._validate_authoring_agent_apply_regression(previous, candidate)

    assert result["ready"] is False
    assert result["errors"][0]["code"] == "authoring_agent_existing_field_coverage_drop"
    assert result["summary"]["previousFieldCount"] == 3
    assert result["summary"]["candidateFieldCount"] == 1


def test_authoring_agent_apply_regression_allows_same_page_bbox_update(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(web_api, "ROOT", tmp_path)
    source = str(tmp_path / "page_001.png")
    previous = {
        "source_image": source,
        "fields": [{"field_id": "name", "bbox_label_id": "det_name", "bbox": [10, 10, 20, 10]}],
    }
    candidate = {
        "source_image": source,
        "fields": [{"field_id": "name", "bbox_label_id": "det_name", "bbox": [12, 11, 22, 11]}],
    }

    result = web_api._validate_authoring_agent_apply_regression(previous, candidate)

    assert result["ready"] is True
    assert result["summary"]["retainedAnchorCount"] == 1


def test_authoring_agent_apply_regression_allows_new_document(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(web_api, "ROOT", tmp_path)
    candidate = {
        "source_image": str(tmp_path / "page_001.png"),
        "fields": [{"field_id": "name", "bbox_label_id": "det_name"}],
    }

    result = web_api._validate_authoring_agent_apply_regression(None, candidate)

    assert result["ready"] is True
    assert result["summary"]["previousFieldCount"] == 0


def test_blank_template_agent_validation_rejects_static_label_field_anchor(tmp_path: Path) -> None:
    request_dir = tmp_path / "request"
    request_dir.mkdir()
    (request_dir / "request.json").write_text(
        json.dumps({"contract": {"sample_kind": "blank_template"}, "inputs": {"sampleKind": "blank_template"}}, ensure_ascii=False),
        encoding="utf-8",
    )
    required_payloads = {
        "schema_draft.json": {
            "schema_version": 1,
            "semantic_schema": {"환자성명": ""},
            "fields": [{"field_id": "patient_name", "key": "환자성명", "anchor_id": "det_label", "value": ""}],
        },
        "anchor_map_draft.json": {
            "schema_version": 1,
            "anchors": [{"anchor_id": "det_label", "status": "keep", "role": "static_label", "auto_type": "static_label"}],
        },
        "stylesheet_draft.json": {"schema_version": 1},
        "faker_profile_draft.json": {"schema_version": 1},
        "value_pool_draft.json": {"schema_version": 1},
        "research_report.json": {"schema_version": 1},
        "uncertainty_report.json": {"schema_version": 1},
    }
    for name, payload in required_payloads.items():
        (request_dir / name).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    (request_dir / "application_notes.md").write_text("notes", encoding="utf-8")

    validation = web_api._validate_authoring_agent_outputs(request_dir)

    assert validation["ready"] is False
    assert validation["summary"]["contractErrors"] >= 1
    assert any(error["code"] == "blank_template_static_label_as_field_anchor" for error in validation["contractErrors"])


def test_blank_template_agent_validation_requires_confirmed_use_value_anchor(tmp_path: Path) -> None:
    request_dir = tmp_path / "request"
    request_dir.mkdir()
    (request_dir / "request.json").write_text(
        json.dumps({"contract": {"sample_kind": "blank_template"}, "inputs": {"sampleKind": "blank_template"}}, ensure_ascii=False),
        encoding="utf-8",
    )
    payloads = {
        "schema_draft.json": {
            "schema_version": 1,
            "semantic_schema": {"환자성명": ""},
            "fields": [{"field_id": "patient_name", "key": "환자성명", "semantic_path": ["환자성명"], "anchor_id": "visual_0001", "value": ""}],
        },
        "anchor_map_draft.json": {
            "schema_version": 1,
            "anchors": [{"anchor_id": "visual_0001", "status": "keep", "role": "value_region", "auto_type": "table_cell", "text_source": "visual_line_detect"}],
        },
        "stylesheet_draft.json": {"schema_version": 1},
        "faker_profile_draft.json": {"schema_version": 1, "field_generators": {"patient_name": "person.name_ko"}},
        "value_pool_draft.json": {"schema_version": 1},
        "research_report.json": {"schema_version": 1, "sources": []},
        "uncertainty_report.json": {"schema_version": 1},
    }
    for name, payload in payloads.items():
        (request_dir / name).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    (request_dir / "application_notes.md").write_text("notes", encoding="utf-8")

    validation = web_api._validate_authoring_agent_outputs(request_dir)

    assert validation["ready"] is False
    assert any(error["code"] == "blank_template_no_value_anchors" for error in validation["contractErrors"])
    assert any(error["code"] == "blank_template_static_label_as_field_anchor" for error in validation["contractErrors"])

    payloads["anchor_map_draft.json"]["anchors"][0]["status"] = "use"
    (request_dir / "anchor_map_draft.json").write_text(json.dumps(payloads["anchor_map_draft.json"], ensure_ascii=False), encoding="utf-8")

    validation = web_api._validate_authoring_agent_outputs(request_dir)

    assert validation["ready"] is True


def test_blank_template_agent_validation_allows_hidden_semantic_fields_with_one_composite_render(tmp_path: Path) -> None:
    request_dir = tmp_path / "request"
    request_dir.mkdir()
    (request_dir / "request.json").write_text(
        json.dumps({"contract": {"sample_kind": "blank_template"}}, ensure_ascii=False),
        encoding="utf-8",
    )
    parsed = {
        "schema_draft.json": {
            "semantic_schema": {"입원정보": {"입원일": "", "퇴원일": "", "표시값": ""}},
            "fields": [
                {"field_id": "admission", "semantic_path": ["입원정보", "입원일"], "anchor_id": "cell_1", "render_policy": {"render": False}},
                {"field_id": "discharge", "semantic_path": ["입원정보", "퇴원일"], "anchor_id": "cell_1", "render_policy": {"render": False}},
                {"field_id": "display", "semantic_path": ["입원정보", "표시값"], "anchor_id": "cell_1", "render_policy": {"render": True}},
            ],
        },
        "anchor_map_draft.json": {
            "anchors": [{"anchor_id": "cell_1", "status": "use", "role": "value_region"}]
        },
    }

    errors = web_api._validate_blank_template_agent_contract(request_dir, parsed)

    assert not any(error["code"] == "blank_template_duplicate_field_anchor" for error in errors)


def test_authoring_agent_validation_auto_materializes_unmapped_use_anchor(tmp_path: Path) -> None:
    request_dir = tmp_path / "request"
    request_dir.mkdir()
    (request_dir / "request.json").write_text(json.dumps({"options": {"minPoolSize": 3}}, ensure_ascii=False), encoding="utf-8")
    payloads = {
        "schema_draft.json": {
            "schema_version": 1,
            "semantic_schema": {"성명": ""},
            "fields": [{"field_id": "name", "key": "성명", "semantic_path": ["성명"], "anchor_id": "det_name", "value": ""}],
            "unmapped_use_anchors": [{"anchor_id": "det_unknown", "reason": "uncertain"}],
        },
        "anchor_map_draft.json": {
            "schema_version": 1,
            "anchors": [
                {"anchor_id": "det_name", "status": "use", "role": "value_region", "bbox": [1, 2, 3, 4]},
                {"anchor_id": "det_unknown", "status": "use", "role": "value_region", "text": "미확인", "bbox": [5, 6, 7, 8]},
            ],
        },
        "stylesheet_draft.json": {"schema_version": 1},
        "faker_profile_draft.json": {"schema_version": 1, "field_generators": {"name": "person.name_ko"}},
        "value_pool_draft.json": {"schema_version": 1},
        "research_report.json": {"schema_version": 1, "sources": []},
        "uncertainty_report.json": {"schema_version": 1},
    }
    for name, payload in payloads.items():
        (request_dir / name).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    (request_dir / "application_notes.md").write_text("notes", encoding="utf-8")

    validation = web_api._validate_authoring_agent_outputs(request_dir)

    assert validation["ready"] is True
    schema = json.loads((request_dir / "schema_draft.json").read_text(encoding="utf-8"))
    faker = json.loads((request_dir / "faker_profile_draft.json").read_text(encoding="utf-8"))
    assert "unmapped_use_anchors" not in schema
    placeholder = next(field for field in schema["fields"] if field["anchor_id"] == "det_unknown")
    assert placeholder["semantic_path"][0] == "검토필요"
    assert placeholder["review_required"] is True
    assert faker["field_generators"][placeholder["field_id"]] == "free_text.short"


def test_authoring_agent_options_control_codex_command_and_pool_minimum(tmp_path: Path, monkeypatch) -> None:
    class FakeDoc:
        doc_id = "APP-14"
        title = "카드발급신청서"

        def to_dict(self) -> dict[str, object]:
            return {"docId": self.doc_id, "title": self.title}

    fake_doc = FakeDoc()
    fake_registry = SimpleNamespace(documents={fake_doc.doc_id: fake_doc})
    captured: dict[str, object] = {}
    prompts: list[str] = []

    def fake_workbench_subdir(doc_id: str, subdir: str):
        target = tmp_path / "workbench" / doc_id / subdir
        target.mkdir(parents=True, exist_ok=True)
        return target

    def fake_run(cmd, prompt, **kwargs):  # noqa: ANN001
        captured["cmd"] = cmd
        prompts.append(prompt)
        request_dir = sorted((tmp_path / "workbench" / fake_doc.doc_id / "authoring" / "agent_requests").glob("*"))[-1]
        for name in web_api.AUTHORING_AGENT_REQUIRED_OUTPUTS:
            path = request_dir / name
            if name.endswith(".json"):
                payload = {"schema_version": 1, "name": name}
                if name == "schema_draft.json":
                    payload.update({"semantic_schema": {"항목": ""}, "fields": [{"field_id": "field_1", "key": "항목", "semantic_path": ["항목"], "anchor_id": "det_1", "value": ""}]})
                elif name == "faker_profile_draft.json":
                    payload.update({"field_generators": {"field_1": "pool:items"}, "data_pools": {"items": ["A", "B", "C", "D"]}})
                elif name == "anchor_map_draft.json":
                    payload.update({"anchors": [{"anchor_id": "det_1", "status": "use", "role": "value_region"}]})
                elif name == "research_report.json":
                    payload.update({"sources": []})
                path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            else:
                path.write_text("ok", encoding="utf-8")
        kwargs["stdout_path"].write_text("ok", encoding="utf-8")
        kwargs["stderr_path"].write_text("tokens used\n42\n", encoding="utf-8")
        Path(cmd[cmd.index("--output-last-message") + 1]).write_text("ok", encoding="utf-8")
        return web_api._AgentProcessResult(returncode=0, stdout_tail="ok", stderr_tail="", pid=456)

    monkeypatch.setattr(web_api, "ROOT", tmp_path)
    monkeypatch.setattr(web_api, "load_registry", lambda: fake_registry)
    monkeypatch.setattr(web_api, "workbench_subdir", fake_workbench_subdir)
    monkeypatch.setattr(web_api, "list_work_items", lambda registry: [{"docId": fake_doc.doc_id, "samples": [], "latestReview": "", "latestInpainted": ""}])
    monkeypatch.setattr(web_api, "update_manifest_artifact", lambda *args, **kwargs: None)
    monkeypatch.setattr(web_api, "_run_codex_process", fake_run)

    payload = web_api.authoring_agent_run_payload(
        {"docId": fake_doc.doc_id, "options": {"reasoningEffort": "high", "fastMode": True, "minPoolSize": 4, "executionMode": "single_pass"}},
        async_run=False,
    )

    assert payload["status"] == "succeeded"
    assert payload["executionMode"] == "single_pass"
    assert payload["passState"]["planned"] == ["full"]
    assert len(prompts) == 1
    assert "full draft generation" in prompts[0]
    assert 'model_reasoning_effort="high"' in captured["cmd"]
    assert "--enable" in captured["cmd"]
    assert captured["cmd"][captured["cmd"].index("--enable") + 1] == "fast_mode"


def test_business_registration_rule_and_fixed_as_of_date_are_agent_contract_inputs() -> None:
    assert web_api._faker_rule_supported("business_reg_no") is True
    options = web_api._authoring_agent_options({"options": {"asOfDate": "2026-07-13"}})
    assert options["asOfDate"] == "2026-07-13"
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        web_api._authoring_agent_options({"options": {"asOfDate": "2026/07/13"}})


def test_faker_pool_contract_separates_scalar_record_and_closed_set_minimums() -> None:
    fields = [
        {"field_id": "category"},
        {"field_id": "diagnosis_name"},
        {"field_id": "diagnosis_code"},
    ]
    faker_profile = {
        "field_generators": {
            "category": "pool:categories",
            "diagnosis_name": "free_text.short",
            "diagnosis_code": "pattern:A##.#",
        },
        "data_pools": {
            "categories": ["신규", "갱신"],
            "diagnoses": [{"name": "급성 기관지염", "code": "J20.9"}],
        },
        "constraints": [
            {
                "type": "pick_record",
                "pool": "diagnoses",
                "targets": {"diagnosis_name": "name", "diagnosis_code": "code"},
            }
        ],
    }

    errors = web_api._validate_faker_profile_contract(faker_profile, fields, min_pool_size=20, min_record_pool_size=12)
    assert {error["code"] for error in errors} == {"faker_pool_too_small", "faker_record_pool_too_small"}

    faker_profile["pool_policies"] = {
        "categories": {"closed_set": True, "exception_kind": "legal_or_form_closed_set", "evidence": "서식상 신규/갱신 택1"},
    }
    errors = web_api._validate_faker_profile_contract(faker_profile, fields, min_pool_size=20, min_record_pool_size=12)
    assert {error["code"] for error in errors} == {"faker_record_pool_too_small"}
