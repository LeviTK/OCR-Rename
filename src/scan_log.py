"""扫描日志：记录已扫描的文件，支持跳过已处理的文件和目录。

日志文件 .scan_log.json 存储在输入目录下，记录每个已扫描文件的状态。
文件名已匹配有效码值格式 (49\\d{8}) 的自动跳过。
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import List

LOG_FILENAME = ".scan_log.json"
_CODED_PATTERN = re.compile(r"^49\d{8}(_.*)?$")


def load_log(input_dir: Path) -> dict:
    log_path = input_dir / LOG_FILENAME
    if log_path.is_file():
        try:
            return json.loads(log_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_log(input_dir: Path, log_data: dict, dry_run: bool = False) -> None:
    if dry_run or not log_data:
        return
    log_path = input_dir / LOG_FILENAME
    log_path.write_text(
        json.dumps(log_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def filter_unscanned(
    images: List[Path],
    log_data: dict,
    base_dir: Path,
) -> tuple[List[Path], List[Path]]:
    """根据日志过滤已扫描文件。

    跳过条件:
    1. 文件名已匹配有效码值格式 (49\\d{8})
    2. 文件的相对路径在日志中存在记录
    """
    to_scan: List[Path] = []
    skipped: List[Path] = []

    for img in images:
        if _CODED_PATTERN.match(img.stem):
            skipped.append(img)
            continue
        try:
            rel = str(img.relative_to(base_dir))
        except ValueError:
            rel = img.name
        if rel in log_data:
            skipped.append(img)
            continue
        to_scan.append(img)

    return to_scan, skipped


def record_result(
    log_data: dict | None,
    rel_path: str,
    status: str,
    code: str = "",
    renamed_to: str = "",
    note: str = "",
) -> None:
    if log_data is None:
        return
    entry: dict = {
        "status": status,
        "time": datetime.now().isoformat(timespec="seconds"),
    }
    if code:
        entry["code"] = code
    if renamed_to:
        entry["renamed_to"] = renamed_to
    if note:
        entry["note"] = note
    log_data[rel_path] = entry
