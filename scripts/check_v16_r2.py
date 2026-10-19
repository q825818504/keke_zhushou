"""Terminal scan, catalog validation and bounded repair regressions; no game input."""
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock,patch
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'desktop'))
from vision.mouse_scanner import VerifiedMouseScanner,ScrollThumb
from vision.upstream.integrations.vision.mouse_inventory_scan import MouseInventoryLayout,MouseScanSlot
from vision.upstream.integrations.vision.mouse_scan_capture import MouseCapturedFrame
from vision.upstream.scanner.window_capture import WindowRect
from vision.stat_validation import validate_record
from inventory.vision_source import vision_domain
from vision.upstream.features.drive_assembly.assembly_session import verify_blueprint_against_screenshot
from vision.upstream.features.drive_assembly.executor import execute_role_traversal_assembly_plan,AssemblyExecutionStopped


class FixTests(unittest.TestCase):
    def scanner(self):
        scanner=VerifiedMouseScanner.__new__(VerifiedMouseScanner)
        scanner.expected_count=1425;scanner.layout=MouseInventoryLayout();scanner._stopped=False
        scanner.scroll_command_count=0;scanner.scroll_amounts=[];scanner._sleep=lambda seconds:None
        scanner._input=Mock()
        frame=MouseCapturedFrame(np.zeros((900,1600,3),dtype=np.uint8),WindowRect(0,0,1600,900),1)
        scanner._capture_frame=lambda:frame
        return scanner,frame

    def test_near_bottom_keeps_tracking_normal_page(self):
        scanner,frame=self.scanner()
        with patch('vision.mouse_scanner.detect_scroll_thumb',return_value=ScrollThumb(1067,149,771,750,769)),patch(
            'vision.mouse_scanner.detect_selected_card_center_y',side_effect=[390,202,202]):
            _,_,_,bottom=scanner._scroll_to_next_page(frame,MouseScanSlot(28,0,3,6))
        self.assertFalse(bottom);self.assertEqual(scanner._input.scroll.call_count,2)

    def test_terminal_page_requires_stable_bottom_and_calibrates_anchor(self):
        scanner,frame=self.scanner()
        with patch('vision.mouse_scanner.detect_scroll_thumb',return_value=ScrollThumb(1067,149,771,750,769)),patch(
            'vision.mouse_scanner.detect_selected_card_center_y',side_effect=[600,500,400,370,370,370,370]):
            _,row,offset,bottom=scanner._scroll_to_next_page(frame,MouseScanSlot(1414,66,3,6))
        self.assertTrue(bottom);self.assertEqual(row,1);self.assertEqual(scanner._input.scroll.call_count,7)
        expected=scanner.layout.cell_center(1,6,1600,900)[1]
        self.assertEqual(offset,370-expected)
        slots=scanner.layout.page_slots(1425)[-1]
        self.assertEqual(len(slots),11);self.assertEqual([(s.row,s.column) for s in slots][-1],(3,3))

    def test_catalog_repairs_only_unambiguous_decimal_loss(self):
        tape={'category':'tape','sub_attributes':{'暴击伤害%':2000,'防御力%':17.5}}
        corrected=validate_record(tape)
        self.assertEqual(corrected['sub_attributes']['暴击伤害%'],20)
        self.assertEqual(tape['sub_attributes']['暴击伤害%'],2000)
        self.assertTrue(corrected['usable_for_calculation'])
        drive=validate_record({'category':'drive','cell_count':3,'sub_attributes':{'攻击力%':375,'暴击伤害%':6}})
        self.assertEqual(drive['sub_attributes']['攻击力%'],3.75)
        self.assertTrue(drive['usable_for_calculation'])
        invalid={'category':'drive','cell_count':3,'sub_attributes':{'攻击力%':1234}}
        result=vision_domain({'id':'fixture','account':'fixture','mode':'mouse','records':[invalid]})
        self.assertFalse(result['records'][0]['usable_for_calculation'])
        self.assertEqual(invalid['sub_attributes']['攻击力%'],1234)
        self.assertTrue(validate_record({'category':'tape','sub_attributes':{'防御力%':14}})['usable_for_calculation'])

    def test_verification_checks_every_cell_not_centroid_or_dark_background(self):
        image=np.full((150,150,3),45,dtype=np.uint8)
        plan={'drive_blocks':[{'block_id':1,'pixel_position':(50,35),'board_origin':(20,20),
                              'cell_size':(30,30),'cells':[(1,1),(1,2)]}]}
        image[30:41,30:41]=180
        report=verify_blueprint_against_screenshot(image,SimpleNamespace(left=0,top=0),plan)
        self.assertFalse(report['ok']);self.assertIn((65,35),report['missing_blocks'][0]['missing_cells'])
        image[30:41,60:71]=180
        self.assertTrue(verify_blueprint_against_screenshot(image,SimpleNamespace(left=0,top=0),plan)['ok'])

    def assembly(self,verifier,stop=None,callback=None):
        calls=[]
        backend=SimpleNamespace(click=lambda position:calls.append(position))
        plan={'role_name':'fixture','available':True,'actions':[
            {'name':'prepare_assembly_page','sequence':[{'name':'unload_existing_drives','position':(1,1)}]},
            {'name':'install_drives','sequence':[{'name':'drive_tab','position':(2,2)},
                {'name':'install_drive_block','sequence_index':0},{'name':'install_drive_block','sequence_index':1}],
             'install_plans':[{'block_id':1,'install_sequence':[{'name':'block1','position':(3,3)}]},
                              {'block_id':2,'install_sequence':[{'name':'block2','position':(4,4)}]}]}]}
        traversal={'plans':[{'role_name':'fixture','action_sequence':[{'name':'assemble_current_role_from_blueprint','role_name':'fixture'}]}]}
        report=execute_role_traversal_assembly_plan(traversal,{'role_plans':[plan]},backend=backend,
            pause_seconds=0,role_verifier=verifier,should_stop=stop,on_action_executed=callback)
        return report,calls

    def test_only_missing_block_is_repaired_then_reverified(self):
        verifier=Mock(side_effect=[{'ok':False,'missing_blocks':[{'block_id':2}]},{'ok':True,'missing_blocks':[]}])
        report,calls=self.assembly(verifier)
        self.assertEqual(calls.count((1,1)),1);self.assertEqual(calls.count((3,3)),1)
        self.assertEqual(calls.count((4,4)),2);self.assertEqual(verifier.call_count,2)
        self.assertEqual(report.verification_failures,[]);self.assertEqual(len(report.repair_attempts),1)

    def test_repair_is_bounded_and_unknown_targets_are_not_replayed(self):
        verifier=Mock(return_value={'ok':False,'missing_blocks':[{'block_id':2}]})
        report,calls=self.assembly(verifier)
        self.assertEqual(verifier.call_count,3);self.assertEqual(len(report.repair_attempts),2)
        self.assertTrue(report.verification_failures);self.assertEqual(calls.count((3,3)),1)
        report,calls=self.assembly(lambda *args:{'ok':False,'missing_blocks':[{'block_id':99}]})
        self.assertEqual(report.repair_attempts,[]);self.assertEqual(calls.count((1,1)),1)

    def test_cancellation_interrupts_repair_before_additional_input(self):
        stopped=[]
        def progress(action,role):
            if '复检补装' in action.get('name',''):stopped.append(True)
        with self.assertRaises(AssemblyExecutionStopped):
            self.assembly(lambda *args:{'ok':False,'missing_blocks':[{'block_id':2}]},stop=lambda:bool(stopped),callback=progress)


if __name__=='__main__':unittest.main(verbosity=2)
