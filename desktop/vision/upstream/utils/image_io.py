# Adapted from NTE-Drive-Calculator, commit 0e7a6b4e8e61d7a288e520bbc192a411d68c2fb1. AGPL-3.0.
# 提供支持中文路径的图像读取工具。
"""Unicode-safe image loading helpers for Windows paths."""

from pathlib import Path

import cv2
import numpy as np


def imread_unicode(path: str | Path, flags=cv2.IMREAD_COLOR):
    """Read images from paths containing non-ASCII characters on Windows."""
    data = np.fromfile(str(path), dtype=np.uint8)
    if data.size == 0:
        return None
    return cv2.imdecode(data, flags)
