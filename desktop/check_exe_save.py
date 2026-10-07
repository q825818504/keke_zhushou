"""Exercise the shipped EXE's real save button in a disposable workspace."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("exe")
    args = parser.parse_args()
    exe = Path(args.exe).resolve()
    with TemporaryDirectory(prefix="keke-real-save-") as temporary:
        repo = Path(temporary)
        (repo / ".git").mkdir()
        (repo / ".isolated-save-test").touch()
        for name in ("index.html", "app.js", "styles.css"):
            shutil.copy2(ROOT / name, repo / name)
        for file in ROOT.glob("*.js"):
            shutil.copy2(file, repo / file.name)
        shutil.copytree(ROOT / "data/knowledge", repo / "data/knowledge")
        # Force a new selection in a test copy, never touch real saved data.
        doc = json.loads((repo / "data/knowledge/character_overrides.json").read_text(encoding="utf-8"))
        doc["characters"].setdefault("nanali", {}).pop("recommended", None)
        (repo / "data/knowledge/character_overrides.json").write_text(json.dumps(doc), encoding="utf-8")
        (repo / "data/knowledge/character_overrides.js").write_text("window.characterOverrides = " + json.dumps(doc) + ";", encoding="utf-8")
        for mode in ("write", "read"):
            report = ROOT / ("build/desktop/real-exe-save-" + mode + ".json")
            subprocess.run([str(exe), "--workspace", str(repo), "--smoke-report", str(report), "--verify-save", mode], timeout=60, check=True)
            result = json.loads(report.read_text(encoding="utf-8"))
            assert result["ok"], result
            print(mode, result["checks"])
        saved = json.loads((repo / "data/knowledge/character_overrides.json").read_text(encoding="utf-8"))["characters"]["nanali"]
        assert saved["basic"]["rating"] == "T0"
        assert any(a["priority"] == 5 for a in saved["recommended"]["cassette"]["recommended_main_affixes"])
    print("Real EXE save and restart passed, including native dirty-state clearing.")


if __name__ == "__main__":
    main()
