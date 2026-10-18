"""UID-backed local account profiles with lossless legacy binding."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import threading

UID_PATTERN = re.compile(r"\d{8,20}\Z")
MAX_UID = 18446744073709551615


def validate_uid(value):
    if not isinstance(value, str) or not UID_PATTERN.fullmatch(value):
        raise ValueError("UID必须是8–20位数字")
    if int(value) > MAX_UID:
        raise ValueError("UID超出游戏账号范围")
    return value


def _timestamp():
    return datetime.now(timezone.utc).isoformat()


class AccountProfiles:
    """Maps stable storage keys to verified game UIDs and editable notes.

    Existing account labels remain their storage keys, so this index never
    moves or rewrites native snapshots, OCR batches, or saved build plans.
    """
    def __init__(self, inventory_directory, vision_directory=None):
        self.directory = Path(inventory_directory)
        self.vision_directory = Path(vision_directory) if vision_directory else None
        self.path = self.directory / "accounts.json"
        self.lock = threading.RLock()
        self.profiles = {}
        self._load()

    @staticmethod
    def _valid_key(value):
        return isinstance(value, str) and bool(value.strip()) and len(value) <= 80

    def _load(self):
        if self.path.exists():
            if self.path.stat().st_size > 2 * 1024 * 1024:
                raise ValueError("本机账号索引文件过大，请保留文件检查")
            value = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(value, dict) or value.get("schema_version") != 1 or not isinstance(value.get("profiles"), dict):
                raise ValueError("本机账号索引格式无效，请保留文件检查")
            seen_uids = set()
            for key, row in value["profiles"].items():
                if not self._valid_key(key) or not isinstance(row, dict):
                    raise ValueError("本机账号索引记录无效")
                uid = row.get("uid")
                if uid is not None:
                    validate_uid(uid)
                    if uid in seen_uids:
                        raise ValueError("本机账号索引包含重复UID")
                    seen_uids.add(uid)
                note = row.get("note", "")
                if not isinstance(note, str) or len(note) > 80:
                    raise ValueError("本机账号备注无效")
                self.profiles[key] = {
                    "account": key, "uid": uid, "note": note,
                    "created_at": str(row.get("created_at", ""))[:64],
                    "updated_at": str(row.get("updated_at", ""))[:64],
                    "former_uid": row.get("former_uid") if isinstance(row.get("former_uid"), str) else None,
                }

    def _write(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix("." + secrets.token_hex(6) + ".tmp")
        payload = {"schema_version": 1, "profiles": self.profiles}
        try:
            temporary.write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False), encoding="utf-8")
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)

    def _ensure_unbound(self, account):
        if not self._valid_key(account):
            return False
        if account not in self.profiles:
            now = _timestamp()
            self.profiles[account] = {"account": account, "uid": None, "note": account,
                                      "created_at": now, "updated_at": now, "former_uid": None}
            return True
        return False

    def discover_legacy(self, current_account=None):
        """Index old label-only data without claiming a UID for any of it."""
        changed = False
        data_accounts = set()
        with self.lock:
            for path in self.directory.glob("account-*.json"):
                if path.name.endswith(".previous.json") or path.is_symlink():
                    continue
                try:
                    if path.stat().st_size > 64 * 1024 * 1024:
                        continue
                    account = json.loads(path.read_text(encoding="utf-8")).get("account")
                    if self._valid_key(account): data_accounts.add(account)
                    changed |= self._ensure_unbound(account)
                except (OSError, ValueError, AttributeError):
                    continue
            if self.vision_directory and self.vision_directory.is_dir():
                for path in self.vision_directory.glob("*/*/batch.json"):
                    if path.is_symlink():
                        continue
                    try:
                        if path.stat().st_size > 16 * 1024 * 1024:
                            continue
                        batch = json.loads(path.read_text(encoding="utf-8"))
                        if self._valid_key(batch.get("account")): data_accounts.add(batch["account"])
                        changed |= self._ensure_unbound(batch.get("account"))
                    except (OSError, ValueError, AttributeError):
                        continue
            plans_directory = self.directory / "build-plans"
            if plans_directory.is_dir():
                for path in plans_directory.glob("*.json"):
                    if path.is_symlink():
                        continue
                    try:
                        if path.stat().st_size > 2 * 1024 * 1024:
                            continue
                        value = json.loads(path.read_text(encoding="utf-8"))
                        if self._valid_key(value.get("account")): data_accounts.add(value["account"])
                        changed |= self._ensure_unbound(value.get("account"))
                    except (OSError, ValueError, AttributeError):
                        continue
            for account, profile in list(self.profiles.items()):
                if profile.get("uid") is None and not profile.get("former_uid") and account not in data_accounts:
                    del self.profiles[account]
                    changed = True
            if changed:
                self._write()

    def _profile(self, account):
        if not self._valid_key(account):
            raise ValueError("账号资料无效")
        return self.profiles.get(account)

    def get(self, account):
        with self.lock:
            profile = self._profile(account)
            return dict(profile) if profile else None

    def resolve_uid(self, uid):
        uid = validate_uid(uid)
        with self.lock:
            for profile in self.profiles.values():
                if profile.get("uid") == uid:
                    return dict(profile)
            key = "uid:" + uid
            suffix = 2
            while key in self.profiles:
                key = "uid:" + uid + ":" + str(suffix)
                suffix += 1
            now = _timestamp()
            self.profiles[key] = {"account": key, "uid": uid, "note": "",
                                  "created_at": now, "updated_at": now, "former_uid": None}
            self._write()
            return dict(self.profiles[key])

    def select(self, account):
        with self.lock:
            profile = self._profile(account)
            if not profile:
                raise ValueError("请选择已发现的账号资料")
            return dict(profile)

    def set_note(self, account, note):
        if not isinstance(note, str) or len(note.strip()) > 80:
            raise ValueError("备注最多80个字符")
        with self.lock:
            profile = self._profile(account)
            if not profile:
                raise ValueError("账号资料不存在")
            profile["note"] = note.strip()
            profile["updated_at"] = _timestamp()
            self._write()
            return dict(profile)

    def remove(self, account):
        with self.lock:
            profile = self._profile(account)
            if not profile:raise ValueError('账号资料不存在')
            del self.profiles[account]
            try:self._write()
            except Exception:
                self.profiles[account] = profile
                raise

    def captured_uids(self, account):
        """Return UIDs already recorded by this account's native, OCR, or plan data."""
        if not self._valid_key(account):
            raise ValueError("账号资料无效")
        found = set()

        def collect(value):
            if not isinstance(value, dict) or value.get("account") != account:
                return
            uid = value.get("account_uid")
            if uid is not None:
                found.add(validate_uid(uid))

        native_path = self.directory / ("account-" + hashlib.sha256(account.encode()).hexdigest() + ".json")
        if native_path.is_file() and not native_path.is_symlink() and native_path.stat().st_size <= 64 * 1024 * 1024:
            collect(json.loads(native_path.read_text(encoding="utf-8")))
        if self.vision_directory and self.vision_directory.is_dir():
            vision_root = self.vision_directory / hashlib.sha256(account.encode()).hexdigest()
            vision_batches = vision_root.glob("*/batch.json") if vision_root.is_dir() and not vision_root.is_symlink() else ()
            for path in vision_batches:
                if path.is_symlink() or path.stat().st_size > 16 * 1024 * 1024:
                    continue
                collect(json.loads(path.read_text(encoding="utf-8")))
        plans_directory = self.directory / "build-plans"
        plan_key = hashlib.sha256(json.dumps(account, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()
        plan_path = plans_directory / (plan_key + ".json")
        if plan_path.is_file() and not plan_path.is_symlink() and plan_path.stat().st_size <= 2 * 1024 * 1024:
            collect(json.loads(plan_path.read_text(encoding="utf-8")))
        return sorted(found)

    def bind(self, account, uid, replace_existing=False):
        uid = validate_uid(uid)
        if type(replace_existing) is not bool:
            raise ValueError("UID冲突确认状态无效")
        with self.lock:
            source = self._profile(account)
            if not source:
                raise ValueError("账号资料不存在")
            previous_uids = set(self.captured_uids(account))
            previous_uids.update(value for value in (source.get("uid"), source.get("former_uid")) if value)
            mismatched_uids = sorted(value for value in previous_uids if value != uid)
            if mismatched_uids:
                return {"uid_mismatch": True, "source": self.summary(source),
                        "requested_uid": uid, "existing_uids": mismatched_uids}
            target = next((row for row in self.profiles.values()
                           if row.get("uid") == uid and row["account"] != account), None)
            if target and not replace_existing:
                return {"conflict": True, "source": self.summary(source), "target": self.summary(target)}

            old_uid = source.get("uid")
            if target:
                target["former_uid"] = uid
                target["uid"] = None
                if not target.get("note"):
                    target["note"] = ""
                target["updated_at"] = _timestamp()
            source["former_uid"] = old_uid if old_uid and old_uid != uid else source.get("former_uid")
            source["uid"] = uid
            source["updated_at"] = _timestamp()
            self._write()
            return {"conflict": False, "source": self.summary(source),
                    "displaced": self.summary(target) if target else None}

    @staticmethod
    def summary(profile):
        if not profile:
            return None
        return {"account": profile["account"], "uid": profile.get("uid"),
                "note": profile.get("note", ""), "former_uid": profile.get("former_uid")}

    def list_profiles(self, active_account=None):
        with self.lock:
            rows = []
            for profile in self.profiles.values():
                uid = profile.get("uid")
                note = profile.get("note", "")
                display_name = ((note + " · " if note else "") + "UID " + uid
                                if uid else "待绑定 UID · " + (note or profile["account"]))
                rows.append({**self.summary(profile), "display_name": display_name,
                             "bound": uid is not None, "active": profile["account"] == active_account})
            return sorted(rows, key=lambda row: (not row["active"], not row["bound"], row["display_name"].casefold()))

    def data_counts(self, account, vision, inventory_path, plans_path=None):
        """Small conflict summary used before a user confirms a binding change."""
        return {
            "native_snapshot": Path(inventory_path).is_file(),
            "ocr_batches": len(vision.history(account)) if vision else 0,
            "saved_plans": bool(plans_path and Path(plans_path).is_file()),
        }
