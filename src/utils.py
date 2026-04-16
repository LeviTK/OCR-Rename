from __future__ import annotations

import contextlib
import os
import re
import threading

import cv2
import numpy as np
from PIL import Image

_STDERR_DEVNULL_FD: int | None = None
_STDERR_INIT_LOCK = threading.Lock()


def _get_devnull_fd() -> int | None:
    global _STDERR_DEVNULL_FD
    if _STDERR_DEVNULL_FD is None:
        with _STDERR_INIT_LOCK:
            if _STDERR_DEVNULL_FD is None:
                try:
                    _STDERR_DEVNULL_FD = os.open(os.devnull, os.O_WRONLY)
                except OSError:
                    pass
    return _STDERR_DEVNULL_FD


def pil_to_bgr(img: Image.Image) -> np.ndarray:
    return cv2.cvtColor(np.array(img.convert("RGB")), cv2.COLOR_RGB2BGR)


def rotate_pil(img: Image.Image, rotation: int) -> Image.Image:
    if rotation == 0:
        return img.copy()
    return img.rotate(rotation, expand=True)


def normalize_value(text: str) -> str:
    return text.strip().replace(" ", "").replace("\n", "")


def normalize_numeric_value(text: str) -> str:
    value = normalize_value(text)
    for pattern in (r"4920\d{6}", r"49\d{8}"):
        match = re.search(pattern, value)
        if match:
            return match.group(0)
    return ""


@contextlib.contextmanager
def suppress_stderr_fd2():
    devnull_fd = _get_devnull_fd()
    if devnull_fd is None:
        yield
        return
    try:
        old_stderr = os.dup(2)
    except OSError:
        yield
        return
    try:
        os.dup2(devnull_fd, 2)
    except OSError:
        os.close(old_stderr)
        yield
        return
    try:
        yield
    finally:
        try:
            os.dup2(old_stderr, 2)
        except OSError:
            pass
        finally:
            os.close(old_stderr)
