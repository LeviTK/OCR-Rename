"""EXIF 方向烧录：将 EXIF Orientation 标签应用到像素数据并重置标签。

macOS 预览旋转图片时只修改 EXIF Orientation 元数据，不改变实际像素。
部分第三方软件忽略该标签，导致图片方向显示不正确。
本模块将旋转信息真正写入像素数据，使所有软件显示一致。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from PIL import Image

from .models import IMAGE_EXTS

ORIENTATION_TAG = 274

ORIENTATION_LABELS = {
    0: "未设置(0)", 1: "正常", 2: "水平翻转", 3: "旋转180°", 4: "垂直翻转",
    5: "转置", 6: "顺时针90°", 7: "横置", 8: "逆时针90°",
}

_ROTATE_MAP = {
    2: lambda img: img.transpose(Image.FLIP_LEFT_RIGHT),
    3: lambda img: img.rotate(180, expand=True),
    4: lambda img: img.transpose(Image.FLIP_TOP_BOTTOM),
    5: lambda img: img.transpose(Image.FLIP_LEFT_RIGHT).rotate(270, expand=True),
    6: lambda img: img.rotate(270, expand=True),
    7: lambda img: img.transpose(Image.FLIP_LEFT_RIGHT).rotate(90, expand=True),
    8: lambda img: img.rotate(90, expand=True),
}


@dataclass
class OrientationStats:
    total: int = 0
    fixed: int = 0
    skipped: int = 0
    errors: int = 0
    orientation_counts: dict = field(default_factory=dict)
    error_files: List[str] = field(default_factory=list)


def scan_orientations(input_dir: Path, recursive: bool = False) -> OrientationStats:
    """统计目录中图片的 EXIF 方向分布。"""
    stats = OrientationStats()
    images = _collect_images(input_dir, recursive)

    for fp in images:
        try:
            with Image.open(fp) as img:
                ori = img.getexif().get(ORIENTATION_TAG, 1)
                stats.orientation_counts[ori] = stats.orientation_counts.get(ori, 0) + 1
                stats.total += 1
        except Exception:
            stats.errors += 1
            stats.error_files.append(fp.name)

    return stats


def bake_orientations(
    input_dir: Path,
    recursive: bool = False,
    dry_run: bool = False,
    quality: int = 95,
) -> OrientationStats:
    """将 EXIF 方向烧录到像素数据。"""
    stats = OrientationStats()
    images = _collect_images(input_dir, recursive)

    for fp in images:
        try:
            with Image.open(fp) as img:
                exif_data = img.getexif()
                ori = exif_data.get(ORIENTATION_TAG, 1)
                stats.orientation_counts[ori] = stats.orientation_counts.get(ori, 0) + 1
                stats.total += 1

                if ori in (0, 1):
                    stats.skipped += 1
                    continue

                transform = _ROTATE_MAP.get(ori)
                if transform is None:
                    stats.skipped += 1
                    continue

                if not dry_run:
                    corrected = transform(img)
                    exif_data[ORIENTATION_TAG] = 1
                    save_kwargs = {"quality": quality, "exif": exif_data.tobytes()}
                    if fp.suffix.lower() in (".png",):
                        save_kwargs.pop("quality", None)
                    corrected.save(str(fp), **save_kwargs)

                stats.fixed += 1
                label = ORIENTATION_LABELS.get(ori, f"未知({ori})")
                print(f"  ✅ {fp.name}  {label} → 正常")

        except Exception as e:
            stats.errors += 1
            stats.error_files.append(fp.name)
            print(f"  ❌ {fp.name}: {e}")

    return stats


def _collect_images(input_dir: Path, recursive: bool) -> List[Path]:
    if recursive:
        images = []
        for root, _, files in os.walk(input_dir):
            root_path = Path(root)
            if root_path.name.startswith("."):
                continue
            for f in sorted(files):
                if Path(f).suffix.lower() in IMAGE_EXTS:
                    images.append(root_path / f)
        return images
    return sorted(
        p for p in input_dir.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS
    )


def print_orientation_report(stats: OrientationStats) -> None:
    """打印方向统计报告。"""
    need_fix = sum(v for k, v in stats.orientation_counts.items() if k not in (0, 1))
    print(f"\n📊 共 {stats.total} 张图片:")
    for ori, count in sorted(stats.orientation_counts.items(), key=lambda x: -x[1]):
        label = ORIENTATION_LABELS.get(ori, f"未知({ori})")
        print(f"   {label}: {count} 张")
    print(f"\n   需要烧录方向: {need_fix} 张")
    if stats.errors:
        print(f"   ❌ 读取失败: {stats.errors} 张")
