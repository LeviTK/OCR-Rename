"""票据照片 / 卸货照片 / 共享托盘照片 配对逻辑。

按文件名排序后:
- 识别到码值的图片视为票据照片
- X 开头的图片视为卸货照片（跳过扫描）
- T 开头的图片视为共享托盘照片（跳过扫描）
- 其他无码图片默认视为卸货照片
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

from .utils import ensure_unique_path

PHOTO_PREFIX_MAP = {"X": "unload", "T": "pallet"}


def classify_by_prefix(filename: str) -> str:
    """根据文件名前缀分类: unload(X) / pallet(T) / normal。"""
    for prefix, role in PHOTO_PREFIX_MAP.items():
        if filename.startswith(prefix):
            return role
    return "normal"


@dataclass
class PairAssignment:
    """配对结果。"""
    source: Path
    new_name: str        # 新文件名（不含目录）
    role: str            # ticket | unload | pallet | unmatched
    paired_code: str     # 配对的码值
    note: str = ""


def assign_pairs(
    results: list,
    marker: str = "X",
    pallet_marker: str = "T",
) -> List[PairAssignment]:
    """根据扫描结果分配配对命名。

    Args:
        results: 按文件名排序的列表，每个元素为:
            (文件路径, 识别码值或空串)  — 兼容旧格式
            (文件路径, 识别码值或空串, 文件类型)  — 新格式，类型: normal/unload/pallet
        marker: 卸货照片标记符，默认 "X"。
        pallet_marker: 共享托盘标记符，默认 "T"。

    Returns:
        每张图片的配对命名结果。
    """
    assignments: List[PairAssignment] = []
    current_code: str = ""
    counters: dict[str, int] = {"unload": 1, "pallet": 1}
    used_names: set[str] = set()

    for item in results:
        if len(item) == 3:
            src, code, ftype = item
        else:
            src, code = item
            ftype = "normal"
        suffix = src.suffix.lower()

        if code:
            # 票据照片 — 有码值
            current_code = code
            counters = {"unload": 1, "pallet": 1}
            stem = code
            name = f"{stem}{suffix}"
            idx = 1
            while name in used_names:
                name = f"{stem}_{idx}{suffix}"
                idx += 1
            used_names.add(name)
            assignments.append(PairAssignment(
                source=src,
                new_name=name,
                role="ticket",
                paired_code=code,
            ))
        elif current_code:
            # 非票据照片 — 根据类型选择标记
            if ftype == "pallet":
                role = "pallet"
                active_marker = pallet_marker
            else:
                role = "unload"
                active_marker = marker

            seq = counters[role]
            if seq == 1:
                stem = f"{current_code}_{active_marker}"
            else:
                stem = f"{current_code}_{active_marker}_{seq}"
            name = f"{stem}{suffix}"
            while name in used_names:
                counters[role] += 1
                seq = counters[role]
                stem = f"{current_code}_{active_marker}_{seq}"
                name = f"{stem}{suffix}"
            used_names.add(name)
            counters[role] += 1
            assignments.append(PairAssignment(
                source=src,
                new_name=name,
                role=role,
                paired_code=current_code,
            ))
        else:
            assignments.append(PairAssignment(
                source=src,
                new_name=src.name,
                role="unmatched",
                paired_code="",
                note="前面没有已识别的票据，无法配对",
            ))

    return assignments


def execute_pair_rename(
    assignments: List[PairAssignment],
    dry_run: bool = False,
) -> tuple[int, int, int]:
    """执行配对重命名。

    Returns:
        (tickets, unloads, unmatched) 计数。
    """
    tickets = unloads = unmatched = 0
    for a in assignments:
        if a.role == "unmatched":
            unmatched += 1
            continue

        new_path = a.source.parent / a.new_name
        if new_path == a.source:
            # 文件名已经正确，跳过
            if a.role == "ticket":
                tickets += 1
            else:
                unloads += 1
            continue

        if not dry_run:
            # 确保不覆盖已有文件
            if new_path.exists():
                new_path = ensure_unique_path(
                    a.source.parent,
                    new_path.stem,
                    new_path.suffix,
                )
            a.source.rename(new_path)

        if a.role == "ticket":
            tickets += 1
        else:
            unloads += 1

    return tickets, unloads, unmatched
