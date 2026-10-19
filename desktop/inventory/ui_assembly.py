"""Stepwise game-interface assembly from one selected saved inventory snapshot."""

from __future__ import annotations

import ctypes
import json
import os
from pathlib import Path
import threading
import time
import uuid

from inventory.accounts import validate_uid
from vision.upstream.domain.drive_layout import SHAPE_FOOTPRINTS, matrix_groups_in_scan_order
from vision.upstream.features.drive_assembly.assembly_session import execute_selected_role_from_current_game_page
from vision.upstream.features.drive_assembly.executor import AssemblyExecutionStopped
from vision.upstream.features.drive_assembly.input_backends import PyAutoGuiMouseBackend
from vision.upstream.integrations.operation_guard import bind_execution_guard
from vision.upstream.services.sqlite_allocation_inventory import legacy_shape_id


SOLVER_SHAPES = {
    "cell2_style1_1": "H_2", "cell2_style2_1": "V_2",
    "cell3_style1_1": "H_3", "cell3_style2_1": "V_3",
    "cell3_style3_1": "L_3_TL", "cell3_style4_1": "L_3_TR",
    "cell3_style5_1": "L_3_BL", "cell3_style6_1": "L_3_BR",
    "cell4_style1_1": "H_4", "cell4_style2_1": "V_4",
    "cell4_style5_1": "Trap_4_H", "cell4_style6_1": "Trap_4_V",
}


class UIAssemblyService:
    """Run one cancellable UI automation job, validating every selected item."""

    def __init__(self, inventory):
        self.inventory = inventory
        self.lock = threading.RLock()
        self.stop = threading.Event()
        self.thread = None
        self.job = {"running": False, "message": "尚未开始游戏内装配", "completed": 0, "total": 0}

    def status(self):
        with self.lock:
            return json.loads(json.dumps(self.job, ensure_ascii=False))

    def start(self, account, source, role_name, role_id, board, core, modules, role_alias=None, source_saved_at=None):
        account = self._text(account, "账号", 80)
        if not isinstance(source, str) or (source != "native" and not source.startswith("ocr:")) or len(source) > 96:
            raise ValueError("游戏内逐步装配需要选择一个已保存的装备快照")
        role_name = self._text(role_name, "角色名称", 40)
        role_id = self._text(role_id, "角色编号", 48)
        role_alias = self._text(role_alias or "", "游戏内角色名称", 40, allow_empty=True)
        active = self._board(board)
        if not isinstance(modules, list) or not 1 <= len(modules) <= 10:
            raise ValueError("驱动方案数量无效")
        if not isinstance(core, str) or len(core) > 160:
            raise ValueError("空幕实例无效")

        with self.inventory.lock, self.lock:
            if self.inventory.native_busy():
                raise ValueError("请等待原生读取或装备操作完成")
            if self.inventory.vision and self.inventory.vision.job.get("running"):
                raise ValueError("请等待截图采集或识别完成")
            if self.job.get("running"):
                raise ValueError("已有游戏内逐步装配任务正在运行")
            profile = self.inventory.accounts.get(account)
            if profile is None:
                raise ValueError("所选账号资料不存在，请刷新账号列表")
            view = self.inventory.view(account, source)
            if source_saved_at is not None and source_saved_at != view.get('inventory',{}).get('equipment',{}).get('saved_at'):
                raise ValueError('方案对应的装备快照已更新，请重新计算并保存后装配')
            selected = next((row for row in view.get("sources", []) if row.get("id") == source), None)
            if not selected:
                raise ValueError("所选历史装备快照已不存在，请重新选择")
            self._validate_uid_binding(view.get("ocr_batch", {}).get("account_uid") or view.get("account_uid"), profile.get("uid"))
            item_records = view.get("inventory", {}).get("equipment", {}).get("records", [])
            item_by_id = {row.get("instance_id"): row for row in item_records if isinstance(row, dict)}
            authoritative_core = item_by_id.get(core)
            if not authoritative_core or authoritative_core.get("category") != "tape":
                raise ValueError("所选空幕不在当前装备快照中，请重新计算方案")
            if authoritative_core.get('usable_for_calculation') is False:raise ValueError('空幕属性未通过图鉴核对，请修正后重算')
            if source == "native":authoritative_core = self._offline_record(authoritative_core)
            selected_modules = []
            seen = {core}
            for row in modules:
                if not isinstance(row, dict):
                    raise ValueError("驱动方案格式无效")
                item_id = row.get("id")
                if not isinstance(item_id, str) or item_id in seen:
                    raise ValueError("驱动实例缺失或重复")
                seen.add(item_id)
                record = item_by_id.get(item_id)
                if not record or record.get("category") != "drive":
                    raise ValueError("驱动不在当前装备快照中，请重新计算方案")
                if record.get('usable_for_calculation') is False:raise ValueError('驱动属性未通过图鉴核对，请修正后重算')
                if source == "native":record = self._offline_record(record)
                solver_shape = row.get("shape_id")
                expected_shape = SOLVER_SHAPES.get(solver_shape)
                source_shape = legacy_shape_id(record.get("shape") or record.get("parser_result", {}).get("shape_id"))
                if not expected_shape or expected_shape != source_shape:
                    raise ValueError("驱动形状与所选快照不一致，请重新计算方案")
                if type(row.get("row")) is not int or type(row.get("column")) is not int:
                    raise ValueError("驱动盘面坐标无效")
                selected_modules.append({"record": record, "shape": source_shape,
                                         "row": row["row"], "column": row["column"]})
            selected_tape = self._tape_for_assembly(authoritative_core)
            if not selected_tape["set_name"] or not selected_tape["main_stats"] or not selected_tape["quality"]:
                raise ValueError("装备快照缺少空幕套装或主属性，无法可靠筛选；请补充截图数据后重算")
            for module in selected_modules:
                stats = module["record"].get("sub_attributes") or module["record"].get("parser_result", {}).get("sub_stats")
                if not self._quality(module["record"]):
                    raise ValueError("装备快照缺少驱动品质，无法可靠筛选；请补充截图数据后重算")
                if not isinstance(stats, (dict, list)) or len(stats) < 4:
                    raise ValueError("装备快照中的驱动副属性不完整，无法可靠筛选；请补充截图数据后重算")

            state = self._build_equipped_state(role_name, active, selected_tape, selected_modules)
            run_id = uuid.uuid4().hex
            self.stop.clear()
            self.job = {"id": run_id, "running": True,
                        "message": "3 秒后开始识别游戏角色并逐步装配，请切回游戏角色详情页",
                        "completed": 0, "total": 0,
                        "account": account, "source": source, "role_id": role_id,
                        "role_name": role_name, "started_at": time.time(), "result": None}
            self.thread = threading.Thread(
                target=self._run,
                args=(run_id, state, role_name, role_alias),
                daemon=True,
                name="KekeUIAssembly",
            )
            self.thread.start()
            return self.status()

    def cancel(self):
        with self.lock:
            if not self.job.get("running"):
                return self.status()
            self.stop.set()
            self.job["message"] = "正在停止后续游戏输入…"
            return self.status()

    @staticmethod
    def _text(value, label, limit, allow_empty=False):
        if not isinstance(value, str) or len(value) > limit or (not allow_empty and not value.strip()):
            raise ValueError(f"{label}无效")
        value = value.strip()
        if not allow_empty and not value:
            raise ValueError(f"{label}无效")
        return value

    @staticmethod
    def _board(value):
        if not isinstance(value, list) or not 4 <= len(value) <= 24:
            raise ValueError("角色终端盘面无效")
        cells = set()
        for row in value:
            if not isinstance(row, list) or len(row) != 2 or any(type(part) is not int for part in row):
                raise ValueError("角色终端盘面坐标无效")
            r, c = row
            if not 1 <= r <= 5 or not 1 <= c <= 5 or (r, c) in cells:
                raise ValueError("角色终端盘面坐标越界或重复")
            cells.add((r, c))
        return cells

    @staticmethod
    def _validate_uid_binding(batch_uid, profile_uid):
        if batch_uid:
            validate_uid(batch_uid)
            if profile_uid and profile_uid != batch_uid:
                raise ValueError("所选 装备快照 UID 与账号资料绑定不一致")

    @staticmethod
    def _offline_record(record):
        """Translate saved DLL fields for UI matching; never call the DLL."""
        from vision.upstream.domain.stat_catalog import StatCatalog
        from vision.upstream.integrations.bundled_resources import bundled_config_dir
        catalog = StatCatalog.from_config_dir(bundled_config_dir())
        def stats(values):
            if not isinstance(values, list):return values
            result = {}
            for row in values:
                if not isinstance(row, dict):continue
                name = row.get("name") or (row.get("names") or {}).get("zh_cn")
                percent = row.get("is_percent") is True or row.get("percent") is True
                value = row.get("value")
                if not name or not isinstance(value, (int, float)):continue
                name = catalog.normalize_stat_name(name, is_percent=percent, cutoff=1.0) or name
                result[name] = value * 100 if percent else value
            return result
        return {**record, "main_attributes": stats(record.get("main_attributes")),
                "sub_attributes": stats(record.get("sub_attributes"))}

    @staticmethod
    def _tape_for_assembly(record):
        parser = record.get("parser_result") if isinstance(record.get("parser_result"), dict) else {}
        name = str(record.get("name") or parser.get("set_name") or "").strip()
        raw_main = record.get("main_attributes") or record.get("inferred_main_attributes") or parser.get("main_stats")
        if isinstance(raw_main, dict):
            main = str(next(iter(raw_main), "")).strip()
        elif isinstance(raw_main, list):
            first = raw_main[0] if raw_main else ""
            main = str(first.get("name") or first.get("names", {}).get("zh_cn") or "") if isinstance(first, dict) else str(first)
        else:
            main = str(raw_main or "").strip()
        subs = record.get("sub_attributes") or parser.get("sub_stats") or {}
        return {"uid": record["instance_id"], "set_name": name, "main_stats": main,
                "sub_stats": subs, "quality": UIAssemblyService._quality(record)}

    @staticmethod
    def _quality(record):
        value = str(record.get("rarity_candidate") or record.get("rarity") or
                    (record.get("parser_result") or {}).get("quality") or "").strip().lower()
        if "gold" in value or "orange" in value or "金" in value or "橙" in value:
            return "gold"
        if "purple" in value or "紫" in value:
            return "purple"
        if "blue" in value or "蓝" in value:
            return "blue"
        return ""

    @classmethod
    def _build_equipped_state(cls, role_name, active, tape, modules):
        board = [["0" for _ in range(5)] for _ in range(5)]
        drive_by_cells = {}
        for module in modules:
            shape = module["shape"]
            footprint = SHAPE_FOOTPRINTS[shape]
            cells = [(module["row"] + dr, module["column"] + dc) for dr, dc in footprint]
            if any(cell not in active for cell in cells):
                raise ValueError("驱动方案超出角色盘面，请重新计算方案")
            if any(board[row - 1][column - 1] != "0" for row, column in cells):
                raise ValueError("驱动方案在角色盘面上重叠，请重新计算方案")
            for cell in cells:
                board[cell[0] - 1][cell[1] - 1] = shape
            cell_key = frozenset(cells)
            if cell_key in drive_by_cells:
                raise ValueError("驱动方案包含重复盘面位置")
            record = module["record"]
            sub_stats = record.get("sub_attributes") or (record.get("parser_result") or {}).get("sub_stats") or {}
            drive_by_cells[cell_key] = {
                "uid": record["instance_id"], "drive_type": shape, "shape_id": shape,
                "quality": cls._quality(record), "sub_stats": sub_stats,
                "set_name": str(record.get("name") or ""),
            }
        ordered = []
        for matrix_name, cells in matrix_groups_in_scan_order(board):
            if matrix_name == "0":
                continue
            block = drive_by_cells.pop(frozenset(cells), None)
            if block is None:
                raise ValueError("驱动盘面与装备实例对应失败，请重新计算方案")
            ordered.append(block)
        if drive_by_cells:
            raise ValueError("驱动盘面未能完整生成，请重新计算方案")
        return {role_name: {"blueprint_layout": board, "equipped_drives": ordered,
                            "equipped_tape": tape}}

    def _run(self, run_id, state, role_name, role_alias):
        backend = None
        try:
            base = self.inventory.directory / "ui-assembly"
            template_root = base / "templates"
            record_root = base / "runs"
            template_root.mkdir(parents=True, exist_ok=True)
            record_root.mkdir(parents=True, exist_ok=True)

            def is_current():
                with self.lock:
                    return self.job.get("id") == run_id

            def guard(capability):
                if capability != "interface_input":
                    raise PermissionError("仅允许进行游戏内逐步装配输入")
                if self.stop.is_set():
                    raise AssemblyExecutionStopped("assembly execution stopped")
                if os.name != "nt":
                    raise ValueError("游戏内逐步装配仅支持 Windows")
                user32 = ctypes.windll.user32
                kernel32 = ctypes.windll.kernel32
                hwnd = user32.GetForegroundWindow()
                if not hwnd:
                    raise ValueError("未检测到前台游戏窗口")
                pid = ctypes.c_ulong()
                user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid))
                kernel32.OpenProcess.restype = ctypes.c_void_p
                handle = kernel32.OpenProcess(0x1000, False, pid.value)
                if not handle:
                    raise ValueError("无法确认前台游戏进程")
                try:
                    buffer = ctypes.create_unicode_buffer(32768)
                    size = ctypes.c_ulong(len(buffer))
                    if not kernel32.QueryFullProcessImageNameW(ctypes.c_void_p(handle), 0, buffer,
                                                               ctypes.byref(size)):
                        raise ValueError("无法确认前台游戏进程")
                    if Path(buffer.value).name.lower() != "htgame.exe":
                        raise ValueError("请先切回异环游戏窗口；当前前台不是游戏")
                    from vision.windows_access import require_matching_input_privilege
                    require_matching_input_privilege(ctypes.c_void_p(handle))
                finally:
                    kernel32.CloseHandle(ctypes.c_void_p(handle))
                with self.lock:
                    if not is_current():
                        raise AssemblyExecutionStopped("assembly execution stopped")
                    identity = (int(hwnd), int(pid.value))
                    expected = self.job.get("window_identity")
                    if expected is not None and tuple(expected) != identity:
                        raise ValueError("前台游戏窗口已变化，装配已停止")
                    self.job["window_identity"] = identity

            operation_guard = bind_execution_guard(guard, should_stop=self.stop.is_set,
                                                   generation=lambda: run_id if is_current() else None)
            backend = PyAutoGuiMouseBackend(operation_guard=operation_guard)

            def progress(action, executed_role_name):
                with self.lock:
                    if self.job.get("id") != run_id:
                        return
                    self.job["completed"] = int(self.job.get("completed", 0)) + 1
                    action_name = str(action.get("name") or "游戏输入")
                    role = executed_role_name or role_name
                    self.job["message"] = f"逐步装配中：{role} · {action_name}"

            with self.lock:
                if self.job.get("id") == run_id:
                    self.job["message"] = "正在 OCR 识别游戏角色列表…"
            report = execute_selected_role_from_current_game_page(
                state, role_name, backend=backend, template_dir=str(template_root),
                startup_delay_seconds=3.0, role_name_aliases={role_name: role_alias} if role_alias else None,
                record_root=record_root, should_stop=self.stop.is_set, on_action_executed=progress,
            )
            result = {"executed_actions": report.executed_actions,
                      "navigation_actions": report.navigation_actions,
                      "skipped_roles": report.skipped_roles,
                      "verification_failures": report.verification_failures,
                      "repair_attempts": report.repair_attempts,
                      "roles": [{"role_name": row.role_name, "executed_actions": row.executed_actions,
                                 "skipped_actions": len(row.skipped_actions)} for row in report.role_reports]}
            if report.skipped_roles or role_name in report.missing_roles:
                message = "角色未能匹配，未完成自动装配；请确认游戏内角色名称与方案一致"
            elif report.verification_failures:
                message = "游戏内装配已执行，但画面复核发现未确认的驱动，请检查游戏盘面"
            elif not report.role_reports or not any(row.executed_actions for row in report.role_reports):
                message = "没有确认到有效装配动作；请核对角色名称、装备快照与游戏页面"
            else:
                message = "游戏内逐步装配完成并通过盘面画面复核"
                if report.repair_attempts:message+=f"（复检补装 {len(report.repair_attempts)} 轮）"
            self._finish(run_id, message, result=result, error=None)
        except (AssemblyExecutionStopped, KeyboardInterrupt) as error:
            self._finish(run_id, "已停止后续游戏输入", result=None, error=str(error) or "已取消")
        except Exception as error:
            self._finish(run_id, str(error)[:300], result=None, error=str(error)[:1000])
        finally:
            if backend is not None:
                try:
                    backend.close()
                except Exception:
                    pass

    def _finish(self, run_id, message, result, error):
        with self.lock:
            if self.job.get("id") != run_id:
                return
            self.job.update({"running": False, "message": message, "result": result, "error": error,
                             "finished_at": time.time()})
