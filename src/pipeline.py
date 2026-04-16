from __future__ import annotations

import argparse
import os
import shutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Sequence

from PIL import Image, ImageOps

from .barcode import scan as scan_barcodes
from .models import DecodeHit, IMAGE_EXTS
from .ocr import scan_fallback
from .pair import PairAssignment, assign_pairs, classify_by_prefix, execute_pair_rename
from .qrcode_scan import scan as scan_qr
from .scan_log import filter_unscanned, load_log, record_result, save_log
from .utils import ensure_unique_path, normalize_numeric_value, rotate_pil

# ── 默认目录（相对于项目根目录，仅在 --move 模式下使用）──────────────
_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_INPUT = _ROOT / "001-Pic"
_DEFAULT_OK_DIR = _ROOT / "识别正确"
_DEFAULT_FAIL_DIR = _ROOT / "未识别"


# ── 单图识别 ────────────────────────────────────────────────────────

ProgressCallback = Callable[[Path, int, int, str], None]


@dataclass
class ProcessOutcome:
    status: str
    final_value: str = ""
    ocr_hint: str = ""
    error_note: str = ""


class BatchReporter:
    def __init__(self, round_name: str) -> None:
        self.round_name = round_name
        self._lock = threading.Lock()

    def step(self, src: Path, step: int, total_steps: int, label: str) -> None:
        with self._lock:
            print(f"  🔄 [{self.round_name}] {src.name}  第{step}/{total_steps}步：{label}", flush=True)

    def line(self, text: str = "") -> None:
        with self._lock:
            print(text, flush=True)


def _emit_progress(progress: ProgressCallback | None, src: Path, step: int, total_steps: int, label: str) -> None:
    if progress is not None:
        progress(src, step, total_steps, label)


def _rank_hits(hits: Sequence[DecodeHit], kind: str | None = None) -> List[tuple[str, int]]:
    seen: dict[str, int] = {}
    for h in hits:
        if kind is not None and h.kind != kind:
            continue
        v = normalize_numeric_value(h.value)
        if v:
            seen[v] = seen.get(v, 0) + h.weight
    return sorted(seen.items(), key=lambda x: (-x[1], x[0]))


def _choose_final_value(hits: Sequence[DecodeHit]) -> str:
    barcode_rank = _rank_hits(hits, "barcode")
    qr_rank = _rank_hits(hits, "qrcode")

    barcode_scores = dict(barcode_rank)
    qr_scores = dict(qr_rank)
    common = sorted(
        ((value, barcode_scores[value] + qr_scores[value]) for value in barcode_scores.keys() & qr_scores.keys()),
        key=lambda x: (-x[1], x[0]),
    )
    if common:
        return common[0][0]

    merged: dict[str, int] = {}
    for value, score in barcode_rank:
        merged[value] = merged.get(value, 0) + score
    for value, score in qr_rank:
        merged[value] = merged.get(value, 0) + score

    if not merged:
        return ""
    return sorted(merged.items(), key=lambda x: (-x[1], x[0]))[0][0]


def _scan_region_fast(img: Image.Image) -> List[DecodeHit]:
    """快速扫描：条形码 + 二维码快扫。"""
    w, h = img.size
    rotations = (0, 180) if w >= h else (90, 270)
    all_hits: List[DecodeHit] = []

    for rot in rotations:
        rotated = rotate_pil(img, rot)
        all_hits.extend(scan_barcodes(rotated, rot))
        all_hits.extend(scan_qr(rotated, rot, deep=False))

    return all_hits


def _scan_region_deep_qr(img: Image.Image) -> List[DecodeHit]:
    """深度扫描：只做二维码增强扫描。"""
    w, h = img.size
    rotations = (0, 180) if w >= h else (90, 270)
    all_hits: List[DecodeHit] = []

    for rot in rotations:
        rotated = rotate_pil(img, rot)
        all_hits.extend(scan_qr(rotated, rot, deep=True))

    return all_hits


def _ocr_hint(img: Image.Image) -> str:
    ranked = _rank_hits(scan_fallback(img, 0, "chi_sim+eng"), "ocr")
    return ranked[0][0] if ranked else ""


def _half_crops(img: Image.Image) -> List[Image.Image]:
    w, h = img.size
    return [img.crop((0, 0, w, h // 2)), img.crop((0, h // 2, w, h))]


def process_one(
    src: Path,
    deep: bool = True,
    progress: ProgressCallback | None = None,
) -> ProcessOutcome:
    """status: ok / fail / fail_ocr / error。"""
    total_steps = 5 if deep else 3
    _emit_progress(progress, src, 1, total_steps, "读取图片")
    try:
        with Image.open(src) as raw:
            base = ImageOps.exif_transpose(raw)
    except Exception:
        return ProcessOutcome(status="error", error_note="图片无法读取")

    _emit_progress(progress, src, 2, total_steps, "全图快扫（条形码 + 二维码）")
    hits = _scan_region_fast(base)
    final_value = _choose_final_value(hits)
    if final_value:
        return ProcessOutcome(status="ok", final_value=final_value)

    _emit_progress(progress, src, 3, total_steps, "半图补扫（上半 / 下半）")
    half_hits: List[DecodeHit] = []
    for crop in _half_crops(base):
        half_hits.extend(_scan_region_fast(crop))
    if half_hits:
        final_value = _choose_final_value(hits + half_hits)
        if final_value:
            return ProcessOutcome(status="ok", final_value=final_value)

    if not deep:
        return ProcessOutcome(status="fail")

    _emit_progress(progress, src, 4, total_steps, "二维码深扫（增强 + ROI）")
    deep_hits: List[DecodeHit] = list(_scan_region_deep_qr(base))
    for crop in _half_crops(base):
        deep_hits.extend(_scan_region_deep_qr(crop))

    if deep_hits:
        all_hits = hits + half_hits + deep_hits
        final_value = _choose_final_value(all_hits)
        if final_value:
            return ProcessOutcome(status="ok", final_value=final_value)

    _emit_progress(progress, src, 5, total_steps, "OCR兜底与最终判定")
    hint = _ocr_hint(base)
    if hint:
        return ProcessOutcome(status="fail_ocr", ocr_hint=hint)

    return ProcessOutcome(status="fail")


def _process_one_timed(
    src: Path,
    deep: bool,
    progress: ProgressCallback | None = None,
    timeout: float | None = None,
) -> tuple[Path, ProcessOutcome, float]:
    started = time.time()
    if timeout is not None:
        result_holder: list[ProcessOutcome | None] = [None]

        def _worker() -> None:
            try:
                result_holder[0] = process_one(src, deep=deep, progress=progress)
            except Exception as exc:
                result_holder[0] = ProcessOutcome(
                    status="error",
                    error_note=f"处理异常: {type(exc).__name__}: {exc}",
                )

        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        t.join(timeout=timeout)
        elapsed = time.time() - started
        if t.is_alive():
            return src, ProcessOutcome(
                status="timeout",
                error_note=f"处理超时（>{timeout}s），已跳过",
            ), elapsed
        return src, result_holder[0] or ProcessOutcome(status="error", error_note="未知错误"), elapsed

    try:
        outcome = process_one(src, deep=deep, progress=progress)
    except Exception as exc:
        outcome = ProcessOutcome(
            status="error",
            error_note=f"处理异常: {type(exc).__name__}: {exc}",
        )
    return src, outcome, time.time() - started


# ── 文件操作 ────────────────────────────────────────────────────────

def _move(src: Path, dst: Path, dry: bool) -> None:
    if not dry:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))


def _rename_in_place(src: Path, new_name: str, dry: bool) -> Path:
    """原地重命名，返回新路径。"""
    dst = src.parent / new_name
    if dst == src:
        return src
    if not dry:
        if dst.exists():
            dst = ensure_unique_path(src.parent, dst.stem, dst.suffix)
        src.rename(dst)
    return dst


def _fail_reason(outcome: ProcessOutcome) -> str:
    reason = "二维码和条形码都未识别出有效数字"
    if outcome.ocr_hint:
        reason += f"  OCR候选={outcome.ocr_hint}"
    return reason


# ── 批量处理 ────────────────────────────────────────────────────────

def _resolve_input_dir(args: argparse.Namespace) -> Path:
    """解析输入目录。"""
    if getattr(args, "input", None):
        p = Path(args.input).resolve()
    else:
        p = _DEFAULT_INPUT
    return p


def _filter_prefix_files(images: List[Path]) -> tuple[List[Path], List[Path]]:
    """将 X/T 前缀文件从图片列表中剥离，返回 (需扫描, 已跳过)。"""
    scan, skip = [], []
    for p in images:
        if classify_by_prefix(p.name) != "normal":
            skip.append(p)
        else:
            scan.append(p)
    return scan, skip


def _log_rel(src: Path, base_dir: Path | None) -> str:
    if base_dir is None:
        return src.name
    try:
        return str(src.relative_to(base_dir))
    except ValueError:
        return src.name


def run_batch(args: argparse.Namespace) -> int:
    input_dir = _resolve_input_dir(args)
    use_move = getattr(args, "move", False)
    use_pair = getattr(args, "pair", False)
    dry = getattr(args, "dry_run", False)
    recursive = getattr(args, "recursive", False)
    timeout = getattr(args, "timeout", None)
    force = getattr(args, "force", False)
    marker = getattr(args, "marker", "X")
    skip_dirs_raw = getattr(args, "skip_dirs", "")
    skip_dirs = {s.strip() for s in skip_dirs_raw.split(",") if s.strip()} if skip_dirs_raw else set()

    if not input_dir.is_dir():
        print(f"❌ 源目录不存在: {input_dir}")
        return 1

    log_data = {} if force else load_log(input_dir)

    if recursive:
        result = _run_recursive(input_dir, use_move, use_pair, dry, timeout, force, skip_dirs, marker, log_data)
        save_log(input_dir, log_data, dry)
        return result

    images = sorted(
        p for p in input_dir.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS
    )

    # X/T 前缀文件跳过扫描
    images, prefix_skipped = _filter_prefix_files(images)
    if prefix_skipped:
        print(f"⏭️ 跳过 X/T 前缀: {len(prefix_skipped)} 张（卸货/托盘，暂不扫描）")

    if log_data and not force:
        images, skipped = filter_unscanned(images, log_data, input_dir)
        if skipped:
            print(f"⏭️ 跳过已扫描: {len(skipped)} 张（使用 --force 强制重扫）")

    if not images:
        print(f"📂 {input_dir.name}/ 中没有待识别图片")
        save_log(input_dir, log_data, dry)
        return 0

    if use_pair:
        # pair 模式需要完整图片列表（含 X/T），内部自行处理前缀
        all_images = sorted(images + prefix_skipped, key=lambda p: p.name)
        _run_batch_pair(all_images, input_dir, dry, timeout, marker, log_data, input_dir)
    elif use_move:
        _run_batch_move(images, _DEFAULT_OK_DIR, _DEFAULT_FAIL_DIR, dry, timeout, log_data, input_dir)
    else:
        _run_batch_rename(images, dry, timeout, log_data, input_dir)

    save_log(input_dir, log_data, dry)
    return 0


def _run_recursive(
    input_dir: Path,
    use_move: bool,
    use_pair: bool,
    dry: bool,
    timeout: float | None,
    force: bool,
    skip_dirs: set[str],
    marker: str,
    log_data: dict,
) -> int:
    """递归扫描子目录模式。"""
    dirs_to_scan: List[tuple[Path, List[Path]]] = []

    root_images = sorted(
        p for p in input_dir.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS
    )
    if root_images:
        dirs_to_scan.append((input_dir, root_images))

    skipped_dirs: List[str] = []
    for d in sorted(input_dir.iterdir()):
        if not d.is_dir() or d.name.startswith("."):
            continue
        if d.name in skip_dirs:
            skipped_dirs.append(d.name)
            continue
        sub_images = sorted(
            p for p in d.iterdir()
            if p.is_file() and p.suffix.lower() in IMAGE_EXTS
        )
        if sub_images:
            dirs_to_scan.append((d, sub_images))

    if not dirs_to_scan:
        print(f"📂 {input_dir.name}/ 及其子目录中没有待识别图片")
        return 0

    total_images = sum(len(imgs) for _, imgs in dirs_to_scan)
    print(f"📁 递归模式: 发现 {len(dirs_to_scan)} 个目录, 共 {total_images} 张图片")
    if skipped_dirs:
        print(f"   ⏭️ 跳过目录: {', '.join(skipped_dirs)}")
    if timeout:
        print(f"   ⏰ 单图超时: {timeout}s")
    if dry:
        print(f"   📋 预览模式")

    grand = {"ok": 0, "fail": 0, "error": 0, "timeout": 0, "total": 0}
    t0 = time.time()
    log_skipped_total = 0
    prefix_skipped_total = 0

    for idx, (scan_dir, images) in enumerate(dirs_to_scan, 1):
        rel_name = scan_dir.name if scan_dir != input_dir else "."
        log_skipped: list = []

        # X/T 前缀过滤
        images, prefix_skipped = _filter_prefix_files(images)
        prefix_skipped_total += len(prefix_skipped)

        # 日志过滤
        if log_data and not force:
            images, log_skipped = filter_unscanned(images, log_data, input_dir)
            log_skipped_total += len(log_skipped)
            if not images:
                skip_parts = []
                if log_skipped:
                    skip_parts.append(f"日志 {len(log_skipped)}")
                if prefix_skipped:
                    skip_parts.append(f"X/T {len(prefix_skipped)}")
                print(f"\n📁 [{idx}/{len(dirs_to_scan)}] {rel_name}/  全部跳过 ({', '.join(skip_parts)})")
                continue

        if not images:
            if prefix_skipped:
                print(f"\n📁 [{idx}/{len(dirs_to_scan)}] {rel_name}/  全部为 X/T 前缀，跳过 ({len(prefix_skipped)} 张)")
            continue

        print(f"\n{'═'*50}")
        msg = f"📁 [{idx}/{len(dirs_to_scan)}] {rel_name}/  ({len(images)} 张)"
        if log_skipped:
            msg += f"  ⏭️ 日志跳过 {len(log_skipped)}"
        if prefix_skipped:
            msg += f"  ⏭️ X/T跳过 {len(prefix_skipped)}"
        print(msg)
        print(f"{'═'*50}")

        if use_pair:
            # pair 模式需要完整列表
            all_images = sorted(images + list(prefix_skipped), key=lambda p: p.name)
            stats = _run_batch_pair(all_images, scan_dir, dry, timeout, marker, log_data, input_dir)
        elif use_move:
            stats = _run_batch_move(images, _DEFAULT_OK_DIR, _DEFAULT_FAIL_DIR, dry, timeout, log_data, input_dir)
        else:
            stats = _run_batch_rename(images, dry, timeout, log_data, input_dir)

        for k in grand:
            grand[k] += stats.get(k, 0)

    total_time = time.time() - t0
    to_str = f"  ⏰ {grand['timeout']}" if grand["timeout"] else ""
    skip_parts = []
    if log_skipped_total:
        skip_parts.append(f"日志 {log_skipped_total}")
    if prefix_skipped_total:
        skip_parts.append(f"X/T {prefix_skipped_total}")
    skip_str = f"  ⏭️ 跳过 {'+'.join(skip_parts)}" if skip_parts else ""
    print(f"\n{'━'*50}")
    print(f"📊 全部目录扫描完成  共 {len(dirs_to_scan)} 个目录")
    print(f"   共 {grand['total']} 张  ✅ {grand['ok']}  ❌ {grand['fail']}  ⚠️ {grand['error']}{to_str}{skip_str}  ⏱ {total_time:.1f}s")
    if dry:
        print("   （预览模式，未执行文件操作）")
    return 0


def _run_batch_rename(images: List[Path], dry: bool, timeout: float | None = None,
                     log_data: dict | None = None, base_dir: Path | None = None) -> dict:
    """原地重命名模式: 识别成功→原地重命名为码值，失败→保持原名。"""
    total = len(images)
    ok = fail = error = timeout_count = 0
    t0 = time.time()
    pending: List[Path] = []
    reserved_names: set[str] = set()
    workers = max(1, min(4, os.cpu_count() or 1))

    # ━━━ 第一轮：快速扫描 ━━━
    print(f"⚡ 第一轮 · 快速扫描  共 {total} 张  {'(预览模式)' if dry else ''}\n")
    r1 = BatchReporter("快扫")

    with ThreadPoolExecutor(max_workers=min(workers, total)) as executor:
        futures = [executor.submit(_process_one_timed, src, False, r1.step, timeout) for src in images]
        for i, future in enumerate(as_completed(futures), 1):
            src, outcome, elapsed = future.result()
            tag = f"[{i}/{total}]"

            if outcome.status == "ok":
                new_name = _unique_name(src, outcome.final_value, reserved_names)
                dst = _rename_in_place(src, new_name, dry)
                ok += 1
                r1.line(f"  ✅ {tag} {src.name} → {dst.name}  ({outcome.final_value})  {elapsed:.1f}s")
                record_result(
                    log_data,
                    _log_rel(src, base_dir),
                    "ok",
                    outcome.final_value,
                    dst.name,
                )
            elif outcome.status in ("error", "timeout"):
                if outcome.status == "timeout":
                    timeout_count += 1
                    symbol = "⏰"
                else:
                    error += 1
                    symbol = "⚠️"
                note = outcome.error_note or "图片无法读取"
                r1.line(f"  {symbol} {tag} {src.name}  {note}  {elapsed:.1f}s")
                record_result(log_data, _log_rel(src, base_dir), outcome.status)
            else:
                pending.append(src)
                r1.line(f"  ⏳ {tag} {src.name}  待深度扫描  {elapsed:.1f}s")

    round1_time = time.time() - t0
    to_str = f"  ⏰ {timeout_count}" if timeout_count else ""
    print(f"\n{'─'*44}")
    print(f"⚡ 第一轮完成  ✅ {ok}  ⏳ 待深度 {len(pending)}  ⚠️ {error}{to_str}  ⏱ {round1_time:.1f}s")

    # ━━━ 第二轮：深度扫描 ━━━
    if pending:
        print(f"\n🔬 第二轮 · 深度扫描  共 {len(pending)} 张\n")
        t1 = time.time()
        active_pending = [src for src in pending if src.exists()]
        r2 = BatchReporter("深扫")
        with ThreadPoolExecutor(max_workers=min(workers, len(active_pending) or 1)) as executor:
            futures = [executor.submit(_process_one_timed, src, True, r2.step, timeout) for src in active_pending]
            for i, future in enumerate(as_completed(futures), 1):
                src, outcome, elapsed = future.result()
                tag = f"[{i}/{len(active_pending)}]"

                if outcome.status == "ok":
                    new_name = _unique_name(src, outcome.final_value, reserved_names)
                    dst = _rename_in_place(src, new_name, dry)
                    ok += 1
                    r2.line(f"  ✅ {tag} {src.name} → {dst.name}  ({outcome.final_value})  {elapsed:.1f}s")
                    record_result(
                        log_data,
                        _log_rel(src, base_dir),
                        "ok",
                        outcome.final_value,
                        dst.name,
                    )
                elif outcome.status == "timeout":
                    timeout_count += 1
                    r2.line(f"  ⏰ {tag} {src.name}  {outcome.error_note}  {elapsed:.1f}s")
                    record_result(log_data, _log_rel(src, base_dir), "timeout")
                elif outcome.status == "error":
                    error += 1
                    note = outcome.error_note or "图片无法读取"
                    r2.line(f"  ⚠️ {tag} {src.name}  {note}  {elapsed:.1f}s")
                    record_result(log_data, _log_rel(src, base_dir), "error")
                else:
                    fail += 1
                    r2.line(f"  ❌ {tag} {src.name}  {_fail_reason(outcome)}  {elapsed:.1f}s")
                    record_result(log_data, _log_rel(src, base_dir), "fail")

        round2_time = time.time() - t1
        to_str = f"  ⏰ {timeout_count}" if timeout_count else ""
        print(f"\n{'─'*44}")
        print(f"🔬 第二轮完成  ✅ {ok}  ❌ {fail}  ⚠️ {error}{to_str}  ⏱ {round2_time:.1f}s")

    total_time = time.time() - t0
    to_str = f"  ⏰ {timeout_count}" if timeout_count else ""
    print(f"\n{'━'*44}")
    print(f"📊 全部完成  共 {total} 张  ✅ {ok}  ❌ {fail}  ⚠️ {error}{to_str}  ⏱ {total_time:.1f}s")
    if dry:
        print("   （预览模式，未执行文件操作）")
    return {"ok": ok, "fail": fail, "error": error, "timeout": timeout_count, "total": total}


def _run_batch_move(images: List[Path], ok_dir: Path, fail_dir: Path, dry: bool, timeout: float | None = None,
                    log_data: dict | None = None, base_dir: Path | None = None) -> dict:
    """移动归档模式（旧行为）: 成功→识别正确/，失败→未识别/。"""
    total = len(images)
    ok = fail = error = timeout_count = 0
    t0 = time.time()
    pending: List[Path] = []
    reserved_ok_names: set[str] = set()
    reserved_fail_names: set[str] = set()
    workers = max(1, min(4, os.cpu_count() or 1))
    no_mkdir = not dry  # dry-run 时不创建目录

    # ━━━ 第一轮：快速扫描 ━━━
    print(f"⚡ 第一轮 · 快速扫描  共 {total} 张  {'(预览模式)' if dry else ''}\n")
    r1 = BatchReporter("快扫")

    with ThreadPoolExecutor(max_workers=min(workers, total)) as executor:
        futures = [executor.submit(_process_one_timed, src, False, r1.step, timeout) for src in images]
        for i, future in enumerate(as_completed(futures), 1):
            src, outcome, elapsed = future.result()
            tag = f"[{i}/{total}]"

            if outcome.status == "ok":
                dst = ensure_unique_path(ok_dir, outcome.final_value, src.suffix.lower(), reserved_ok_names, mkdir=no_mkdir)
                _move(src, dst, dry)
                ok += 1
                r1.line(f"  ✅ {tag} {src.name} → 识别正确/{dst.name}  ({outcome.final_value})  {elapsed:.1f}s")
            elif outcome.status in ("error", "timeout"):
                if outcome.status == "timeout":
                    timeout_count += 1
                    symbol = "⏰"
                else:
                    dst = ensure_unique_path(fail_dir, src.stem, src.suffix.lower(), reserved_fail_names, mkdir=no_mkdir)
                    _move(src, dst, dry)
                    error += 1
                    symbol = "⚠️"
                note = outcome.error_note or "图片无法读取"
                r1.line(f"  {symbol} {tag} {src.name}  {note}  {elapsed:.1f}s")
            else:
                pending.append(src)
                r1.line(f"  ⏳ {tag} {src.name}  待深度扫描  {elapsed:.1f}s")

    round1_time = time.time() - t0
    to_str = f"  ⏰ {timeout_count}" if timeout_count else ""
    print(f"\n{'─'*44}")
    print(f"⚡ 第一轮完成  ✅ {ok}  ⏳ 待深度 {len(pending)}  ⚠️ {error}{to_str}  ⏱ {round1_time:.1f}s")

    # ━━━ 第二轮：深度扫描 ━━━
    if pending:
        print(f"\n🔬 第二轮 · 深度扫描  共 {len(pending)} 张\n")
        t1 = time.time()
        active_pending = [src for src in pending if src.exists()]
        r2 = BatchReporter("深扫")
        with ThreadPoolExecutor(max_workers=min(workers, len(active_pending) or 1)) as executor:
            futures = [executor.submit(_process_one_timed, src, True, r2.step, timeout) for src in active_pending]
            for i, future in enumerate(as_completed(futures), 1):
                src, outcome, elapsed = future.result()
                tag = f"[{i}/{len(active_pending)}]"

                if outcome.status == "ok":
                    dst = ensure_unique_path(ok_dir, outcome.final_value, src.suffix.lower(), reserved_ok_names, mkdir=no_mkdir)
                    _move(src, dst, dry)
                    ok += 1
                    r2.line(f"  ✅ {tag} {src.name} → 识别正确/{dst.name}  ({outcome.final_value})  {elapsed:.1f}s")
                elif outcome.status == "timeout":
                    timeout_count += 1
                    r2.line(f"  ⏰ {tag} {src.name}  {outcome.error_note}  {elapsed:.1f}s")
                elif outcome.status == "error":
                    dst = ensure_unique_path(fail_dir, src.stem, src.suffix.lower(), reserved_fail_names, mkdir=no_mkdir)
                    _move(src, dst, dry)
                    error += 1
                    note = outcome.error_note or "图片无法读取"
                    r2.line(f"  ⚠️ {tag} {src.name}  {note}，已归入未识别  {elapsed:.1f}s")
                else:
                    dst = ensure_unique_path(fail_dir, src.stem, src.suffix.lower(), reserved_fail_names, mkdir=no_mkdir)
                    _move(src, dst, dry)
                    fail += 1
                    r2.line(f"  ❌ {tag} {src.name} → 未识别/{dst.name}  {_fail_reason(outcome)}  {elapsed:.1f}s")

        round2_time = time.time() - t1
        to_str = f"  ⏰ {timeout_count}" if timeout_count else ""
        print(f"\n{'─'*44}")
        print(f"🔬 第二轮完成  ✅ {ok}  ❌ {fail}  ⚠️ {error}{to_str}  ⏱ {round2_time:.1f}s")

    total_time = time.time() - t0
    to_str = f"  ⏰ {timeout_count}" if timeout_count else ""
    print(f"\n{'━'*44}")
    print(f"📊 全部完成  共 {total} 张  ✅ {ok}  ❌ {fail}  ⚠️ {error}{to_str}  ⏱ {total_time:.1f}s")
    if dry:
        print("   （预览模式，未移动文件）")
    return {"ok": ok, "fail": fail, "error": error, "timeout": timeout_count, "total": total}


def _run_batch_pair(images: List[Path], input_dir: Path, dry: bool, timeout: float | None = None,
                    marker: str = "X", log_data: dict | None = None, base_dir: Path | None = None) -> dict:
    """配对模式: 先扫描所有图片，再按票据+卸货配对命名。"""
    total = len(images)
    t0 = time.time()
    timeout_count = 0
    workers = max(1, min(4, os.cpu_count() or 1))

    # ── 预分类: X/T 前缀文件跳过扫描 ────────────────────
    skip_files: dict[Path, str] = {}   # path → ftype (unload/pallet)
    scan_images: List[Path] = []
    for src in images:
        ftype = classify_by_prefix(src.name)
        if ftype != "normal":
            skip_files[src] = ftype
        else:
            scan_images.append(src)

    scan_count = len(scan_images)
    skip_count = len(skip_files)
    print(f"🔗 配对模式  共 {total} 张  (扫描 {scan_count}, X/T跳过 {skip_count})  {'(预览模式)' if dry else ''}\n")

    # ── 第一阶段: 扫描非 X/T 文件（两轮）────────────────
    scan_results: dict[Path, str] = {}  # path → code_or_empty
    pending: List[Path] = []

    if scan_images:
        print(f"⚡ 第一轮 · 快速扫描  ({scan_count} 张)\n")
        r1 = BatchReporter("快扫")
        with ThreadPoolExecutor(max_workers=min(workers, scan_count)) as executor:
            futures = [executor.submit(_process_one_timed, src, False, r1.step, timeout) for src in scan_images]
            for i, future in enumerate(as_completed(futures), 1):
                src, outcome, elapsed = future.result()
                tag = f"[{i}/{scan_count}]"
                if outcome.status == "ok":
                    scan_results[src] = outcome.final_value
                    r1.line(f"  ✅ {tag} {src.name}  → {outcome.final_value}  {elapsed:.1f}s")
                elif outcome.status == "timeout":
                    timeout_count += 1
                    scan_results[src] = ""
                    r1.line(f"  ⏰ {tag} {src.name}  {outcome.error_note}  {elapsed:.1f}s")
                elif outcome.status == "error":
                    scan_results[src] = ""
                    r1.line(f"  ⚠️ {tag} {src.name}  {outcome.error_note or '图片无法读取'}  {elapsed:.1f}s")
                else:
                    pending.append(src)
                    r1.line(f"  ⏳ {tag} {src.name}  待深度扫描  {elapsed:.1f}s")

        if pending:
            print(f"\n🔬 第二轮 · 深度扫描  共 {len(pending)} 张\n")
            active_pending = [src for src in pending if src.exists()]
            r2 = BatchReporter("深扫")
            with ThreadPoolExecutor(max_workers=min(workers, len(active_pending) or 1)) as executor:
                futures = [executor.submit(_process_one_timed, src, True, r2.step, timeout) for src in active_pending]
                for i, future in enumerate(as_completed(futures), 1):
                    src, outcome, elapsed = future.result()
                    tag = f"[{i}/{len(active_pending)}]"
                    if outcome.status == "ok":
                        scan_results[src] = outcome.final_value
                        r2.line(f"  ✅ {tag} {src.name}  → {outcome.final_value}  {elapsed:.1f}s")
                    elif outcome.status == "timeout":
                        timeout_count += 1
                        scan_results[src] = ""
                        r2.line(f"  ⏰ {tag} {src.name}  {outcome.error_note}  {elapsed:.1f}s")
                    else:
                        scan_results[src] = ""
                        r2.line(f"  ❌ {tag} {src.name}  未识别  {elapsed:.1f}s")

    if skip_count:
        role_map = {"unload": "卸货", "pallet": "托盘"}
        print(f"\n⏭️ 跳过扫描 {skip_count} 张 (X/T前缀，重命名规则待定):")
        for src, ftype in skip_files.items():
            print(f"  📋 {src.name}  ({role_map.get(ftype, ftype)})")

    # ── 第二阶段: 配对命名（仅普通文件参与）──────────────
    print(f"\n{'─'*44}")
    print(f"🔗 配对分析...\n")

    ordered = [(src, scan_results.get(src, "")) for src in sorted(scan_images)]
    assignments = assign_pairs(ordered, marker=marker)

    for a in assignments:
        if a.role == "ticket":
            print(f"  📄 {a.source.name} → {a.new_name}  (票据)")
        elif a.role == "unload":
            print(f"  📸 {a.source.name} → {a.new_name}  (卸货照片, 配对: {a.paired_code})")
        elif a.role == "pallet":
            print(f"  📦 {a.source.name} → {a.new_name}  (共享托盘, 配对: {a.paired_code})")
        else:
            print(f"  ⚠️ {a.source.name}  {a.note}")

    tickets, unloads, unmatched = execute_pair_rename(assignments, dry_run=dry)

    # 记录扫描日志
    for a in assignments:
        rel = _log_rel(a.source, base_dir)
        if a.role in ("ticket", "unload"):
            record_result(log_data, rel, "ok", a.paired_code, a.new_name)
        else:
            record_result(log_data, rel, "unmatched")

    total_time = time.time() - t0
    to_str = f"  ⏰ {timeout_count}" if timeout_count else ""
    skip_str = f"  📋 X/T跳过 {skip_count}" if skip_count else ""
    print(f"\n{'━'*44}")
    print(f"📊 配对完成  📄 票据 {tickets}  📸 卸货 {unloads}  ⚠️ 未配对 {unmatched}{skip_str}{to_str}  ⏱ {total_time:.1f}s")
    if dry:
        print("   （预览模式，未执行文件操作）")
    return {"ok": tickets + unloads, "fail": unmatched, "error": 0, "timeout": timeout_count, "total": total}


def _unique_name(src: Path, code: str, reserved: set[str]) -> str:
    """生成不重复的文件名。"""
    suffix = src.suffix.lower()
    name = f"{code}{suffix}"
    if name not in reserved:
        reserved.add(name)
        return name
    idx = 1
    while True:
        name = f"{code}_{idx}{suffix}"
        if name not in reserved:
            reserved.add(name)
            return name
        idx += 1
