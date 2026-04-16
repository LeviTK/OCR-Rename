from __future__ import annotations

import argparse
import os
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
from .qrcode_scan import scan as scan_qr
from .utils import normalize_numeric_value, rotate_pil

_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_INPUT = _ROOT / "001-Pic"

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
    for hit in hits:
        if kind is not None and hit.kind != kind:
            continue
        value = normalize_numeric_value(hit.value)
        if value:
            seen[value] = seen.get(value, 0) + hit.weight
    return sorted(seen.items(), key=lambda item: (-item[1], item[0]))


def _choose_final_value(hits: Sequence[DecodeHit]) -> str:
    barcode_rank = _rank_hits(hits, "barcode")
    qr_rank = _rank_hits(hits, "qrcode")

    barcode_scores = dict(barcode_rank)
    qr_scores = dict(qr_rank)
    common = sorted(
        (
            (value, barcode_scores[value] + qr_scores[value])
            for value in barcode_scores.keys() & qr_scores.keys()
        ),
        key=lambda item: (-item[1], item[0]),
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
    return sorted(merged.items(), key=lambda item: (-item[1], item[0]))[0][0]


def _scan_region_fast(img: Image.Image) -> List[DecodeHit]:
    w, h = img.size
    rotations = (0, 180) if w >= h else (90, 270)
    hits: List[DecodeHit] = []

    for rotation in rotations:
        rotated = rotate_pil(img, rotation)
        hits.extend(scan_barcodes(rotated, rotation))
        hits.extend(scan_qr(rotated, rotation, deep=False))
    return hits


def _scan_region_deep_qr(img: Image.Image) -> List[DecodeHit]:
    w, h = img.size
    rotations = (0, 180) if w >= h else (90, 270)
    hits: List[DecodeHit] = []

    for rotation in rotations:
        rotated = rotate_pil(img, rotation)
        hits.extend(scan_qr(rotated, rotation, deep=True))
    return hits


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
        final_value = _choose_final_value(hits + half_hits + deep_hits)
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
) -> tuple[Path, ProcessOutcome, float]:
    started = time.time()
    try:
        outcome = process_one(src, deep=deep, progress=progress)
    except Exception as exc:
        outcome = ProcessOutcome(
            status="error",
            error_note=f"处理异常: {type(exc).__name__}: {exc}",
        )
    return src, outcome, time.time() - started


def _resolve_input_dir(args: argparse.Namespace) -> Path:
    if getattr(args, "input", None):
        return Path(args.input).resolve()
    return _DEFAULT_INPUT


def _rename_in_place(src: Path, new_name: str, dry: bool) -> Path:
    dst = src.parent / new_name
    if dst == src:
        return src
    if dry:
        return dst
    base_stem = dst.stem
    suffix = dst.suffix
    idx = 1
    while dst.exists() and dst != src:
        dst = src.parent / f"{base_stem}_{idx}{suffix}"
        idx += 1
    src.rename(dst)
    return dst


def _unique_name(src: Path, code: str, reserved: set[str]) -> str:
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


def _fail_reason(outcome: ProcessOutcome) -> str:
    reason = "二维码和条形码都未识别出有效数字"
    if outcome.ocr_hint:
        reason += f"  OCR候选={outcome.ocr_hint}"
    return reason


def _run_batch_rename(images: List[Path], dry: bool) -> dict[str, int]:
    total = len(images)
    ok = fail = error = 0
    pending: List[Path] = []
    reserved_names: set[str] = set()
    workers = max(1, min(4, os.cpu_count() or 1, total))
    started = time.time()

    print(f"⚡ 第一轮 · 快速扫描  共 {total} 张  {'(预览模式)' if dry else ''}\n")
    reporter = BatchReporter("快扫")
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(_process_one_timed, src, False, reporter.step) for src in images]
        for index, future in enumerate(as_completed(futures), 1):
            src, outcome, elapsed = future.result()
            tag = f"[{index}/{total}]"

            if outcome.status == "ok":
                new_name = _unique_name(src, outcome.final_value, reserved_names)
                dst = _rename_in_place(src, new_name, dry)
                ok += 1
                reporter.line(f"  ✅ {tag} {src.name} → {dst.name}  ({outcome.final_value})  {elapsed:.1f}s")
            elif outcome.status == "error":
                error += 1
                note = outcome.error_note or "图片无法读取"
                reporter.line(f"  ⚠️ {tag} {src.name}  {note}  {elapsed:.1f}s")
            else:
                pending.append(src)
                reporter.line(f"  ⏳ {tag} {src.name}  待深度扫描  {elapsed:.1f}s")

    round1_time = time.time() - started
    print(f"\n{'─' * 44}")
    print(f"⚡ 第一轮完成  ✅ {ok}  ⏳ 待深度 {len(pending)}  ⚠️ {error}  ⏱ {round1_time:.1f}s")

    if pending:
        print(f"\n🔬 第二轮 · 深度扫描  共 {len(pending)} 张\n")
        round2_started = time.time()
        reporter = BatchReporter("深扫")
        with ThreadPoolExecutor(max_workers=max(1, min(workers, len(pending)))) as executor:
            futures = [executor.submit(_process_one_timed, src, True, reporter.step) for src in pending if src.exists()]
            for index, future in enumerate(as_completed(futures), 1):
                src, outcome, elapsed = future.result()
                tag = f"[{index}/{len(pending)}]"

                if outcome.status == "ok":
                    new_name = _unique_name(src, outcome.final_value, reserved_names)
                    dst = _rename_in_place(src, new_name, dry)
                    ok += 1
                    reporter.line(f"  ✅ {tag} {src.name} → {dst.name}  ({outcome.final_value})  {elapsed:.1f}s")
                elif outcome.status == "error":
                    error += 1
                    note = outcome.error_note or "图片无法读取"
                    reporter.line(f"  ⚠️ {tag} {src.name}  {note}  {elapsed:.1f}s")
                else:
                    fail += 1
                    reporter.line(f"  ❌ {tag} {src.name}  {_fail_reason(outcome)}  {elapsed:.1f}s")

        round2_time = time.time() - round2_started
        print(f"\n{'─' * 44}")
        print(f"🔬 第二轮完成  ✅ {ok}  ❌ {fail}  ⚠️ {error}  ⏱ {round2_time:.1f}s")

    total_time = time.time() - started
    print(f"\n{'━' * 44}")
    print(f"📊 全部完成  共 {total} 张  ✅ {ok}  ❌ {fail}  ⚠️ {error}  ⏱ {total_time:.1f}s")
    if dry:
        print("   （预览模式，未执行文件操作）")
    return {"ok": ok, "fail": fail, "error": error, "total": total}


def run_batch(args: argparse.Namespace) -> int:
    input_dir = _resolve_input_dir(args)
    dry = getattr(args, "dry_run", False)

    if not input_dir.is_dir():
        print(f"❌ 源目录不存在: {input_dir}")
        return 1

    images = sorted(
        path for path in input_dir.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTS
    )
    if not images:
        print(f"📂 {input_dir.name}/ 中没有待识别图片")
        return 0

    _run_batch_rename(images, dry)
    return 0
