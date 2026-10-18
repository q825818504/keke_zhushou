"""Read active account identity fields from the current NTE PlayerState.

This is a bounded, read-only probe. It reuses the independent object/name
discovery and root resolver, with a checked reflected-property fallback. It
does not call the author's SDK, DLL, IPC, or modify the game.
"""
import argparse
import ctypes as C
import json
import re
import struct
import sys
from pathlib import Path

from .discover_runtime_names import inspect as discover_names
from .discover_runtime_objects import inspect as discover_registry
from .reader_api import Adapter, Roots
from .process_reader import ProcessReader, find_process_ids_by_image_name


DEFAULT_OUTPUT = Path(__file__).parent / "reports" / "reader-reconstruction" / "account-uid-live-probe.json"
CANDIDATE_FIELDS = (
    ("m_nRoleId", "role_id"),
    ("m_strPSAccountId", "platform_service_account_id"),
    ("m_strPSOnlineId", "platform_service_online_id"),
    ("PlayerId", "unreal_player_id"),
)


def mask_identifier(value):
    if not value:
        return ""
    if len(value) <= 4:
        return "*" * len(value)
    return value[:2] + "*" * min(8, len(value) - 4) + value[-2:]


def read_string_property(adapter, address, size):
    if size != 16:
        return {"decode_status": "unexpected_size", "size": size}
    data, count, capacity = struct.unpack("<Qii", adapter.read(address, 16))
    if not 0 <= count <= capacity <= 128:
        return {"decode_status": "invalid_fstring_header", "num": count, "capacity": capacity}
    if count == 0:
        return {"decode_status": "ok", "value": ""}
    if not 0x10000 <= data < 0x800000000000:
        return {"decode_status": "invalid_fstring_data"}
    raw = adapter.read(data, count * 2)
    value = raw.decode("utf-16-le", errors="strict").split("\0", 1)[0]
    return {"decode_status": "ok", "value": value}


def property_type_name(adapter, property_address):
    """Decode FField.ClassPrivate+8 → FFieldClass.Name+0."""
    class_private = struct.unpack("<Q", adapter.read(property_address + 8, 8))[0]
    if not 0x10000 <= class_private < 0x800000000000:
        raise RuntimeError("FField has an invalid ClassPrivate pointer")
    name_token = struct.unpack("<Q", adapter.read(class_private, 8))[0]
    return adapter.name(name_token)


def read_candidate(adapter, player_state, name, label, expected_uid):
    status, field = adapter.field(adapter.dll, player_state, name)
    result = {"field": name, "label": label, "status": status}
    if status:
        return result

    property_type = property_type_name(adapter, field.property)
    result.update({"property_type": property_type, "offset": field.offset, "size": field.size})
    address = player_state + field.offset

    if property_type in ("StrProperty", "StringProperty"):
        decoded = read_string_property(adapter, address, field.size)
        result["decode_status"] = decoded["decode_status"]
        if decoded["decode_status"] != "ok":
            result.update({k: v for k, v in decoded.items() if k != "decode_status"})
            return result
        value = decoded["value"]
        result["present"] = bool(value)
        result["length"] = len(value)
        result["numeric_uid_shape"] = bool(re.fullmatch(r"\d{8,20}", value))
        if expected_uid is not None:
            result["matches_visible_uid"] = value == expected_uid
        # Keep login/platform identifiers masked in the saved report. If one
        # equals the public UID shown in the game's UI, show that exact match.
        result["value"] = value if expected_uid is not None and value == expected_uid else mask_identifier(value)
        return result

    raw = adapter.read(address, field.size)
    if field.size == 4 and property_type in ("IntProperty", "UInt32Property"):
        value = struct.unpack("<i", raw)[0] if property_type == "IntProperty" else struct.unpack("<I", raw)[0]
    elif field.size == 8 and property_type in ("Int64Property", "UInt64Property"):
        value = struct.unpack("<q", raw)[0] if property_type == "Int64Property" else struct.unpack("<Q", raw)[0]
    else:
        result["decode_status"] = "unrecognized_type_or_size"
        result["raw_size"] = len(raw)
        return result
    result["decode_status"] = "ok"
    result["value"] = value
    if expected_uid is not None:
        result["matches_visible_uid"] = str(value) == expected_uid
    return result


def reflected_object(adapter, obj, name):
    status, field = adapter.field(adapter.dll, obj, name)
    if status:
        raise RuntimeError(f"{name} property lookup failed (status={status})")
    property_type = property_type_name(adapter, field.property)
    if field.size != 8 or property_type != "ObjectProperty":
        raise RuntimeError(f"{name} is not an 8-byte object reference ({property_type}, {field.size})")
    value = struct.unpack("<Q", adapter.read(obj + field.offset, 8))[0]
    if not 0x10000 <= value < 0x800000000000:
        raise RuntimeError(f"{name} contains an invalid object pointer")
    return value, {"field": name, "type": property_type, "offset": field.offset}


def first_array_object(adapter, obj, name):
    status, field = adapter.field(adapter.dll, obj, name)
    if status:
        raise RuntimeError(f"{name} property lookup failed (status={status})")
    property_type = property_type_name(adapter, field.property)
    if field.size != 16 or property_type != "ArrayProperty":
        raise RuntimeError(f"{name} is not a 16-byte reflected array ({property_type}, {field.size})")
    header = adapter.read(obj + field.offset, 16)
    data, count, capacity = struct.unpack("<Qii", header)
    if not 1 <= count <= capacity <= 128 or not 0x10000 <= data < 0x800000000000:
        raise RuntimeError(f"{name} has an invalid array header")
    value = struct.unpack("<Q", adapter.read(data, 8))[0]
    if not 0x10000 <= value < 0x800000000000:
        raise RuntimeError(f"{name}[0] is not a valid object pointer")
    return value, header, {"field": name, "type": property_type, "offset": field.offset, "count": count}


def resolve_player_state(adapter, registry):
    candidate = next(row for row in registry["candidates"] if row.get("verified"))
    registry_address = int(candidate["address"], 16)
    chunks, _, maximum, count, max_chunks, num_chunks = struct.unpack("<QQiiii", adapter.read(registry_address, 32))
    if not (0 < count <= maximum <= 67108864 and 0 < num_chunks <= max_chunks <= 1024
            and maximum == max_chunks * 65536 and count <= num_chunks * 65536):
        raise RuntimeError("object registry header failed revalidation")
    chunk_addresses = struct.unpack("<" + "Q" * num_chunks, adapter.read(chunks, num_chunks * 8))
    if not all(0x10000 <= address < 0x800000000000 for address in chunk_addresses):
        raise RuntimeError("object registry contains an invalid chunk pointer")

    diagnostics = {
        "registry_objects_scanned": 0,
        "engine_objects": 0,
        "valid_viewports": 0,
        "world_objects": 0,
        "native_roots_status_counts": {},
        "native_roots_status_legend": {
            "0": "OK",
            "1": "ARGUMENT",
            "2": "UNREADABLE",
            "3": "LIMIT",
            "4": "CORRUPT",
            "5": "CHANGED",
            "6": "NOT_FOUND",
            "7": "CAPACITY",
        },
        "rejections": {},
        "examples": [],
    }

    def reject(stage, reason):
        key = f"{stage}:{reason}"
        diagnostics["rejections"][key] = diagnostics["rejections"].get(key, 0) + 1

    def record_exception(stage, error):
        reject(stage, type(error).__name__)
        if len(diagnostics["examples"]) < 6:
            diagnostics["examples"].append({
                "stage": stage,
                "error_type": type(error).__name__,
                "message": str(error)[:160],
            })

    class_names = {}
    for chunk_index, chunk in enumerate(chunk_addresses):
        num = min(65536, count - chunk_index * 65536)
        if num <= 0:
            break
        entries = b"".join(
            adapter.read(chunk + offset, min(1024 * 1024, num * 24 - offset))
            for offset in range(0, num * 24, 1024 * 1024)
        )
        for index in range(num):
            obj = struct.unpack_from("<Q", entries, index * 24)[0]
            if not obj:
                continue
            diagnostics["registry_objects_scanned"] += 1
            try:
                header = adapter.read(obj, 40)
                klass = struct.unpack_from("<Q", header, 16)[0]
                if klass not in class_names:
                    class_name = adapter.object_name(klass)
                    class_names[klass] = class_name if class_name in ("Engine", "GameEngine", "HTGameEngine") else ""
                if not class_names[klass]:
                    continue
                diagnostics["engine_objects"] += 1

                status, viewport_field = adapter.field(adapter.dll, obj, "GameViewport")
                if status:
                    reject("GameViewport", f"property_status_{status}")
                    continue
                if viewport_field.size != 8:
                    reject("GameViewport", "unexpected_size")
                    continue
                viewport = struct.unpack("<Q", adapter.read(obj + viewport_field.offset, 8))[0]
                if not 0x10000 <= viewport < 0x800000000000:
                    reject("GameViewport", "invalid_pointer")
                    continue

                world_status, world_field = adapter.field(adapter.dll, viewport, "World")
                if world_status == 0 and world_field.size == 8:
                    world = struct.unpack("<Q", adapter.read(viewport + world_field.offset, 8))[0]
                    world_source = "reflected_property"
                else:
                    reject(
                        "Viewport.World",
                        f"fallback_after_property_status_{world_status}"
                        if world_status else "fallback_after_unexpected_size",
                    )
                    # This fallback is already used by the independent inventory
                    # reader for builds where the viewport property is not exposed
                    # through the runtime reflection chain.
                    world = struct.unpack("<Q", adapter.read(viewport + 0x78, 8))[0]
                    world_source = "validated_reader_fallback_0x78"
                if adapter.class_name(world) != "World":
                    reject("Viewport.World", "class_not_world")
                    continue
                diagnostics["valid_viewports"] += 1
                diagnostics["world_objects"] += 1

                # Reuse the independent reader's bounded root resolver. It checks
                # the World → GameInstance → LocalPlayer → PlayerState links twice
                # and returns a status code instead of relying on an all-reflection
                # chain that failed to resolve this live session.
                roots = Roots()
                roots_status = adapter.dll.keke_inventory_roots(
                    adapter.read_cb, adapter.name_cb, adapter.read_user,
                    world, C.byref(roots),
                )
                status_key = str(int(roots_status))
                diagnostics["native_roots_status_counts"][status_key] = (
                    diagnostics["native_roots_status_counts"].get(status_key, 0) + 1
                )
                if roots_status == 0 and roots.player_state:
                    roots_again = Roots()
                    status_again = adapter.dll.keke_inventory_roots(
                        adapter.read_cb, adapter.name_cb, adapter.read_user,
                        world, C.byref(roots_again),
                    )
                    if status_again == 0 and roots_again.player_state == roots.player_state:
                        return {
                            "player_state": roots.player_state,
                            "player_state_class": adapter.class_name(roots.player_state),
                            "resolution_method": "independent_reader_roots",
                            "world_source": world_source,
                        }
                    reject("stable_roots", f"second_status_{int(status_again)}")
                else:
                    reject("independent_reader_roots", f"status_{int(roots_status)}")

                # Keep the property-based route as a fallback for a build where
                # the inventory reader's fixed root layout no longer applies.
                game_instance, _ = reflected_object(adapter, world, "OwningGameInstance")
                local_player, local_players_header, _ = first_array_object(adapter, game_instance, "LocalPlayers")
                controller, _ = reflected_object(adapter, local_player, "PlayerController")
                player_state, _ = reflected_object(adapter, controller, "PlayerState")

                if world_source == "reflected_property" and reflected_object(adapter, viewport, "World")[0] != world:
                    raise RuntimeError("GameViewport.World changed during read")
                if reflected_object(adapter, world, "OwningGameInstance")[0] != game_instance:
                    raise RuntimeError("World.OwningGameInstance changed during read")
                local_player_again, header_again, _ = first_array_object(adapter, game_instance, "LocalPlayers")
                if local_player_again != local_player or header_again != local_players_header:
                    raise RuntimeError("GameInstance.LocalPlayers changed during read")
                if reflected_object(adapter, local_player, "PlayerController")[0] != controller:
                    raise RuntimeError("LocalPlayer.PlayerController changed during read")
                if reflected_object(adapter, controller, "PlayerState")[0] != player_state:
                    raise RuntimeError("PlayerController.PlayerState changed during read")

                return {
                    "player_state": player_state,
                    "player_state_class": adapter.class_name(player_state),
                    "resolution_method": "reflected_properties",
                    "world_source": world_source,
                }
            except (OSError, ValueError, RuntimeError, UnicodeError) as error:
                record_exception("chain_resolution", error)
                continue
    raise PlayerStateResolutionError(diagnostics)


class PlayerStateResolutionError(RuntimeError):
    def __init__(self, diagnostics):
        self.diagnostics = diagnostics
        super().__init__("could not resolve one stable World → LocalPlayer → PlayerState chain")


def inspect_pid(pid, expected_uid):
    registry = discover_registry(pid, allow_unpinned_version=True)
    if registry.get("status") != "registry_candidates_verified":
        raise RuntimeError("object registry discovery failed")
    registry_report = {"processes": [registry]}

    names = discover_names(pid, registry_report, allow_unpinned_version=True)
    if names.get("status") != "name_pool_verified":
        raise RuntimeError("name-pool discovery failed")

    pool = next(row for row in names["candidates"] if row.get("verified"))
    with ProcessReader(pid) as reader:
        if reader.identity() != registry["identity"]:
            raise RuntimeError("game process changed during the probe")
        adapter = Adapter(reader, pool)
        roots = resolve_player_state(adapter, registry)
        player_state = roots["player_state"]
        rows = [read_candidate(adapter, player_state, name, label, expected_uid)
                for name, label in CANDIDATE_FIELDS]
        return {
            "pid": pid,
            "read_only": True,
            "uses_author_components": False,
            "game_sha256": registry.get("game_sha256"),
            "version_policy": registry.get("version_policy"),
            "player_state_class": roots["player_state_class"],
            "player_state_resolution_method": roots["resolution_method"],
            "world_source": roots["world_source"],
            "candidate_fields": rows,
            "uid_match": next((r["field"] for r in rows if r.get("matches_visible_uid")), None),
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-visible-uid", help="optional UID visible in the game UI, used only for local comparison")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.expected_visible_uid and not re.fullmatch(r"\d{8,20}", args.expected_visible_uid):
        parser.error("--expected-visible-uid must be 8–20 decimal digits")

    results = []
    for pid in find_process_ids_by_image_name("HTGame.exe"):
        try:
            results.append({"status": "ok", **inspect_pid(pid, args.expected_visible_uid)})
        except Exception as error:
            row = {"pid": pid, "status": "failed", "error": str(error)}
            if isinstance(error, PlayerStateResolutionError):
                row["resolution_diagnostics"] = error.diagnostics
            results.append(row)

    report = {
        "schema": "keke_account_uid_probe_v1",
        "read_only": True,
        "expected_uid_supplied": args.expected_visible_uid is not None,
        "processes": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"Report written to: {args.output.resolve()}")
    return 0 if any(row.get("status") == "ok" for row in results) else 2


if __name__ == "__main__":
    sys.exit(main())
