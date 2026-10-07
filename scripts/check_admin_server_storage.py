#!/usr/bin/env python3
"""Exercise the repository write transaction against an isolated temporary tree."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from http.server import ThreadingHTTPServer
from subprocess import CompletedProcess
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.request import Request, urlopen

import admin_server as admin


def post_local(port: int, path: str, payload: dict | bytes, content_type: str = "application/json") -> tuple[int, dict]:
    body = payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(
        f"http://127.0.0.1:{port}{path}", data=body,
        headers={"Content-Type": content_type, "Origin": f"http://127.0.0.1:{port}"}, method="POST",
    )
    with urlopen(request, timeout=5) as response:
        response_body = response.read()
        return response.status, json.loads(response_body) if response_body else {}


def check_api_write_routes() -> None:
    with TemporaryDirectory(prefix="keke-admin-api-check-") as temporary:
        base = Path(temporary)
        root = base / "repo"
        knowledge = root / "data" / "knowledge"
        characters = knowledge / "characters"
        characters.mkdir(parents=True)
        for ident in ("role-a", "role-b", "role-c", "role-d"):
            (characters / f"{ident}.json").write_text(json.dumps({"id": ident}), encoding="utf-8")

        source = knowledge / "team_templates.json"
        original_catalog = {"schema_version": "1.0.0", "teams": []}
        source.write_text(json.dumps(original_catalog), encoding="utf-8")
        team_overrides_path = knowledge / "team_overrides.json"
        team_bundle_path = knowledge / "team_templates.js"
        char_overrides_path = knowledge / "character_overrides.json"
        char_bundle_path = knowledge / "character_overrides.js"
        team_overrides_path.write_text(json.dumps({"edits": {}, "removed": []}), encoding="utf-8")
        team_bundle_path.write_text("old team bundle", encoding="utf-8")

        image = root / "data" / "resources" / "characters" / "role-a" / "drive-layout.png"
        image.parent.mkdir(parents=True)
        image.write_bytes(b"old image")
        image_relative = image.relative_to(root).as_posix()
        seeded_character = {"schema_version": "1.0.0", "characters": {"role-a": {
            "recommended": {"weapon": {"id": "default", "name": "默认弧盘"}},
            "drive_layout_image": image_relative, "custom_note": "preserve",
        }}}
        char_overrides_path.write_text(json.dumps(seeded_character), encoding="utf-8")
        char_bundle_path.write_text("old character bundle", encoding="utf-8")
        backups = base / "backups"

        with (
            patch.object(admin, "ROOT", root),
            patch.object(admin, "KNOWLEDGE", knowledge),
            patch.object(admin, "TEAM_SOURCE", source),
            patch.object(admin, "TEAM_OVERRIDES", team_overrides_path),
            patch.object(admin, "TEAM_BUNDLE", team_bundle_path),
            patch.object(admin, "CHAR_OVERRIDES", char_overrides_path),
            patch.object(admin, "CHAR_BUNDLE", char_bundle_path),
            patch.object(admin, "_backup_root", return_value=backups),
        ):
            server = ThreadingHTTPServer(("127.0.0.1", 0), admin.Handler)
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                port = server.server_port
                status, result = post_local(port, "/api/characters/basic", {
                    "id": "role-a", "patch": {"name": "角色甲", "basic": {"element": "光", "role": "主C"}},
                })
                assert status == 200 and result.get("ok") is True, "valid role edit was not saved"
                saved = json.loads(char_overrides_path.read_text(encoding="utf-8"))["characters"]["role-a"]
                assert saved["basic"] == {"element": "光", "role": "主C"}
                assert saved["recommended"]["weapon"]["id"] == "default", "role edit lost recommendations"
                assert saved["drive_layout_image"] == image_relative, "role edit lost the layout path"
                assert saved["custom_note"] == "preserve", "role edit dropped unrelated override data"

                recommendation = {"weapon": {"id": "new-weapon", "name": "新弧盘"},
                    "cassette": {"id": "new-cassette", "name": "新卡带",
                    "recommended_main_affixes": [{"name": "暴击伤害", "priority": 5}],
                    "recommended_sub_affixes": [{"name": "暴击率", "priority": 4}]}}
                status, result = post_local(port, "/api/characters/save", {
                    "id": "role-a", "patch": {"name": "角色甲", "basic": {"rating": "T0"}},
                    "recommended": recommendation,
                })
                saved = json.loads(char_overrides_path.read_text(encoding="utf-8"))["characters"]["role-a"]
                assert status == 200 and saved["recommended"] == recommendation
                assert saved["basic"]["element"] == "光" and saved["basic"]["rating"] == "T0"
                assert saved["custom_note"] == "preserve" and saved["drive_layout_image"] == image_relative
                assert "暴击伤害" in char_bundle_path.read_text(encoding="utf-8")

                team = {
                    "id": "local-team", "member_character_ids": ["role-a", "role-b", "role-c", "role-d"],
                    "source_core_character_id": "role-a", "source_archetype": "本地测试阵容",
                    "editorial": {"notes": "isolated test", "active": True},
                }
                status, result = post_local(port, "/api/teams", {
                    "overrides": {"schema_version": "1.0.0", "edits": {"local-team": team}, "removed": []},
                })
                assert status == 200 and result.get("ok") is True, "valid team was not saved"
                assert "本地测试阵容" in team_bundle_path.read_text(encoding="utf-8")
                assert json.loads(source.read_text(encoding="utf-8")) == original_catalog, "team save changed source catalog"

                uploaded_image = b"\x89PNG\r\n\x1a\nlocal test"
                status, result = post_local(port, "/api/characters/layout?id=role-a", uploaded_image, "image/png")
                assert status == 200 and result.get("ok") is True, "layout image upload failed"
                assert image.read_bytes() == uploaded_image, "uploaded image bytes changed"
                status, result = post_local(port, "/api/characters/layout/delete", {"id": "role-a"})
                assert status == 200 and result.get("ok") is True, "layout image delete failed"
                assert not image.exists(), "layout image was not deleted"
                saved = json.loads(char_overrides_path.read_text(encoding="utf-8"))["characters"]["role-a"]
                assert "drive_layout_image" not in saved, "deleted image path remains in overrides"
            finally:
                server.shutdown()
                server.server_close()
                worker.join(timeout=5)

            git_result = CompletedProcess(["git"], 0, stdout=image_relative + "\0", stderr="")
            with patch.object(admin, "_run_git", return_value=git_result):
                assert image_relative in admin._managed_git_paths(), "deleted tracked image is not syncable"
            assert any(path.name == "drive-layout.png" for path in backups.rglob("*") if path.is_file()), "image backups are missing"


def main() -> None:
    with TemporaryDirectory(prefix="keke-admin-storage-check-") as temporary:
        base = Path(temporary)
        root = base / "repo"
        knowledge = root / "data" / "knowledge"
        knowledge.mkdir(parents=True)
        source = knowledge / "team_templates.json"
        original_catalog = {"schema_version": "1.0.0", "teams": []}
        source.write_text(json.dumps(original_catalog), encoding="utf-8")
        team_overrides_path = knowledge / "team_overrides.json"
        team_bundle_path = knowledge / "team_templates.js"
        character_overrides_path = knowledge / "character_overrides.json"
        character_bundle_path = knowledge / "character_overrides.js"
        team_overrides_path.write_text("{}", encoding="utf-8")
        team_bundle_path.write_text("old team bundle", encoding="utf-8")
        character_overrides_path.write_text("{}", encoding="utf-8")
        character_bundle_path.write_text("old character bundle", encoding="utf-8")
        image = root / "data" / "resources" / "characters" / "role-a" / "drive-layout.png"
        image.parent.mkdir(parents=True)
        image.write_bytes(b"old image")
        backups = base / "backups"
        team_overrides = {"schema_version": "1.0.0", "edits": {}, "removed": []}
        character_data = {"schema_version": "1.0.0", "characters": {"role-a": {}}}

        with (
            patch.object(admin, "ROOT", root),
            patch.object(admin, "KNOWLEDGE", knowledge),
            patch.object(admin, "TEAM_SOURCE", source),
            patch.object(admin, "TEAM_OVERRIDES", team_overrides_path),
            patch.object(admin, "TEAM_BUNDLE", team_bundle_path),
            patch.object(admin, "CHAR_OVERRIDES", character_overrides_path),
            patch.object(admin, "CHAR_BUNDLE", character_bundle_path),
            patch.object(admin, "_backup_root", return_value=backups),
        ):
            admin._commit_bundles(team_overrides=team_overrides, character_overrides=character_data)
            assert json.loads(source.read_text(encoding="utf-8")) == original_catalog, "source catalog changed"
            assert "window.teamGuideOverrides" in team_bundle_path.read_text(encoding="utf-8")
            assert "window.characterOverrides" in character_bundle_path.read_text(encoding="utf-8")
            assert any(
                path.name == "team_templates.js" and path.read_text(encoding="utf-8") == "old team bundle"
                for path in backups.rglob("*") if path.is_file()
            ), "previous bundle was not backed up"

            admin._commit_bundles(character_overrides=character_data, deletes=(image,))
            assert not image.exists(), "requested image deletion did not apply"
            assert any(
                path.name == "drive-layout.png" and path.read_bytes() == b"old image"
                for path in backups.rglob("*") if path.is_file()
            ), "deleted image was not backed up"

            tracked_image = image.relative_to(root).as_posix()
            git_result = CompletedProcess(["git"], 0, stdout=tracked_image + "\0", stderr="")
            with patch.object(admin, "_run_git", return_value=git_result):
                assert tracked_image in admin._managed_git_paths(), "deleted tracked image is not syncable"

            previous_bundle = team_bundle_path.read_bytes()
            try:
                admin._write_transaction({team_bundle_path: b"unsafe", base / "outside.txt": b"no"})
            except ValueError:
                pass
            else:
                raise AssertionError("write outside the repository should be rejected")
            assert team_bundle_path.read_bytes() == previous_bundle, "rejected transaction changed project files"

    check_api_write_routes()
    print("Admin storage checks passed: source preserved, bundle/write APIs exercised in isolation, backups kept, deleted layouts syncable, outside paths rejected.")


if __name__ == "__main__":
    main()
