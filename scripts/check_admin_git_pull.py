#!/usr/bin/env python3
"""Test safe fast-forward pulls against a temporary local bare remote."""

from __future__ import annotations

import json
import subprocess
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import admin_server as admin


def git(repository: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), *args], check=True,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return result.stdout.strip()


def post(port: int, path: str, payload: dict) -> tuple[int, dict]:
    request = Request(
        f"http://127.0.0.1:{port}{path}", data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Origin": f"http://127.0.0.1:{port}"}, method="POST",
    )
    try:
        with urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read())
    except HTTPError as error:
        return error.code, json.loads(error.read())


def pull(port: int) -> tuple[int, dict]:
    return post(port, "/api/git/pull", {})


def check_sync_allowlist(base: Path) -> None:
    remote = base / "sync-remote.git"
    local = base / "sync-local"
    git(base, "init", "--bare", "--initial-branch=main", str(remote))
    git(base, "init", "--initial-branch=main", str(local))
    git(local, "config", "user.name", "Keke test")
    git(local, "config", "user.email", "keke-test@example.invalid")
    for relative in admin.GIT_PATHS:
        file = local / relative
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text("base\n", encoding="utf-8")
    readme = local / "README.md"
    readme.write_text("base readme\n", encoding="utf-8")
    git(local, "add", "--all")
    git(local, "commit", "-m", "base")
    git(local, "remote", "add", "origin", str(remote))
    git(local, "push", "--set-upstream", "origin", "main")

    managed_file = local / "data" / "knowledge" / "team_overrides.json"
    managed_file.write_text("managed update\n", encoding="utf-8")
    readme.write_text("local unrelated edit\n", encoding="utf-8")
    with patch.object(admin, "ROOT", local):
        server = ThreadingHTTPServer(("127.0.0.1", 0), admin.Handler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            status, result = post(server.server_port, "/api/git/sync", {"message": "sync allowlist test"})
            assert status == 200 and result.get("ok") is True, f"allowlisted sync failed: {result}"
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=5)

    assert git(remote, "show", "main:data/knowledge/team_overrides.json") == "managed update"
    assert git(remote, "show", "main:README.md") == "base readme"
    committed = set(git(local, "diff", "--name-only", "HEAD~1", "HEAD").splitlines())
    assert committed == {"data/knowledge/team_overrides.json"}, f"sync committed unexpected files: {committed}"
    assert "README.md" in git(local, "status", "--porcelain")


def main() -> None:
    with TemporaryDirectory(prefix="keke-admin-git-check-") as temporary:
        base = Path(temporary)
        remote = base / "remote.git"
        local = base / "local"
        second = base / "second"
        git(base, "init", "--bare", "--initial-branch=main", str(remote))
        git(base, "init", "--initial-branch=main", str(local))
        git(local, "config", "user.name", "Keke test")
        git(local, "config", "user.email", "keke-test@example.invalid")
        (local / "shared.txt").write_text("base\n", encoding="utf-8")
        (local / "local-tracked.txt").write_text("base local\n", encoding="utf-8")
        git(local, "add", "--all")
        git(local, "commit", "-m", "base")
        git(local, "remote", "add", "origin", str(remote))
        git(local, "push", "--set-upstream", "origin", "main")
        git(base, "clone", str(remote), str(second))
        git(second, "config", "user.name", "Keke test")
        git(second, "config", "user.email", "keke-test@example.invalid")

        (second / "shared.txt").write_text("remote update\n", encoding="utf-8")
        git(second, "add", "shared.txt")
        git(second, "commit", "-m", "non-overlapping remote update")
        git(second, "push", "origin", "main")
        (local / "local-only.txt").write_text("keep me\n", encoding="utf-8")
        (local / "local-tracked.txt").write_text("local uncommitted tracked edit\n", encoding="utf-8")

        with patch.object(admin, "ROOT", local):
            server = ThreadingHTTPServer(("127.0.0.1", 0), admin.Handler)
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                status, result = pull(server.server_port)
                assert status == 200 and result.get("ok") is True, f"non-overlap fast-forward failed: {result}"
                assert (local / "shared.txt").read_text(encoding="utf-8") == "remote update\n"
                assert (local / "local-only.txt").read_text(encoding="utf-8") == "keep me\n"
                assert (local / "local-tracked.txt").read_text(encoding="utf-8") == "local uncommitted tracked edit\n"

                (second / "shared.txt").write_text("second remote update\n", encoding="utf-8")
                git(second, "add", "shared.txt")
                git(second, "commit", "-m", "overlapping remote update")
                git(second, "push", "origin", "main")
                (local / "shared.txt").write_text("local uncommitted edit\n", encoding="utf-8")
                status, result = pull(server.server_port)
                assert status == 409 and result.get("ok") is False, f"overlap should be rejected: {status}, {result}"
                assert (local / "shared.txt").read_text(encoding="utf-8") == "local uncommitted edit\n", "local content was overwritten"

                (second / "collision.txt").write_text("remote file\n", encoding="utf-8")
                git(second, "add", "collision.txt")
                git(second, "commit", "-m", "add collision target")
                git(second, "push", "origin", "main")
                (local / "collision.txt").write_text("local untracked file\n", encoding="utf-8")
                status, result = pull(server.server_port)
                assert status == 409 and result.get("ok") is False, f"untracked collision should be rejected: {status}, {result}"
                assert (local / "collision.txt").read_text(encoding="utf-8") == "local untracked file\n"
            finally:
                server.shutdown()
                server.server_close()
                worker.join(timeout=5)

        check_sync_allowlist(base)

    print("Admin Git checks passed: safe fast-forward, overlap rejection, and allowlisted sync without committing unrelated files.")


if __name__ == "__main__":
    main()
