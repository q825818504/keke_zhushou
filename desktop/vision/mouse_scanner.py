"""Mouse capture with verified list origin and feedback-controlled scrolling."""
from dataclasses import dataclass
import cv2
import numpy as np
from .upstream.integrations.vision.mouse_inventory_scan import MouseInventoryScanner,MouseInventoryScanError
from .upstream.integrations.vision.mouse_scan_grid import detect_selected_card_center_y
from .upstream.scanner.window_capture import game_content_rect

@dataclass(frozen=True)
class ScrollThumb:
    x:int
    rail_top:int
    rail_bottom:int
    top:int
    bottom:int

    @property
    def at_top(self):return self.top<=self.rail_top+3
    @property
    def at_bottom(self):return self.bottom>=self.rail_bottom-3


def detect_scroll_thumb(image):
    height,width=image.shape[:2]
    left,top,_,content_height=game_content_rect(width,height)
    scale=content_height/1440
    x=left+round(1707*scale)
    rail_top=top+round(238*scale);rail_bottom=top+round(1234*scale)
    half=max(1,round(2*scale))
    roi=image[rail_top:rail_bottom+1,max(0,x-half):x+half+1,:3]
    if roi.size==0:return None
    gray=cv2.cvtColor(roi,cv2.COLOR_BGR2GRAY).mean(axis=1)
    rows=np.flatnonzero(gray>95)
    if not len(rows):return None
    groups=np.split(rows,np.where(np.diff(rows)>1)[0]+1)
    candidates=[g for g in groups if len(g)>=max(3,round(5*scale))]
    if len(candidates)!=1:return None
    group=candidates[0]
    return ScrollThumb(x,rail_top,rail_bottom,rail_top+int(group[0]),rail_top+int(group[-1]))


class VerifiedMouseScanner(MouseInventoryScanner):
    PANEL_STABLE_FRAMES=3
    PANEL_MAX_POLLS=45

    def __init__(self,*args,**kwargs):
        kwargs.setdefault('input_speed_profile',self.COMPATIBILITY_INPUT_SPEED_PROFILE)
        super().__init__(*args,**kwargs)

    def start_scan(self,total_drives=None,on_capture=None,commit_on_complete=True):
        self.expected_count=int(total_drives or 0)
        return super().start_scan(total_drives,on_capture,commit_on_complete)

    def _drag_inventory_list_to_top(self,frame):
        # Drag the visible scrollbar thumb, not the equipment grid: list swipes
        # carry momentum and cannot prove that the first item is visible.
        for attempt in range(2):
            if self._stopped:raise MouseInventoryScanError('扫描已停止')
            thumb=detect_scroll_thumb(frame.image)
            if thumb is None:
                if self.expected_count<=28:return
                raise MouseInventoryScanError('无法确认背包滚动条，请保持默认网格；已停止，未点击装备')
            if thumb.at_top:return
            center=(thumb.top+thumb.bottom)//2
            destination=thumb.rail_top+(thumb.bottom-thumb.top)//2
            self._input.drag((frame.rect.left+thumb.x,frame.rect.top+center),
                             (frame.rect.left+thumb.x,frame.rect.top+destination),
                             hold_seconds=.2,duration_seconds=.6)
            self._sleep(.5)
            frame=self._capture_frame()
        thumb=detect_scroll_thumb(frame.image)
        if thumb is None or not thumb.at_top:raise MouseInventoryScanError('未能确认背包已回到顶部，扫描已停止')

    def _scroll_to_next_page(self,frame,slot,*,row_offset_px=0):
        x,target=self.layout.cell_center(0,slot.column,frame.rect.width,frame.rect.height)
        _,next_y=self.layout.cell_center(1,slot.column,frame.rect.width,frame.rect.height)
        spacing=next_y-target
        scale=self._content_height(frame)/self.layout.base_height
        anchor=self.layout.cell_center(2,3,frame.rect.width,frame.rect.height)
        position=(frame.rect.left+anchor[0],frame.rect.top+anchor[1])
        for attempt in range(40):
            if self._stopped:raise MouseInventoryScanError('扫描已停止')
            self._input.scroll(position,-120)
            self.scroll_command_count+=1;self.scroll_amounts.append(-120)
            self._sleep(.12)
            current=self._capture_frame()
            thumb=detect_scroll_thumb(current.image)
            if thumb is None:raise MouseInventoryScanError('翻页后无法确认滚动条，已停止')
            if thumb.at_bottom:return current,0,0,True
            center=detect_selected_card_center_y(current.image,expected_x=x,scale=scale)
            if center is None:raise MouseInventoryScanError('翻页后无法定位原选中行，已停止以避免错位')
            if target-spacing*.4<=center<=target+spacing*.12:
                offset=round(center-target)
                # Wait for inertia to settle and verify the same row again.
                self._sleep(.3);settled=self._capture_frame()
                checked=detect_selected_card_center_y(settled.image,expected_x=x,scale=scale)
                if checked is None or abs(checked-center)>3:raise MouseInventoryScanError('列表仍在移动，已停止以避免点击错位')
                return settled,0,offset,False
            if center<target-spacing*.4:raise MouseInventoryScanError('滚动超过预期行，已停止以避免漏件')
        raise MouseInventoryScanError('翻页未到达预期行，扫描已停止')
