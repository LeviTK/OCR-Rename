from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
ROTATIONS = (0, 90, 180, 270)


@dataclass
class DecodeHit:
    kind: str  # barcode | qrcode | ocr
    value: str
    rotation: int
    variant: str
    source: str
    weight: int


@dataclass
class ProcessResult:
    status: str
    source: Path
    destination: Path
    final_value: str = ""
    barcode_value: str = ""
    qr_value: str = ""
    note: str = ""
    hits: List[DecodeHit] = field(default_factory=list)


class PipelineError(Exception):
    pass
