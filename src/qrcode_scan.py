from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Optional

import cv2
import numpy as np
from PIL import Image

from .models import DecodeHit
from .utils import normalize_numeric_value, pil_to_bgr, suppress_stderr_fd2

try:
    import zxingcpp  # type: ignore
except Exception:  # pragma: no cover
    zxingcpp = None

try:
    from pyzbar.pyzbar import decode as zbar_decode
except Exception:  # pragma: no cover
    zbar_decode = None

MAX_QR_EDGE = 2000
_qr_detector = cv2.QRCodeDetector()
_SHARP_KERNEL = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]])


def _limit_size(img: np.ndarray) -> np.ndarray:
    h, w = img.shape[:2]
    if max(h, w) <= MAX_QR_EDGE:
        return img
    ratio = MAX_QR_EDGE / max(h, w)
    return cv2.resize(img, (int(w * ratio), int(h * ratio)), interpolation=cv2.INTER_AREA)


def _rois(img: np.ndarray) -> Iterable[tuple[str, np.ndarray]]:
    h, w = img.shape[:2]
    regions = {
        "top_right": (int(w * 0.45), 0, w, int(h * 0.45)),
        "top_left": (0, 0, int(w * 0.55), int(h * 0.45)),
        "full": (0, 0, w, h),
    }
    for name, (x1, y1, x2, y2) in regions.items():
        roi = img[y1:y2, x1:x2]
        if roi.shape[0] < 60 or roi.shape[1] < 60:
            continue
        yield name, roi


def _color_separate_blue(roi: np.ndarray) -> List[tuple[str, np.ndarray]]:
    lab = cv2.cvtColor(roi, cv2.COLOR_BGR2Lab)
    return [
        ("gray", cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)),
        ("lab_b_inv", 255 - lab[:, :, 2]),
    ]


def _background_correct(gray: np.ndarray) -> List[tuple[str, np.ndarray]]:
    bg = cv2.GaussianBlur(gray, (51, 51), 0)
    return [
        ("raw", gray),
        ("sub51", cv2.normalize(cv2.subtract(gray, bg), None, 0, 255, cv2.NORM_MINMAX)),
    ]


def _binarize(gray: np.ndarray) -> Iterable[tuple[str, np.ndarray]]:
    _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    yield "otsu", otsu
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8)).apply(gray)
    _, cotsu = cv2.threshold(clahe, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    yield "clahe_otsu", cotsu
    if min(gray.shape[:2]) > 31:
        bw = cv2.adaptiveThreshold(clahe, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 8)
        yield "gauss_31_8", bw


# ── 解码函数 ────────────────────────────────────────────────────────

def _decode_fast(img: np.ndarray) -> Optional[str]:
    """快速解码：只用 zxingcpp（最快）+ cv2，跳过慢速 pyzbar。"""
    if zxingcpp is not None:
        try:
            results = zxingcpp.read_barcodes(img, formats=zxingcpp.BarcodeFormat.QRCode)
            if results:
                return normalize_numeric_value(results[0].text)
        except Exception:
            pass
    try:
        text, pts, _ = _qr_detector.detectAndDecode(img)
        if text:
            return normalize_numeric_value(text)
    except Exception:
        pass
    return None


def _decode_pyzbar(img: np.ndarray) -> Optional[str]:
    """有限次 pyzbar 兜底，并抑制 zbar databar warning。"""
    if zbar_decode is None:
        return None
    with suppress_stderr_fd2():
        pil = Image.fromarray(img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        for item in zbar_decode(pil):
            if item.type == "QRCODE":
                return normalize_numeric_value(item.data.decode("utf-8", errors="ignore"))
    return None


def _decode_full(img: np.ndarray) -> Optional[str]:
    """完整解码：zxingcpp → cv2 → pyzbar，覆盖面最广。"""
    val = _decode_fast(img)
    if val:
        return val
    try:
        return _decode_pyzbar(img)
    except Exception:
        return None
    return None


def _deep_fast_variants(roi: np.ndarray) -> Iterable[tuple[str, np.ndarray]]:
    for ch_name, ch in _color_separate_blue(roi):
        for bg_name, corrected in _background_correct(ch):
            for scale in (2, 3, 4):
                scaled = cv2.resize(corrected, None, fx=scale, fy=scale, interpolation=cv2.INTER_LANCZOS4)
                for bin_name, variant in _binarize(scaled):
                    padded = cv2.copyMakeBorder(variant, 24, 24, 24, 24, cv2.BORDER_CONSTANT, value=255)
                    yield f"{ch_name}/{bg_name}/x{scale}/{bin_name}", padded
                sharp = cv2.filter2D(scaled, -1, _SHARP_KERNEL)
                padded = cv2.copyMakeBorder(sharp, 24, 24, 24, 24, cv2.BORDER_CONSTANT, value=255)
                yield f"{ch_name}/{bg_name}/x{scale}/sharp", padded


def _deep_pyzbar_candidates(roi: np.ndarray) -> Iterable[tuple[str, np.ndarray]]:
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    yield "gray/raw", gray

    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8)).apply(gray)
    yield "gray/clahe", clahe

    scaled = cv2.resize(clahe, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    sharp = cv2.filter2D(scaled, -1, _SHARP_KERNEL)
    yield "gray/clahe/x3/sharp", cv2.copyMakeBorder(sharp, 24, 24, 24, 24, cv2.BORDER_CONSTANT, value=255)

    lab_b_inv = 255 - cv2.cvtColor(roi, cv2.COLOR_BGR2Lab)[:, :, 2]
    scaled_blue = cv2.resize(lab_b_inv, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    yield "lab_b_inv/x3", cv2.copyMakeBorder(scaled_blue, 24, 24, 24, 24, cv2.BORDER_CONSTANT, value=255)
    return None


# ── 主扫描入口 ──────────────────────────────────────────────────────

def scan(
    img: Image.Image,
    rotation: int,
    deep: bool = True,
    save_debug: bool = False,
    debug_dir: Optional[Path] = None,
    stem: str = "",
) -> List[DecodeHit]:
    bgr = _limit_size(pil_to_bgr(img))
    hits: List[DecodeHit] = []

    # ① 快速通道：全图直接解码（高清图秒出）
    value = _decode_fast(bgr)
    if value:
        hits.append(DecodeHit("qrcode", value, rotation, "full/raw", "direct_fast", 180))
        return hits

    # ② 快速通道：灰度放大 + 锐化（低分辨率 / 弧面变形）
    gray_full = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    for scale in (3, 4):
        scaled = cv2.resize(gray_full, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        sharp = cv2.filter2D(scaled, -1, _SHARP_KERNEL)
        padded = cv2.copyMakeBorder(sharp, 30, 30, 30, 30, cv2.BORDER_CONSTANT, value=255)
        value = _decode_fast(padded)
        if value:
            hits.append(DecodeHit("qrcode", value, rotation, f"full/sharp/x{scale}", "quick_sharp", 170))
            return hits

    if not deep:
        return hits

    # ③ 深度扫描：先在 ROI 上跑快速解码器，再用少量 pyzbar 候选兜底
    for roi_name, roi in _rois(bgr):
        direct = _decode_full(roi)
        if direct:
            hits.append(DecodeHit("qrcode", direct, rotation, f"{roi_name}/raw", "direct", 180))
            return hits

        for variant_name, candidate in _deep_fast_variants(roi):
            value = _decode_fast(candidate)
            if value:
                hits.append(DecodeHit(
                    kind="qrcode", value=value, rotation=rotation,
                    variant=f"{roi_name}/{variant_name}",
                    source="deep_scan_fast", weight=140 + (20 if roi_name == "top_right" else 0),
                ))
                return hits

        for variant_name, candidate in _deep_pyzbar_candidates(roi):
            value = _decode_pyzbar(candidate)
            if value:
                hits.append(DecodeHit(
                    kind="qrcode", value=value, rotation=rotation,
                    variant=f"{roi_name}/{variant_name}",
                    source="deep_scan_pyzbar", weight=125 + (20 if roi_name == "top_right" else 0),
                ))
                return hits
    return hits
