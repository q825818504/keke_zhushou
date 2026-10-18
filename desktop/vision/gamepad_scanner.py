"""Local capture performance adapter; upstream input timings remain unchanged."""
import os
import time
from dataclasses import replace
import mss.tools
from .upstream.scanner.gamepad_controller import GamepadScanner as UpstreamGamepadScanner
from .upstream.scanner.window_capture import capture_foreground_window
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
