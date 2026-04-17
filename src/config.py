"""平台检测与环境配置。"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def _root_dir() -> Path:
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        return Path(bundle_root)
    return Path(__file__).resolve().parent.parent


def _prepend_path(path: Path) -> None:
    current = os.environ.get("PATH", "")
    parts = [part for part in current.split(os.pathsep) if part]
    value = str(path)
    if value not in parts:
        os.environ["PATH"] = value + os.pathsep + current if current else value


ROOT = _root_dir()
TESSDATA_DIR = ROOT / "tessdata"


def setup_platform() -> None:
    """启动时调用，配置平台特定依赖路径。"""
    if sys.platform == "darwin":
        _add_mac_library_paths()

    # Windows: 自动添加 libzbar DLL 搜索路径
    if sys.platform == "win32":
        dll_dir = ROOT / "libs" / "win64"
        if dll_dir.is_dir():
            try:
                os.add_dll_directory(str(dll_dir))
            except AttributeError:
                pass
            _prepend_path(dll_dir)

        tesseract_dir = ROOT / "tesseract"
        if tesseract_dir.is_dir():
            _prepend_path(tesseract_dir)

    # 设置 Tesseract tessdata 路径（使用项目自带训练数据）
    if TESSDATA_DIR.is_dir():
        os.environ.setdefault("TESSDATA_PREFIX", str(TESSDATA_DIR))


def _add_mac_library_paths() -> None:
    candidates = [Path("/opt/homebrew/lib"), Path("/usr/local/lib")]
    existing = [str(path) for path in candidates if path.is_dir()]
    if not existing:
        return
    current = os.environ.get("DYLD_LIBRARY_PATH", "")
    parts = [part for part in current.split(os.pathsep) if part]
    for path in reversed(existing):
        if path not in parts:
            parts.insert(0, path)
    os.environ["DYLD_LIBRARY_PATH"] = os.pathsep.join(parts)
