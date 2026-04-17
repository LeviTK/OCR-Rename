#!/usr/bin/env python3
"""票据二维码/条形码识别工具 CLI。"""
from __future__ import annotations

import argparse
import os
import sys
from typing import Sequence

from .config import setup_platform


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ocr-rename",
        description="对指定目录中的票据图片执行扫描识别并原地重命名",
    )
    sub = parser.add_subparsers(dest="command")

    scan = sub.add_parser(
        "scan",
        help="扫描目录中的图片并原地重命名",
    )
    scan.add_argument(
        "directory",
        nargs="?",
        default=None,
        help="图片目录路径（默认: ./input）",
    )
    scan.add_argument(
        "--dry-run",
        action="store_true",
        help="预览结果，不执行文件操作",
    )
    return parser


def _coerce_argv(argv: Sequence[str] | None) -> tuple[list[str], bool]:
    args = list(argv) if argv is not None else sys.argv[1:]
    if args:
        if args[0] == "scan" or args[0].startswith("-"):
            return args, False
        return ["scan", *args], False

    print("请把要处理的图片文件夹拖到这个窗口，然后按回车。")
    print("直接回车则使用项目内默认 input/ 目录。")
    try:
        raw = input("> ").strip()
    except EOFError:
        raw = ""
    if raw:
        return ["scan", raw.strip('"')], True
    return ["scan"], True


def _pause_before_exit() -> None:
    if sys.platform != "win32":
        return
    if not getattr(sys, "frozen", False):
        return
    if os.environ.get("OCR_RENAME_NO_PAUSE") == "1":
        return
    try:
        input("\n处理结束，按回车退出...")
    except EOFError:
        pass


def main(argv: Sequence[str] | None = None) -> int:
    setup_platform()
    from .pipeline import run_batch

    parser = build_parser()
    coerced_argv, prompted = _coerce_argv(argv)
    try:
        args = parser.parse_args(coerced_argv)

        if args.command == "scan":
            args.input = args.directory
            return run_batch(args)
        parser.print_help()
        return 2
    finally:
        if prompted or getattr(sys, "frozen", False):
            _pause_before_exit()


if __name__ == "__main__":
    raise SystemExit(main())
