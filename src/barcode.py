from __future__ import annotations

from typing import List

import cv2
import numpy as np
from PIL import Image, ImageOps

from .models import DecodeHit
from .utils import normalize_numeric_value, pil_to_bgr, suppress_stderr_fd2

try:
    import zxingcpp  # type: ignore
except Exception:
    zxingcpp = None

try:
    from pyzbar.pyzbar import decode as zbar_decode
except Exception:
    zbar_decode = None

MAX_BARCODE_EDGE = 2000


def _limit(img: np.ndarray) -> np.ndarray:
    h, w = img.shape[:2]
    if max(h, w) <= MAX_BARCODE_EDGE:
        return img
    r = MAX_BARCODE_EDGE / max(h, w)
    return cv2.resize(img, (int(w * r), int(h * r)), interpolation=cv2.INTER_AREA)


def _decode_zxing(gray: np.ndarray) -> List[tuple[str, str]]:
    """用 zxingcpp 解码所有条形码（极快，无 WARNING）。"""
    if zxingcpp is None:
        return []
    try:
        results = zxingcpp.read_barcodes(gray)
        out = []
        for r in results:
            fmt = str(r.format).replace("BarcodeFormat.", "")
            if "QR" in fmt:
                continue  # QR 交给 qrcode_scan 处理
            v = normalize_numeric_value(r.text)
            if v:
                out.append((fmt, v))
        return out
    except Exception:
        return []


def _decode_pyzbar(img: Image.Image) -> List[tuple[str, str]]:
    """pyzbar 兜底（抑制 WARNING 输出）。"""
    if zbar_decode is None:
        return []
    with suppress_stderr_fd2():
        results = []
        for item in zbar_decode(img):
            try:
                data = item.data.decode("utf-8", errors="ignore")
            except Exception:
                data = str(item.data)
            v = normalize_numeric_value(data)
            if v:
                results.append((item.type, v))
        return results


def scan(img: Image.Image, rotation: int) -> List[DecodeHit]:
    hits: List[DecodeHit] = []
    bgr = _limit(pil_to_bgr(img))
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

    # ① zxingcpp 快速全图扫描（一次调用找所有条形码）
    for fmt, value in _decode_zxing(gray):
        weight = 100
        if value.isdigit() and 8 <= len(value) <= 20:
            weight += 50
        if len(value) == 10 and value.isdigit():
            weight += 20
        hits.append(DecodeHit("barcode", value, rotation, "full", fmt, weight))

    if hits:
        return hits

    # ② 增强后再试一次 zxingcpp
    auto = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(auto)
    for fmt, value in _decode_zxing(clahe):
        weight = 90
        if value.isdigit() and 8 <= len(value) <= 20:
            weight += 50
        hits.append(DecodeHit("barcode", value, rotation, "full/clahe", fmt, weight))

    if hits:
        return hits

    # ③ pyzbar 兜底：只用灰度全图（抑制 WARNING）
    gray_pil = ImageOps.autocontrast(ImageOps.grayscale(img))
    for btype, value in _decode_pyzbar(gray_pil):
        weight = 80
        if value.isdigit() and 8 <= len(value) <= 20:
            weight += 50
        hits.append(DecodeHit("barcode", value, rotation, "full/pyzbar", btype, weight))

    return hits
