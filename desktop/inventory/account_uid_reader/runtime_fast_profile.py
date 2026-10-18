"""Version-pinned discovery hints and efficient executable fingerprinting."""

import hashlib
import os
from pathlib import Path

_PROFILES = {
    "84a55352f6ad4a495ae349b18e273739f2a003f932f83fd56ecadceadafb1024": {
        "image_size": 282279936,
        "profile_id": "htgame-win64-84a55352",
        "object_registry_rva": 0xFB1AF80,
        "name_pool_rva": 0xFA36E00,
    },
}


def profile_for(game_sha256, image_size):
    """Return an exact SHA/size profile; never guess for another build."""
    profile = _PROFILES.get(game_sha256)
    if profile is None or type(image_size) is not int:
        return None
    if profile["image_size"] != image_size:
        return None
    return dict(profile)


def executable_file_state(path):
    stat = Path(path).stat()
    return {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def sha256_file(path):
    """Hash in bounded memory instead of materializing a large game image."""
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def resolve_game_sha256(path, previous_report=None):
    """Reuse a same-capture digest only while executable path and stat match."""
    path = Path(path).resolve()
    state = executable_file_state(path)
    if isinstance(previous_report, dict):
        identity = previous_report.get("identity", {})
        previous_path = identity.get("executable") if isinstance(identity, dict) else None
        digest = previous_report.get("game_sha256")
        if previous_path:
            try:
                same_path = os.path.normcase(str(Path(previous_path).resolve())) == os.path.normcase(str(path))
            except (OSError, RuntimeError):
                same_path = False
            if (same_path and previous_report.get("executable_file_state") == state
                    and isinstance(digest, str) and len(digest) == 64
                    and all(ch in "0123456789abcdefABCDEF" for ch in digest)):
                return digest.lower(), state, True
    return sha256_file(path), state, False
