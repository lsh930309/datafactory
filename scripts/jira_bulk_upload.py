#!/usr/bin/env python3
"""Bulk upload prepared result packages to Jira issues.

Reads ``outputs/jira_upload/jira_upload_plan.csv`` and, for each row with a
``ticket_key``, attaches the row's ZIP, adds the prepared comment, then
optionally transitions the issue to a completion state.

Environment variables:
  JIRA_BASE_URL     e.g. https://your-domain.atlassian.net
  JIRA_EMAIL        Jira Cloud email, for basic auth
  JIRA_API_TOKEN    Jira Cloud API token, for basic auth
  JIRA_PAT          Personal access token, for bearer auth

Local fallback files:
  .env/jira_base_url
  .env/jira_email
  .env/jira_api_token
"""

from __future__ import annotations

import argparse
import base64
import csv
import json
import mimetypes
import os
import sys
import uuid
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PLAN = ROOT / "outputs" / "jira_upload" / "jira_upload_plan.csv"


class JiraError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--transition-id", help="Jira transition id to apply after upload.")
    parser.add_argument("--transition-name", help="Jira transition name to resolve per issue.")
    parser.add_argument("--execute", action="store_true", help="Perform Jira writes. Default is dry-run.")
    parser.add_argument("--skip-attachments", action="store_true")
    parser.add_argument("--skip-comments", action="store_true")
    parser.add_argument("--skip-transition", action="store_true")
    parser.add_argument("--limit", type=int, help="Process only the first N mapped rows.")
    return parser.parse_args()


def local_secret(name: str) -> str:
    path = ROOT / ".env" / name
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


def auth_header() -> str:
    pat = os.environ.get("JIRA_PAT") or local_secret("jira_pat")
    if pat:
        return f"Bearer {pat}"

    email = os.environ.get("JIRA_EMAIL") or local_secret("jira_email") or "randy@koreadeep.com"
    token = os.environ.get("JIRA_API_TOKEN") or local_secret("jira_api_token")
    if email and token:
        raw = f"{email}:{token}".encode("utf-8")
        return "Basic " + base64.b64encode(raw).decode("ascii")

    raise JiraError("Set JIRA_PAT or both JIRA_EMAIL and JIRA_API_TOKEN.")


def base_url() -> str:
    value = os.environ.get("JIRA_BASE_URL") or local_secret("jira_base_url") or "https://koreadeep.atlassian.net"
    value = value.rstrip("/")
    if not value:
        raise JiraError("Set JIRA_BASE_URL, e.g. https://your-domain.atlassian.net.")
    return value


def jira_request(
    method: str,
    path: str,
    *,
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
) -> Any:
    request_headers = {
        "Authorization": auth_header(),
        "Accept": "application/json",
    }
    if headers:
        request_headers.update(headers)

    req = Request(base_url() + path, data=body, headers=request_headers, method=method)
    try:
        with urlopen(req, timeout=120) as resp:
            payload = resp.read()
            if not payload:
                return None
            return json.loads(payload.decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise JiraError(f"{method} {path} failed: HTTP {exc.code}: {detail}") from exc


def read_plan(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    return [row for row in rows if row.get("ticket_key", "").strip()]


def adf_comment(text: str) -> dict[str, Any]:
    paragraphs = []
    for line in text.splitlines():
        paragraphs.append(
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": line}] if line else [],
            }
        )
    return {"body": {"type": "doc", "version": 1, "content": paragraphs}}


def row_comment(row: dict[str, str]) -> str:
    comment_path = row.get("comment_path", "").strip()
    if comment_path:
        path = ROOT / comment_path
        if path.exists():
            return path.read_text(encoding="utf-8").strip()
    return row.get("comment", "").replace(" | ", "\n").strip()


def multipart_file(field: str, path: Path) -> tuple[bytes, str]:
    boundary = "----datafactory-" + uuid.uuid4().hex
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    chunks = [
        f"--{boundary}\r\n".encode("utf-8"),
        (
            f'Content-Disposition: form-data; name="{field}"; filename="{path.name}"\r\n'
            f"Content-Type: {mime}\r\n\r\n"
        ).encode("utf-8"),
        path.read_bytes(),
        f"\r\n--{boundary}--\r\n".encode("utf-8"),
    ]
    return b"".join(chunks), boundary


def attach_file(issue_key: str, path: Path) -> None:
    body, boundary = multipart_file("file", path)
    jira_request(
        "POST",
        f"/rest/api/3/issue/{quote(issue_key)}/attachments",
        body=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "X-Atlassian-Token": "no-check",
        },
    )


def add_comment(issue_key: str, text: str) -> None:
    body = json.dumps(adf_comment(text), ensure_ascii=False).encode("utf-8")
    jira_request(
        "POST",
        f"/rest/api/3/issue/{quote(issue_key)}/comment",
        body=body,
        headers={"Content-Type": "application/json"},
    )


def resolve_transition_id(issue_key: str, transition_name: str) -> str:
    data = jira_request("GET", f"/rest/api/3/issue/{quote(issue_key)}/transitions")
    transitions = data.get("transitions", []) if isinstance(data, dict) else []
    for transition in transitions:
        if transition.get("name", "").casefold() == transition_name.casefold():
            return str(transition["id"])
    available = ", ".join(t.get("name", "") for t in transitions)
    raise JiraError(f"{issue_key}: transition {transition_name!r} not found. Available: {available}")


def transition_issue(issue_key: str, transition_id: str) -> None:
    body = json.dumps({"transition": {"id": transition_id}}).encode("utf-8")
    jira_request(
        "POST",
        f"/rest/api/3/issue/{quote(issue_key)}/transitions",
        body=body,
        headers={"Content-Type": "application/json"},
    )


def main() -> int:
    args = parse_args()
    rows = read_plan(args.plan)
    if args.limit is not None:
        rows = rows[: args.limit]
    if not rows:
        print(f"No rows with ticket_key found in {args.plan}")
        return 1

    if not args.skip_transition and not (args.transition_id or args.transition_name):
        raise JiraError("Provide --transition-id or --transition-name, or pass --skip-transition.")

    for row in rows:
        issue_key = row["ticket_key"].strip()
        zip_path = ROOT / row["zip_path"]
        if not zip_path.exists():
            raise JiraError(f"{issue_key}: missing attachment {zip_path}")

        print(f"{issue_key}: {row['domain']} / {row['doc_id']} / {row['title']}")
        if args.execute:
            if not args.skip_attachments:
                attach_file(issue_key, zip_path)
                print(f"  attached {zip_path.name}")
            if not args.skip_comments:
                add_comment(issue_key, row_comment(row))
                print("  commented")
            if not args.skip_transition:
                transition_id = args.transition_id or resolve_transition_id(issue_key, args.transition_name)
                transition_issue(issue_key, transition_id)
                print(f"  transitioned via {transition_id}")
        else:
            print(f"  dry-run attachment: {zip_path}")
            if not args.skip_comments:
                print("  dry-run comment: yes")
            if not args.skip_transition:
                transition_label = args.transition_id or args.transition_name
                print(f"  dry-run transition: {transition_label}")

    mode = "executed" if args.execute else "dry-run"
    print(f"{mode}: processed {len(rows)} mapped row(s)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except JiraError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
