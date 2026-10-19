"""Validate OCR-plan to upstream assembly projection without launching game input."""
from __future__ import annotations

from pathlib import Path
import sys
import threading
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'desktop'))

from inventory.ui_assembly import SOLVER_SHAPES, UIAssemblyService
from vision.upstream.domain.drive_layout import SHAPE_FOOTPRINTS
from vision.upstream.features.drive_assembly.assembly_session import build_single_role_assembly_plan


def main() -> None:
    assert set(SOLVER_SHAPES.values()) == set(SHAPE_FOOTPRINTS)
    active = {(1, 1), (1, 2), (1, 3), (2, 1), (2, 2), (2, 3)}
    tape_record = {
        'instance_id': 'ocr:fixture:tape', 'name': '森林萤火之心', 'rarity_candidate': 'gold',
        'main_attributes': [{'name': '暴击率', 'value': 0.1}],
        'sub_attributes': {'生命值百分比': 10, '攻击力百分比': 10, '防御力百分比': 10, '生命值': 30},
    }
    drive_a = {
        'instance_id': 'ocr:fixture:drive-a', 'name': '驱动甲', 'rarity_candidate': 'gold',
        'sub_attributes': {'生命值百分比': 10, '攻击力百分比': 10, '防御力百分比': 10, '生命值': 30},
    }
    drive_b = {
        'instance_id': 'ocr:fixture:drive-b', 'name': '驱动乙', 'rarity_candidate': 'purple',
        'sub_attributes': {'生命值百分比': 10, '攻击力百分比': 10, '防御力百分比': 10, '生命值': 30},
    }
    tape = UIAssemblyService._tape_for_assembly(tape_record)
    state = UIAssemblyService._build_equipped_state('测试角色', active, tape, [
        {'record': drive_a, 'shape': 'H_2', 'row': 1, 'column': 1},
        {'record': drive_b, 'shape': 'V_2', 'row': 1, 'column': 3},
    ])
    role = state['测试角色']
    assert role['equipped_tape']['uid'] == tape_record['instance_id']
    assert {row['uid'] for row in role['equipped_drives']} == {drive_a['instance_id'], drive_b['instance_id']}
    assert len(role['equipped_drives']) == 2
    plan = build_single_role_assembly_plan(state, '测试角色', screen_size=(1920, 1080), content_rect=(0, 0, 1920, 1080))
    assert plan['available'] and plan['tape_count'] == 1 and plan['drive_count'] == 2
    try:
        UIAssemblyService._build_equipped_state('测试角色', active, tape, [
            {'record': drive_a, 'shape': 'H_2', 'row': 1, 'column': 1},
            {'record': drive_b, 'shape': 'H_2', 'row': 1, 'column': 1},
        ])
    except ValueError as error:
        assert '重叠' in str(error)
    else:
        raise AssertionError('Overlapping solver placements must be rejected')

    class FakeInventory:
        def __init__(self):
            self.lock = threading.RLock()
            self.vision = None
            self.accounts = type('Accounts', (), {'get': lambda _self, _account: {'uid': '123456789012'}})()
            self.records = [
                {**tape_record, 'category': 'tape'},
                {**drive_a, 'category': 'drive', 'shape': 'H_2'},
                {**drive_b, 'category': 'drive', 'shape': 'V_2'},
            ]

        @staticmethod
        def native_busy():
            return False

        def view(self, account, source):
            return {
                'sources': [{'id': source}], 'ocr_batch': {'account_uid': '123456789012'},
                'inventory': {'equipment': {'records': self.records}},
            }

    service = UIAssemblyService(FakeInventory())
    board = [[row, column] for row, column in sorted(active)]
    request = {
        'account': '测试账号', 'source': 'ocr:fixture', 'role_name': '测试角色', 'role_id': 'fixture-role',
        'board': board, 'core': tape_record['instance_id'],
        'modules': [
            {'id': drive_a['instance_id'], 'row': 1, 'column': 1, 'shape_id': 'cell2_style1_1'},
            {'id': drive_b['instance_id'], 'row': 1, 'column': 3, 'shape_id': 'cell2_style2_1'},
        ],
    }
    for invalid in (
        {**request, 'source_saved_at':'stale-fixture-time'},
        {**request, 'source': 'unsupported'},
        {**request, 'source': 'ocr:fixture', 'core': 'not-in-snapshot'},
        {**request, 'source': 'ocr:fixture', 'modules': [dict(request['modules'][0], shape_id='cell2_style2_1')]},
    ):
        try:
            service.start(**invalid)
        except ValueError:
            pass
        else:
            raise AssertionError('Invalid assembly plan must be rejected before starting a job')
    assert service.thread is None
    native_stats=[{'name':'攻击力','value':.1,'is_percent':True},
                  {'name':'生命值','value':30},{'name':'暴击率','value':.03,'is_percent':True},
                  {'name':'暴击伤害','value':.06,'is_percent':True}]
    service.inventory.records=[{**row,'rarity_candidate':None,'rarity':'Orange',
        'main_attributes':[{'name':'攻击力','value':.1,'is_percent':True}],
        'sub_attributes':native_stats} for row in service.inventory.records]
    with patch('inventory.ui_assembly.threading.Thread') as thread:
        service.start(**{**request,'source':'native'})
        thread.return_value.start.assert_called_once()
        native_state=thread.call_args.kwargs['args'][1]
    assert native_state['测试角色']['equipped_drives'][0]['quality']=='gold'
    stats=native_state['测试角色']['equipped_drives'][0]['sub_stats']
    assert sorted(stats.values())==[3,6,10,30],stats
    print('Offline DLL/OCR assembly passed: shapes, instance mapping, native percent/quality conversion, overlap rejection; no game input sent.')


if __name__ == '__main__':
    main()
