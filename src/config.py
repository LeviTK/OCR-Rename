"""平台检测与环境配置。"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TESSDATA_DIR = ROOT / "tessdata"


def setup_platform() -> None:
    """启动时调用，配置平台特定依赖路径。"""
    # Windows: 自动添加 libzbar DLL 搜索路径
    if sys.platform == "win32":
        dll_dir = ROOT / "libs" / "win64"
        if dll_dir.is_dir():
            try:
                os.add_dll_directory(str(dll_dir))
            except AttributeError:
                pass
            os.environ["PATH"] = str(dll_dir) + os.pathsep + os.environ.get("PATH", "")

    # 设置 Tesseract tessdata 路径（使用项目自带训练数据）
    if TESSDATA_DIR.is_dir():
        os.environ.setdefault("TESSDATA_PREFIX", str(TESSDATA_DIR))
