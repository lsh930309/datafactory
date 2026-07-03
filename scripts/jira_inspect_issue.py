#!/usr/bin/env python3
"""Inspect a Jira issue and its incomplete subtasks.

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
import json
import os
import sys
from typing import Any
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class JiraError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("issue_key", help="Parent issue key, e.g. JUNGLETFT-1726")
    parser.add_argument("--json", action="store_true", help="Print raw summary as JSON.")
    return parser.parse_args()


def base_url() -> str:
    value = os.environ.get("JIRA_BASE_URL") or local_secret("jira_base_url") or "https://koreadeep.atlassian.net"
    value = value.rstrip("/")
    if not value:
        raise JiraError("Set JIRA_BASE_URL, e.g. https://your-domain.atlassian.net.")
    return value


def local_secret(name: str) -> str:
    path = os.path.join(ROOT, ".env", name)
    if not os.path.exists(path):
        return ""
    return open(path, "r", encoding="utf-8").read().strip()


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


def jira_get(path: str) -> Any:
    req = Request(
        base_url() + path,
        headers={"Authorization": auth_header(), "Accept": "application/json"},
        method="GET",
    )
    try:
        with urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise JiraError(f"GET {path} failed: HTTP {exc.code}: {detail}") from exc


def issue_summary(issue: dict[str, Any]) -> dict[str, Any]:
    fields = issue.get("fields", {})
    status = fields.get("status") or {}
    status_category = status.get("statusCategory") or {}
    issue_type = fields.get("issuetype") or {}
    return {
        "key": issue.get("key"),
        "summary": fields.get("summary"),
        "issue_type": issue_type.get("name"),
        "status": status.get("name"),
        "status_category": status_category.get("key"),
    }


def fetch_issue(issue_key: str) -> dict[str, Any]:
    fields = "summary,status,subtasks,issuetype,parent"
    return jira_get(f"/rest/api/3/issue/{quote(issue_key)}?fields={fields}")


def main() -> int:
    args = parse_args()
    parent = fetch_issue(args.issue_key)
    parent_info = issue_summary(parent)

    subtasks = parent.get("fields", {}).get("subtasks") or []
    child_infos: list[dict[str, Any]] = []
    for subtask in subtasks:
        child = fetch_issue(subtask["key"])
        child_infos.append(issue_summary(child))

    incomplete = [item for item in child_infos if item.get("status_category") != "done"]
    result = {
        "parent": parent_info,
        "subtask_count": len(child_infos),
        "incomplete_subtask_count": len(incomplete),
        "incomplete_subtasks": incomplete,
        "all_subtasks": child_infos,
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"{parent_info['key']}: {parent_info['summary']}")
        print(f"status: {parent_info['status']} ({parent_info['status_category']})")
        print(f"subtasks: {len(child_infos)}, incomplete: {len(incomplete)}")
        for item in incomplete:
            print(f"- {item['key']}: {item['summary']} [{item['status']}]")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except JiraError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
