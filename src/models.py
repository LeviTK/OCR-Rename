from __future__ import annotations

from dataclasses import dataclass

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}


@dataclass
class DecodeHit:
    kind: str  # barcode | qrcode | ocr
    value: str
    rotation: int
    variant: str
    source: str
    weight: int
