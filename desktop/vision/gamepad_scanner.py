"""Local capture performance adapter; upstream input timings remain unchanged."""
import os
import time
from dataclasses import replace
import mss.tools
from .upstream.scanner.gamepad_controller import GamepadScanner as UpstreamGamepadScanner
from .upstream.scanner.window_capture import capture_foreground_window
from .upstream.scanner.window_capture import get_foreground_client_rect, game_content_rect
from .upstream.utils.logger import logger
from .upstream.utils.perf import log_perf


class GamepadScanner(UpstreamGamepadScanner):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # VisionService already gives the user three seconds to focus the game.
        self.action_profile = replace(self.action_profile, takeover_countdown_seconds=0)

    def capture_panel(self, sct, counter):
        started = time.perf_counter()
        screenshot, _ = capture_foreground_window(sct)
        captured = time.perf_counter()
        filename = os.path.join(self.capture_dir, f'raw_drive_{counter:04d}.png')
        # Level 1 keeps pixels lossless while shortening the input-blocking write.
        mss.tools.to_png(screenshot.rgb, screenshot.size, level=1, output=filename)
        finished = time.perf_counter()
        log_perf(logger, 'scan.capture', elapsed_ms=(finished-started)*1000,
                 index=counter, capture_ms=(captured-started)*1000,
                 write_ms=(finished-captured)*1000)
        return filename

    def _drag_inventory_list_to_top(self):
        super()._drag_inventory_list_to_top()
        if self._stopped:return
        # Dragging only resets scrolling; it does not reset the selected item.
        # Its final mouse position can also keep hovering another grid cell.
        rect=get_foreground_client_rect()
        left,top,width,height=game_content_rect(rect.width,rect.height)
        first=(round(rect.left+left+width*254/2560),round(rect.top+top+height*322/1440))
        driver=self._inventory_reset_input
        driver.click(first,content_height=height)
        driver.park((round(rect.left+left+width*.62),round(rect.top+top+height*.11)))
        if not self._wait_for_inventory_first_item():
            raise RuntimeError('未能确认背包第一格，已停止采集，请将列表置顶并选中第一件后重试。')
