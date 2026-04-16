from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Sequence

from .models import DecodeHit, ProcessResult
from .utils import ensure_unique_path


def _aggregate(hits: Sequence[DecodeHit], kind: str) -> List[tuple[str, int, List[DecodeHit]]]:
    bucket: dict[str, List[DecodeHit]] = {}
    for hit in hits:
        if hit.kind != kind:
            continue
        bucket.setdefault(hit.value, []).append(hit)
    ranked = [(v, sum(h.weight for h in g), g) for v, g in bucket.items()]
    ranked.sort(key=lambda x: (-x[1], x[0]))
    return ranked


def _note_for(kind_rank: List[tuple[str, int, List[DecodeHit]]]) -> str:
    parts = []
    for value, score, grouped in kind_rank[:3]:
        s = grouped[0]
        parts.append(f"{value}@{score}[rot={s.rotation} {s.variant}]")
    return "; ".join(parts)


def choose_result(
    src: Path,
    root: Path,
    args: argparse.Namespace,
    hits: Sequence[DecodeHit],
) -> ProcessResult:
    barcode_rank = _aggregate(hits, "barcode")
    qr_rank = _aggregate(hits, "qrcode")
    ocr_rank = _aggregate(hits, "ocr")

    best_barcode = barcode_rank[0][0] if barcode_rank else ""
    best_qr = qr_rank[0][0] if qr_rank else ""
    best_ocr = ocr_rank[0][0] if ocr_rank else ""

    suffix = src.suffix.lower()
    success_dir = root / args.success_dir
    conflict_dir = root / args.conflict_dir
    failed_dir = root / args.failed_dir

    if best_barcode and best_qr:
        if best_barcode == best_qr:
            return ProcessResult(
                status="both_match",
                source=src,
                destination=ensure_unique_path(success_dir, best_barcode, suffix),
                final_value=best_barcode,
                barcode_value=best_barcode,
                qr_value=best_qr,
                note=f"barcode={_note_for(barcode_rank)} | qr={_note_for(qr_rank)}",
                hits=list(hits),
            )
        return ProcessResult(
            status="conflict",
            source=src,
            destination=ensure_unique_path(conflict_dir, src.stem, suffix),
            barcode_value=best_barcode,
            qr_value=best_qr,
            note=f"barcode={_note_for(barcode_rank)} | qr={_note_for(qr_rank)}",
            hits=list(hits),
        )

    if best_barcode:
        return ProcessResult(
            status="barcode_only",
            source=src,
            destination=ensure_unique_path(success_dir, best_barcode, suffix),
            final_value=best_barcode,
            barcode_value=best_barcode,
            note=f"barcode={_note_for(barcode_rank)}",
            hits=list(hits),
        )

    if best_qr:
        return ProcessResult(
            status="qr_only",
            source=src,
            destination=ensure_unique_path(success_dir, best_qr, suffix),
            final_value=best_qr,
            qr_value=best_qr,
            note=f"qr={_note_for(qr_rank)}",
            hits=list(hits),
        )

    if args.ocr_fallback and best_ocr:
        return ProcessResult(
            status="ocr_fallback",
            source=src,
            destination=ensure_unique_path(success_dir, best_ocr, suffix),
            final_value=best_ocr,
            note=f"ocr={_note_for(ocr_rank)}",
            hits=list(hits),
        )

    return ProcessResult(
        status="unrecognized",
        source=src,
        destination=ensure_unique_path(failed_dir, src.stem, suffix),
        note="barcode/qr/ocr 均无有效结果",
        hits=list(hits),
    )
