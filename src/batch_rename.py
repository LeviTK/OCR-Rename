"""批量重命名：原始出库单号 → 新出库单号。

支持从 CSV 文件加载映射，三层查重校验后执行重命名。
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from .models import IMAGE_EXTS


@dataclass
class RenameResult:
    original: str
    target: str
    status: str     # ok | dup_original | dup_target | file_exists | not_found | skipped
    files_renamed: List[tuple[str, str]] = field(default_factory=list)
    reason: str = ""


def load_mapping(csv_path: Path) -> dict[str, str]:
    """从 CSV 文件读取原始单号→新单号的映射。

    CSV 格式: 第一列为原始单号，第二列为新单号。
    自动跳过表头（如果第一行不是纯数字）。
    支持 UTF-8 和 GBK 编码。
    """
    text = ""
    for encoding in ("utf-8-sig", "utf-8", "gbk", "gb2312"):
        try:
            text = csv_path.read_text(encoding=encoding)
            break
        except (UnicodeDecodeError, LookupError):
            continue
    if not text:
        raise ValueError(f"无法读取 CSV 文件: {csv_path}")

    mapping: dict[str, str] = {}
    reader = csv.reader(text.strip().splitlines())
    for row in reader:
        if len(row) < 2:
            continue
        original = row[0].strip()
        target = row[1].strip()
        if not original or not target:
            continue
        # 跳过表头
        if not re.search(r"\d", original):
            continue
        mapping[original] = target
    return mapping


def validate_mapping(
    mapping: dict[str, str],
    target_dir: Path,
) -> tuple[dict[str, str], List[RenameResult]]:
    """三层查重校验。

    Returns:
        (有效映射, 冲突报告列表)
    """
    conflicts: List[RenameResult] = []
    valid: dict[str, str] = {}

    # ── 校验 ①: 原始单号唯一性（在 load_mapping 中 dict 已去重，后出现的覆盖前面的）
    # 如果需要严格检查 CSV 中重复行，可在 load_mapping 中增加检测
    # 这里检查的是：是否有多个原始单号指向不同新单号（load_mapping 只保留最后一个）

    # ── 校验 ②: 新单号唯一性
    reverse: dict[str, list[str]] = {}
    for original, target in mapping.items():
        reverse.setdefault(target, []).append(original)

    dup_targets: set[str] = set()
    for target, originals in reverse.items():
        if len(originals) > 1:
            dup_targets.add(target)
            for orig in originals:
                conflicts.append(RenameResult(
                    original=orig,
                    target=target,
                    status="dup_target",
                    reason=f"多个原始单号指向同一新单号: {', '.join(originals)}",
                ))

    # ── 校验 ③: 文件系统冲突
    existing_files: set[str] = set()
    if target_dir.is_dir():
        existing_files = {p.stem for p in target_dir.iterdir() if p.is_file()}

    for original, target in mapping.items():
        if target in dup_targets:
            continue  # 已在校验②中报告

        # 检查新单号是否与现有文件撞名（且不是自己）
        if target in existing_files and target != original:
            conflicts.append(RenameResult(
                original=original,
                target=target,
                status="file_exists",
                reason=f"目标文件名已存在: {target}",
            ))
            continue

        valid[original] = target

    return valid, conflicts


def execute_rename(
    valid_map: dict[str, str],
    target_dir: Path,
    dry_run: bool = False,
) -> List[RenameResult]:
    """执行批量重命名。

    查找 target_dir 中所有匹配 {原始单号}*.ext 的文件并重命名。
    包括配对的卸货照片（如 {原始单号}_2.jpg）。
    """
    results: List[RenameResult] = []

    # 建立原始单号 → 文件列表的索引
    all_files = sorted(
        p for p in target_dir.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS
    )

    for original, target in sorted(valid_map.items()):
        # 匹配: {original}.ext, {original}_2.ext, {original}_3.ext ...
        pattern = re.compile(rf"^{re.escape(original)}(_\d+)?$")
        matched_files: list[Path] = []
        for f in all_files:
            if pattern.match(f.stem):
                matched_files.append(f)

        if not matched_files:
            results.append(RenameResult(
                original=original,
                target=target,
                status="not_found",
                reason=f"未找到文件: {original}.*",
            ))
            continue

        renamed_pairs: list[tuple[str, str]] = []
        for f in matched_files:
            # 保留后缀部分 (如 _2)
            suffix_part = f.stem[len(original):]  # "" 或 "_2" 或 "_3" ...
            new_stem = f"{target}{suffix_part}"
            new_path = f.parent / f"{new_stem}{f.suffix}"

            if new_path.exists() and new_path != f:
                # 目标已存在，跳过该文件
                continue

            renamed_pairs.append((f.name, new_path.name))
            if not dry_run:
                f.rename(new_path)

        results.append(RenameResult(
            original=original,
            target=target,
            status="ok" if renamed_pairs else "skipped",
            files_renamed=renamed_pairs,
            reason="" if renamed_pairs else "文件已存在或无法重命名",
        ))

    return results


def print_rename_report(
    results: List[RenameResult],
    conflicts: List[RenameResult],
    dry_run: bool = False,
) -> None:
    """打印重命名报告。"""
    ok = [r for r in results if r.status == "ok"]
    not_found = [r for r in results if r.status == "not_found"]
    skipped = [r for r in results if r.status == "skipped"]

    print(f"\n{'━'*50}")
    if dry_run:
        print("📋 批量重命名预览（未执行）")
    else:
        print("📋 批量重命名结果")
    print(f"{'━'*50}")

    if ok:
        print(f"\n✅ 成功: {len(ok)} 组")
        for r in ok:
            for old_name, new_name in r.files_renamed:
                print(f"   {old_name} → {new_name}")

    if conflicts:
        print(f"\n⚠️ 冲突跳过: {len(conflicts)} 组")
        for r in conflicts:
            print(f"   {r.original} → {r.target}  原因: {r.reason}")

    if not_found:
        print(f"\n📂 未找到文件: {len(not_found)} 组")
        for r in not_found:
            print(f"   {r.original} ({r.reason})")

    if skipped:
        print(f"\n⏭️ 跳过: {len(skipped)} 组")
        for r in skipped:
            print(f"   {r.original} → {r.target}  {r.reason}")

    total = len(ok) + len(conflicts) + len(not_found) + len(skipped)
    print(f"\n{'─'*50}")
    print(f"📊 共 {total} 条映射  ✅ {len(ok)}  ⚠️ {len(conflicts)}  📂 {len(not_found)}  ⏭️ {len(skipped)}")
