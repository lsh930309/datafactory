from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import stat
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CREDENTIAL_PATH = ROOT / ".env" / "deep_agent_api_key"
DEFAULT_BASE_URL = "https://agent-api.koreadeep.com"
DEFAULT_TIMEOUT_SECONDS = 180


class DeepAgentError(RuntimeError):
    def __init__(self, message: str, *, status: int | None = None, code: str = "DEEP_AGENT_ERROR") -> None:
        super().__init__(message)
        self.status = status
        self.code = code


@dataclass(frozen=True)
class DeepAgentCredentials:
    api_key: str
    webhook_secret: str = ""


def _parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def load_deep_agent_credentials(path: Path | None = None) -> DeepAgentCredentials:
    credential_path = path or DEFAULT_CREDENTIAL_PATH
    if not credential_path.exists():
        raise DeepAgentError(f"DeepAgent credential file not found: {credential_path}", code="CREDENTIAL_FILE_MISSING")
    values = _parse_env_file(credential_path)
    api_key = values.get("API_KEY", "").strip()
    if not api_key:
        raise DeepAgentError("DeepAgent API_KEY is missing", code="API_KEY_MISSING")
    return DeepAgentCredentials(api_key=api_key, webhook_secret=values.get("WEBHOOK_SECRET", "").strip())


def deep_agent_credential_status(path: Path | None = None) -> dict[str, Any]:
    credential_path = path or DEFAULT_CREDENTIAL_PATH
    values = _parse_env_file(credential_path) if credential_path.exists() else {}
    mode = stat.S_IMODE(credential_path.stat().st_mode) if credential_path.exists() else None
    permission_safe = mode is None or os.name != "posix" or mode & 0o077 == 0
    return {
        "ready": bool(values.get("API_KEY", "").strip()),
        "apiKeyPresent": bool(values.get("API_KEY", "").strip()),
        "webhookSecretPresent": bool(values.get("WEBHOOK_SECRET", "").strip()),
        "permissionSafe": permission_safe,
        "permissionMode": f"{mode:03o}" if mode is not None else None,
        "path": str(credential_path),
    }


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def call_deep_agent_ocr(
    image_path: Path,
    *,
    credentials: DeepAgentCredentials | None = None,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    open_request: Callable[..., Any] = urlopen,
) -> dict[str, Any]:
    resolved_credentials = credentials or load_deep_agent_credentials()
    boundary = f"----datafactory-{secrets.token_hex(16)}"
    content_type = _image_content_type(image_path)
    header = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{image_path.name}"\r\n'
        f"Content-Type: {content_type}\r\n\r\n"
    ).encode("utf-8")
    body = header + image_path.read_bytes() + f"\r\n--{boundary}--\r\n".encode("utf-8")
    request = Request(
        f"{base_url.rstrip('/')}/api/v2/ocr/direct",
        data=body,
        method="POST",
        headers={
            "x-api-key": resolved_credentials.api_key,
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Accept": "application/json",
        },
    )
    try:
        with open_request(request, timeout=timeout) as response:
            status = int(response.status)
            raw = response.read()
    except HTTPError as exc:
        status = int(exc.code)
        raw = exc.read()
    except URLError as exc:
        raise DeepAgentError(f"DeepAgent network error: {type(exc.reason).__name__}", code="NETWORK_ERROR") from exc
    except TimeoutError as exc:
        raise DeepAgentError("DeepAgent request timed out", code="TIMEOUT") from exc

    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DeepAgentError(f"DeepAgent returned invalid JSON (HTTP {status})", status=status, code="INVALID_RESPONSE") from exc
    api_status = str(payload.get("status") or "").lower() if isinstance(payload, dict) else ""
    if status >= 400 or api_status in {"error", "failed"}:
        error_code = str(payload.get("error_code") or "HTTP_ERROR") if isinstance(payload, dict) else "HTTP_ERROR"
        error_message = str(payload.get("error_message") or f"DeepAgent request failed (HTTP {status})") if isinstance(payload, dict) else f"DeepAgent request failed (HTTP {status})"
        if resolved_credentials.api_key:
            error_message = error_message.replace(resolved_credentials.api_key, "[REDACTED]")
        if resolved_credentials.webhook_secret:
            error_message = error_message.replace(resolved_credentials.webhook_secret, "[REDACTED]")
        raise DeepAgentError(error_message, status=status, code=error_code)
    if not isinstance(payload, dict):
        raise DeepAgentError("DeepAgent response must be a JSON object", status=status, code="INVALID_RESPONSE")
    return payload


def normalize_deep_ocr_response(payload: dict[str, Any], *, source_image: Path, source_sha256: str | None = None) -> dict[str, Any]:
    fields: list[dict[str, Any]] = []
    results = payload.get("results") if isinstance(payload.get("results"), dict) else {}
    elements = results.get("elements") if isinstance(results.get("elements"), list) else []
    for element_index, element in enumerate(elements):
        if not isinstance(element, dict):
            continue
        page_number = element.get("page_number")
        key_values = element.get("key_value_list") if isinstance(element.get("key_value_list"), list) else []
        for item in key_values:
            if not isinstance(item, dict):
                continue
            raw_values = item.get("value") if isinstance(item.get("value"), list) else [item.get("value")]
            values = [str(value) for value in raw_values if value is not None and str(value).strip()]
            fields.append(
                {
                    "index": len(fields),
                    "elementIndex": element_index,
                    "pageNumber": page_number,
                    "key": str(item.get("key") or "").strip(),
                    "value": " ".join(values).strip(),
                    "values": values,
                    "type": str(item.get("type") or ""),
                    "confidence": float(item["confidence_score"]) if item.get("confidence_score") is not None else None,
                    "bbox": item.get("bbox"),
                }
            )
    return {
        "schemaVersion": 1,
        "provider": "deep_agent",
        "endpoint": "/api/v2/ocr/direct",
        "status": str(payload.get("status") or ""),
        "sourceImage": str(source_image),
        "sourceSha256": source_sha256 or file_sha256(source_image),
        "metadata": payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
        "fields": fields,
    }


def match_deep_ocr_fields(normalized: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    raw_labels = policy.get("labels") if isinstance(policy.get("labels"), list) else []
    labels: list[dict[str, Any]] = []
    for raw in raw_labels:
        if not isinstance(raw, dict) or not str(raw.get("id") or "").strip():
            continue
        text = str(raw.get("rec_text") or raw.get("text") or "").strip()
        labels.append({"id": str(raw["id"]), "text": text, "normalized": normalize_match_text(text)})
    matches: list[dict[str, Any]] = []
    for field in normalized.get("fields", []):
        if not isinstance(field, dict):
            continue
        value = str(field.get("value") or "").strip()
        target = normalize_match_text(value)
        exact = [label for label in labels if target and label["normalized"] == target]
        candidates = sorted(
            (_match_candidate(target, label) for label in labels if label["normalized"]),
            key=lambda candidate: (-candidate["score"], candidate["bboxLabelId"]),
        )[:5]
        if len(exact) == 1:
            status = "exact"
            bbox_label_id: str | None = exact[0]["id"]
        elif len(exact) > 1:
            status = "ambiguous"
            bbox_label_id = None
        else:
            status = "unmatched"
            bbox_label_id = None
        matches.append(
            {
                "fieldIndex": int(field.get("index") or 0),
                "key": str(field.get("key") or ""),
                "value": value,
                "confidence": field.get("confidence"),
                "bbox": field.get("bbox"),
                "status": status,
                "bboxLabelId": bbox_label_id,
                "candidates": candidates,
            }
        )
    return {
        "schemaVersion": 1,
        "provider": "deep_agent+paddleocr",
        "sourceImage": normalized.get("sourceImage"),
        "sourceSha256": normalized.get("sourceSha256"),
        "policyFingerprint": policy_fingerprint(policy),
        "summary": {
            "fieldCount": len(matches),
            "exactCount": sum(match["status"] == "exact" for match in matches),
            "ambiguousCount": sum(match["status"] == "ambiguous" for match in matches),
            "unmatchedCount": sum(match["status"] == "unmatched" for match in matches),
        },
        "matches": matches,
    }


def normalize_match_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).lower()
    return re.sub(r"[^0-9a-z가-힣]+", "", normalized)


def policy_fingerprint(policy: dict[str, Any]) -> str:
    labels = []
    for raw in policy.get("labels", []):
        if isinstance(raw, dict):
            labels.append(
                {
                    "id": str(raw.get("id") or ""),
                    "text": str(raw.get("text") or ""),
                    "rec_text": str(raw.get("rec_text") or ""),
                    "bbox": raw.get("bbox"),
                }
            )
    body = json.dumps({"source_image": policy.get("source_image"), "labels": labels}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _match_candidate(target: str, label: dict[str, Any]) -> dict[str, Any]:
    candidate = str(label["normalized"])
    if target == candidate:
        score = 1.0
        method = "exact"
    elif target and candidate and (target in candidate or candidate in target):
        score = 0.96
        method = "substring"
    else:
        score = SequenceMatcher(None, target, candidate).ratio() if target and candidate else 0.0
        method = "fuzzy"
    return {
        "bboxLabelId": label["id"],
        "text": label["text"],
        "score": round(float(score), 4),
        "method": method,
    }


def _image_content_type(path: Path) -> str:
    suffix = path.suffix.lower()
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".tif": "image/tiff",
        ".tiff": "image/tiff",
        ".bmp": "image/bmp",
    }.get(suffix, "application/octet-stream")
