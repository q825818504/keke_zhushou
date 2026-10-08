from typing import Any
class AllocationInventoryProjectionError(RuntimeError):
    """稳定背包包含当前求解器尚不能识别的数据。"""

_SHAPE_IDS = {
    "hen2": "H_2",
    "hen3": "H_3",
    "hen4": "H_4",
    # 旧 OCR/模板曾把 Hen 误转写为 Heng；统一投影为既有 H_* 名称。
    "heng2": "H_2",
    "heng3": "H_3",
    "heng4": "H_4",
    "shu2": "V_2",
    "shu3": "V_3",
    "shu4": "V_4",
    "z3": "Trap_4_H",
    "z4": "Trap_4_V",
    "zhijiao1": "L_3_BL",
    "zhijiao2": "L_3_TL",
    "zhijiao3": "L_3_TR",
    "zhijiao4": "L_3_BR",
}

def legacy_shape_id(value: Any) -> str:
    """Map an official geometry ID to the existing puzzle-solver shape ID."""

    geometry = str(value or "").strip().removeprefix("EquipmentGeometry_")
    if geometry in _SHAPE_IDS.values():
        return geometry
    shape_id = _SHAPE_IDS.get(geometry.casefold())
    if shape_id is None:
        raise AllocationInventoryProjectionError(f"未知官方驱动形状：{value!r}")
    return shape_id