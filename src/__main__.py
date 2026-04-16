#!/usr/bin/env python3
"""票据二维码/条形码识别工具 — CLI 入口。

子命令:
    scan    扫描识别图片上的条形码/二维码并重命名
    rename  根据 CSV 映射表批量替换单号
    bake    将 EXIF 方向信息烧录到像素数据（修复旋转问题）

用法:
    python -m src scan --input /path/to/images
    python -m src scan --input /path/to/images --pair --dry-run
    python -m src rename --mapping map.csv --input /path/to/images
    python -m src bake --input /path/to/images
    python -m src --dry-run          # 向后兼容，等价于 scan --dry-run
"""
from __future__ import annotations

import argparse
from pathlib import Path

from .config import setup_platform

# 启动时配置平台依赖
setup_platform()


def _build_scan_parser(sub: argparse._SubParsersAction) -> argparse.ArgumentParser:
    p = sub.add_parser("scan", help="扫描识别图片上的条形码/二维码并重命名")
    p.add_argument("--input", type=str, default=None, help="输入图片文件夹路径（默认: ./001-Pic）")
    p.add_argument("-r", "--recursive", action="store_true", help="递归扫描子目录")
    p.add_argument("--skip-dirs", type=str, default="", help="跳过的子目录名称，逗号分隔（如: --skip-dirs 已处理,归档）")
    p.add_argument("--timeout", type=int, default=None, help="单张图片处理超时秒数，超时自动跳过（如: --timeout 60）")
    p.add_argument("--force", action="store_true", help="忽略扫描日志，强制重新扫描所有文件")
    p.add_argument("--marker", type=str, default="X", help="卸货照片标记符（默认: X，命名如: {码值}_X.jpg）")
    p.add_argument("--move", action="store_true", help="识别后移动到 识别正确/未识别 目录（旧行为）")
    p.add_argument("--pair", action="store_true", help="启用票据+卸货照片配对命名")
    p.add_argument("--dry-run", action="store_true", help="预览结果，不执行文件操作")
    return p


def _build_rename_parser(sub: argparse._SubParsersAction) -> argparse.ArgumentParser:
    p = sub.add_parser("rename", help="根据映射表批量替换单号（原始单号→新单号）")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--mapping", type=str, help="CSV 映射文件路径（列: 原始单号, 新单号）")
    group.add_argument("--from", dest="from_code", type=str, help="单条重命名: 原始单号")
    p.add_argument("--to", dest="to_code", type=str, help="单条重命名: 新单号（与 --from 配合使用）")
    p.add_argument("--input", type=str, default=".", help="图片所在文件夹（默认: 当前目录）")
    p.add_argument("--dry-run", action="store_true", help="预览结果，不执行")
    return p


def _build_bake_parser(sub: argparse._SubParsersAction) -> argparse.ArgumentParser:
    p = sub.add_parser("bake", help="将 EXIF 方向信息烧录到像素数据（修复 macOS 预览旋转后其他软件方向不对的问题）")
    p.add_argument("--input", type=str, required=True, help="图片文件夹路径")
    p.add_argument("-r", "--recursive", action="store_true", help="递归处理子目录")
    p.add_argument("--scan-only", action="store_true", help="仅统计方向分布，不执行烧录")
    p.add_argument("--quality", type=int, default=95, help="JPEG 保存质量（默认: 95）")
    p.add_argument("--dry-run", action="store_true", help="预览结果，不执行")
    return p


def _cmd_bake(args: argparse.Namespace) -> int:
    from .orientation import (
        bake_orientations,
        print_orientation_report,
        scan_orientations,
    )

    input_dir = Path(args.input).resolve()
    if not input_dir.is_dir():
        print(f"❌ 目录不存在: {input_dir}")
        return 1

    recursive = getattr(args, "recursive", False)
    scan_only = getattr(args, "scan_only", False)
    dry = getattr(args, "dry_run", False)
    quality = getattr(args, "quality", 95)

    if scan_only:
        print(f"📐 扫描 EXIF 方向信息  {'(递归)' if recursive else ''}\n")
        stats = scan_orientations(input_dir, recursive=recursive)
        print_orientation_report(stats)
        return 0

    print(f"📐 烧录 EXIF 方向到像素数据  {'(预览模式)' if dry else ''}  {'(递归)' if recursive else ''}\n")
    stats = bake_orientations(input_dir, recursive=recursive, dry_run=dry, quality=quality)

    print(f"\n{'━'*44}")
    print(f"📊 完成  ✅ 修正 {stats.fixed}  ⏭️ 无需处理 {stats.skipped}  ❌ 失败 {stats.errors}")
    if dry:
        print("   （预览模式，未修改文件）")
    return 0


def _cmd_scan(args: argparse.Namespace) -> int:
    from .pipeline import run_batch
    return run_batch(args)


def _cmd_rename(args: argparse.Namespace) -> int:
    from .batch_rename import (
        execute_rename,
        load_mapping,
        print_rename_report,
        validate_mapping,
    )

    target_dir = Path(args.input).resolve()
    if not target_dir.is_dir():
        print(f"❌ 目标目录不存在: {target_dir}")
        return 1

    # 加载映射
    if args.from_code:
        if not args.to_code:
            print("❌ --from 必须与 --to 配合使用")
            return 1
        mapping = {args.from_code: args.to_code}
    else:
        csv_path = Path(args.mapping).resolve()
        if not csv_path.is_file():
            print(f"❌ CSV 文件不存在: {csv_path}")
            return 1
        mapping = load_mapping(csv_path)
        if not mapping:
            print("📂 CSV 文件中没有有效映射")
            return 0
        print(f"📄 已加载 {len(mapping)} 条映射")

    # 校验
    valid_map, conflicts = validate_mapping(mapping, target_dir)

    # 执行
    results = execute_rename(valid_map, target_dir, dry_run=args.dry_run)

    # 报告
    print_rename_report(results, conflicts, dry_run=args.dry_run)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="python -m src",
        description="票据条形码/二维码批量识别工具",
    )

    # 向后兼容: 无子命令时的参数
    parser.add_argument("--dry-run", action="store_true", help="预览结果，不执行")

    sub = parser.add_subparsers(dest="command")
    _build_scan_parser(sub)
    _build_rename_parser(sub)
    _build_bake_parser(sub)

    args = parser.parse_args()

    if args.command == "scan":
        return _cmd_scan(args)
    elif args.command == "rename":
        return _cmd_rename(args)
    elif args.command == "bake":
        return _cmd_bake(args)
    else:
        # 向后兼容: 无子命令 → 等价于 scan
        args.command = "scan"
        args.input = None
        args.move = False
        args.pair = False
        args.recursive = False
        args.skip_dirs = ""
        args.timeout = None
        args.force = False
        args.marker = "X"
        return _cmd_scan(args)


if __name__ == "__main__":
    raise SystemExit(main())
