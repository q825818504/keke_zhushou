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
        final_page=0<self.expected_count-slot.index<=self.layout.columns*(self.layout.visible_rows-1)
        previous=None;stationary=0
        for attempt in range(60):
            if self._stopped:raise MouseInventoryScanError('扫描已停止')
            self._input.scroll(position,-120)
            self.scroll_command_count+=1;self.scroll_amounts.append(-120)
            self._sleep(.12)
            current=self._capture_frame()
            thumb=detect_scroll_thumb(current.image)
            if thumb is None:raise MouseInventoryScanError('翻页后无法确认滚动条，已停止')
            center=detect_selected_card_center_y(current.image,expected_x=x,scale=scale)
            if center is None:raise MouseInventoryScanError('翻页后无法定位原选中行，已停止以避免错位')
            # One scrollbar pixel can represent many items in a large bag.
            # A near-bottom thumb is not proof that the list has reached its end.
            state=(thumb.top,thumb.bottom,center)
            stationary=stationary+1 if previous and state[:2]==previous[:2] and abs(center-previous[2])<=2 else 0
            previous=state
            if thumb.at_bottom and stationary>=3:
                if not final_page:raise MouseInventoryScanError('列表已到底，但剩余数量超过一页；请核对筛选数量后重扫')
                first_row=max(0,(self.expected_count+self.layout.columns-1)//self.layout.columns-self.layout.visible_rows)
                row=(slot.index-1)//self.layout.columns-first_row
                if not 0<=row<self.layout.visible_rows:raise MouseInventoryScanError('末页锚点与库存数量不符，已停止')
                _,expected_y=self.layout.cell_center(row,slot.column,frame.rect.width,frame.rect.height)
                offset=round(center-expected_y)
                if abs(offset)>spacing*.45:raise MouseInventoryScanError('末页网格偏移超出范围，请核对数量后重扫')
                return current,row,offset,True
            if not final_page and target-spacing*.4<=center<=target+spacing*.12:
                offset=round(center-target)
                # Wait for inertia to settle and verify the same row again.
                self._sleep(.3);settled=self._capture_frame()
                checked=detect_selected_card_center_y(settled.image,expected_x=x,scale=scale)
                if checked is None or abs(checked-center)>3:raise MouseInventoryScanError('列表仍在移动，已停止以避免点击错位')
                return settled,0,offset,False
            if not final_page and center<target-spacing*.4:raise MouseInventoryScanError('滚动超过预期行，已停止以避免漏件')
        raise MouseInventoryScanError('翻页未到达预期行，扫描已停止')
