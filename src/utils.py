from __future__ import annotations

import contextlib
import os
import re
import shutil
import threading
from pathlib import Path
from typing import List, Sequence

import cv2
import numpy as np
from PIL import Image, ImageOps

from .models import IMAGE_EXTS

_STDERR_DEVNULL_FD: int | None = None
_STDERR_INIT_LOCK = threading.Lock()


def _get_devnull_fd() -> int | None:
    """延迟创建一个全局 devnull fd，所有线程共享。"""
    global _STDERR_DEVNULL_FD
    if _STDERR_DEVNULL_FD is None:
        with _STDERR_INIT_LOCK:
            if _STDERR_DEVNULL_FD is None:
                try:
                    _STDERR_DEVNULL_FD = os.open(os.devnull, os.O_WRONLY)
                except OSError:
                    pass
    return _STDERR_DEVNULL_FD


def iter_images(root: Path, recursive: bool, excluded_dirs: Sequence[Path]) -> List[Path]:
    resolved_excluded = [p.resolve() for p in excluded_dirs]
    if recursive:
        items = []
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in IMAGE_EXTS:
                continue
            rp = path.resolve()
            if any(ex == rp.parent or ex in rp.parents for ex in resolved_excluded if ex.exists()):
                continue
            items.append(path)
        return sorted(items)
    return sorted([p for p in root.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS])


def pil_to_bgr(img: Image.Image) -> np.ndarray:
    return cv2.cvtColor(np.array(img.convert("RGB")), cv2.COLOR_RGB2BGR)


def rotate_pil(img: Image.Image, rotation: int) -> Image.Image:
    if rotation == 0:
        return img.copy()
    return img.rotate(rotation, expand=True)


def ensure_unique_path(
    folder: Path,
    stem: str,
    suffix: str,
    reserved_names: set[str] | None = None,
    mkdir: bool = True,
) -> Path:
    if mkdir:
        folder.mkdir(parents=True, exist_ok=True)
    idx = 1
    while True:
        name = f"{stem}{suffix}" if idx == 1 else f"{stem}_{idx - 1}{suffix}"
        candidate = folder / name
        if not candidate.exists() and (reserved_names is None or name not in reserved_names):
            if reserved_names is not None:
                reserved_names.add(name)
            return candidate
        idx += 1


def move_file(src: Path, dst: Path, dry_run: bool) -> None:
    if dry_run:
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))


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
    """抑制当前线程中 C 层 stderr 输出（如 zbar databar warning）。

    使用 dup/dup2 在调用前后切换 fd2 到 /dev/null，
    减少全局锁持有时间，仅保护 dup2 操作本身，不跨越 yield。
    """
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
