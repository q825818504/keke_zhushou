"""Read the logged-in game's public account UID using the bounded local probe."""
from .probe import inspect_pid


def read_uid(pid):
    if type(pid) is not int or pid <= 0:
        raise ValueError("游戏进程无效")
    try:
        report = inspect_pid(pid, expected_uid=None)
    except OSError as error:
        if getattr(error, "winerror", None) == 5:
            raise PermissionError(
                "无法读取游戏进程 UID；请以与游戏相同的 Windows 权限启动可可助手。"
            ) from None
        raise RuntimeError("无法从当前游戏进程确认 UID；请确认游戏已登录并重试。") from None
    except Exception:
        raise RuntimeError(
            "无法从当前游戏会话确认 UID；请确认游戏已登录，且客户端版本受支持。"
        ) from None

    rows = report.get("candidate_fields")
    field = next((row for row in rows or [] if row.get("field") == "m_nRoleId"), None)
    value = field.get("value") if isinstance(field, dict) else None
    if (not isinstance(field, dict) or field.get("property_type") != "UInt64Property"
            or field.get("size") != 8 or field.get("decode_status") != "ok"
            or type(value) is not int or not 0 < value <= 18446744073709551615):
        raise RuntimeError(
            "当前游戏没有提供经过类型校验的 UID；本次读取已停止，请等待适配更新。"
        )
    return str(value)
