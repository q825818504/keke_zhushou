"""Only temporary data is modified; verifies live public reads and isolation."""
import json
import threading
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from runtime import public_server


def main():
    with TemporaryDirectory(prefix="keke-public-read-") as temporary:
        base = Path(temporary)
        bundle, repo = base / "public", base / "repo"
        for root in (bundle, repo):
            (root / "data/knowledge").mkdir(parents=True)
            (root / "data/knowledge/character_overrides.js").write_text("old", encoding="utf-8")
        (bundle / "index.html").write_text("user only", encoding="utf-8")
        (bundle / "public-manifest.json").write_text(json.dumps({"files":{
            "index.html":"", "data/knowledge/character_overrides.js":""}}), encoding="utf-8")
        (repo / "admin_bridge.js").write_text("private", encoding="utf-8")
        (repo / "data/knowledge/character_overrides.json").write_text("private source", encoding="utf-8")
        image = repo / "data/resources/characters/nanali/drive-layout.png"
        image.parent.mkdir(parents=True)
        image.write_bytes(b"test image")
        selected = [repo]
        server = public_server(bundle, 0, workspace=lambda: selected[0])
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        url = "http://127.0.0.1:" + str(server.server_port)
        def get(relative):
            with urlopen(url + relative) as response:
                assert response.headers.get("Cache-Control") == "no-store"
                return response.read()
        try:
            before = get("/local-data-version")
            (repo / "data/knowledge/character_overrides.js").write_text("latest priority 5", encoding="utf-8")
            assert get("/data/knowledge/character_overrides.js") == b"latest priority 5"
            assert before != get("/local-data-version")
            assert get("/index.html") == b"user only"
            assert get("/data/resources/characters/nanali/drive-layout.png") == b"test image"
            for path in ("/admin_bridge.js", "/.git/config", "/api/status", "/data/knowledge/character_overrides.json",
                         "/data/resources/../knowledge/character_overrides.js"):
                try:
                    get(path)
                    raise AssertionError("Private or traversal path exposed: " + path)
                except HTTPError as error:
                    assert error.code == 404
            try:
                urlopen(Request(url+"/api/characters/save",data=b"{}",method="POST"))
                raise AssertionError("Public client accepted a write")
            except HTTPError as error:
                assert error.code == 405
            selected[0] = None
            assert get("/data/knowledge/character_overrides.js") == b"old"
        finally:
            server.shutdown();server.server_close();worker.join(timeout=5)
    print("Public local data passed: live reads, change detection, workspace fallback, no private paths/writes.")


if __name__ == "__main__":
    main()
