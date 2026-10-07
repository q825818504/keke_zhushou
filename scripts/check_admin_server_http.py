#!/usr/bin/env python3
"""Read-only HTTP integration checks for the local admin bridge."""

from __future__ import annotations

import argparse
import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def get_json(url: str, headers: dict[str, str] | None = None) -> tuple[int, dict]:
    try:
        with urlopen(Request(url, headers=headers or {}), timeout=5) as response:
            return response.status, json.loads(response.read())
    except HTTPError as error:
        return error.code, json.loads(error.read())


def post_json(url: str, payload: dict, headers: dict[str, str]) -> tuple[int, dict]:
    request = Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    try:
        with urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read())
    except HTTPError as error:
        return error.code, json.loads(error.read())


def get_bytes(url: str, headers: dict[str, str] | None = None) -> tuple[int, bytes]:
    try:
        with urlopen(Request(url, headers=headers or {}), timeout=5) as response:
            return response.status, response.read()
    except HTTPError as error:
        return error.code, error.read()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True, help="base URL, e.g. http://127.0.0.1:18991")
    args = parser.parse_args()
    base = args.url.rstrip("/")
    port = base.rsplit(":", 1)[-1]

    status, ping = get_json(f"{base}/api/ping")
    assert status == 200 and ping.get("service") == "keke-admin", f"unexpected ping: {status}, {ping}"
    status, state = get_json(f"{base}/api/status")
    assert status == 200 and isinstance(state.get("git"), dict), f"unexpected status response: {status}, {state}"
    assert state["git"].get("available") is True or state["git"].get("error"), "Git status should be explicit"

    for path, expected in (
        ("/", b"<title>"),
        ("/styles.css", b".repo-sync-dialog"),
        ("/data/knowledge/character_overrides.js", b"window.characterOverrides"),
    ):
        response_status, body = get_bytes(base + path)
        assert response_status == 200 and expected in body, f"expected local app asset was unavailable: {path}"
    for path in ("/scripts/admin_server.py", "/data/mysqil/ATTRIBUTION.md", "/.planning/.active_plan"):
        response_status, _ = get_bytes(base + path)
        assert response_status == 404, f"private or maintenance path must not be served: {path}"

    rejected_host_status, rejected_host = get_json(
        f"{base}/api/ping", {"Host": f"localhost:{port}"}
    )
    assert rejected_host_status == 403 and rejected_host.get("ok") is False, "unexpected Host should be rejected"

    invalid_write_status, invalid_write = post_json(
        f"{base}/api/teams",
        {"overrides": {"edits": {"bad id": {}}, "removed": []}},
        {"Content-Type": "application/json", "Origin": base},
    )
    assert invalid_write_status == 400 and invalid_write.get("ok") is False, "invalid team write should be rejected"

    missing_origin_status, missing_origin = post_json(
        f"{base}/api/teams",
        {"overrides": {"edits": {}, "removed": []}},
        {"Content-Type": "application/json"},
    )
    assert missing_origin_status == 403 and missing_origin.get("ok") is False, "POST without Origin should be rejected"
    print("Admin HTTP checks passed: ping/status, Host and Origin guards, invalid write validation.")


if __name__ == "__main__":
    main()
