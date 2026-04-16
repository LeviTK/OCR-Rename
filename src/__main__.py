#!/usr/bin/env python3
"""票据二维码/条形码识别工具 CLI。"""
from __future__ import annotations

import argparse

from .config import setup_platform
from .pipeline import run_batch

setup_platform()


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="python -m src",
        description="扫描目录中的票据图片并原地重命名",
    )
    parser.add_argument(
        "--input",
        type=str,
        default=None,
        help="输入图片文件夹路径（默认: ./001-Pic）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="预览结果，不执行文件操作",
    )
    args = parser.parse_args()
    return run_batch(args)


if __name__ == "__main__":
    raise SystemExit(main())
