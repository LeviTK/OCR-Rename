#!/usr/bin/env python3
"""票据二维码/条形码识别工具 CLI。"""
from __future__ import annotations

import argparse
from typing import Sequence

from .config import setup_platform


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ocr-rename",
        description="对指定目录中的票据图片执行扫描识别并原地重命名",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    scan = sub.add_parser(
        "scan",
        help="扫描目录中的图片并原地重命名",
    )
    scan.add_argument(
        "directory",
        nargs="?",
        default=None,
        help="图片目录路径（默认: ./001-Pic）",
    )
    scan.add_argument(
        "--dry-run",
        action="store_true",
        help="预览结果，不执行文件操作",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    setup_platform()
    from .pipeline import run_batch

    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.command == "scan":
        args.input = args.directory
        return run_batch(args)
    parser.error(f"未知命令: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
