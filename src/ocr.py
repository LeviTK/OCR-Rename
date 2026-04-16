from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import List

from PIL import Image, ImageOps

from .models import DecodeHit
from .utils import normalize_numeric_value


_tessdata_dir = os.environ.get("TESSDATA_PREFIX", "")
_tesseract_warned = False


def _tesseract_available() -> bool:
    return shutil.which("tesseract") is not None


def _check_tessdata(lang: str) -> bool:
    """检查 tessdata 目录中是否存在所需的训练数据文件。"""
    global _tesseract_warned
    if not _tessdata_dir:
        return True  # 没有指定目录时，依赖系统默认路径
    for single_lang in lang.split("+"):
        data_file = Path(_tessdata_dir) / f"{single_lang}.traineddata"
        if not data_file.is_file():
            if not _tesseract_warned:
                _tesseract_warned = True
                import sys
                print(
                    f"⚠️ OCR 训练数据缺失: {data_file}，OCR 兜底将不可用",
                    file=sys.stderr,
                    flush=True,
                )
            return False
    return True


def _ocr_text(img: Image.Image, lang: str) -> str:
    if not _tesseract_available():
        return ""
    if not _check_tessdata(lang):
        return ""
    with ImageOps.exif_transpose(img) as normalized:
        enlarged = normalized.resize((normalized.width * 2, normalized.height * 2), Image.Resampling.LANCZOS)
        gray = ImageOps.grayscale(enlarged)
        auto = ImageOps.autocontrast(gray)
        cmd = ["tesseract", "stdin", "stdout", "--psm", "6", "-l", lang]
        if _tessdata_dir:
            cmd.extend(["--tessdata-dir", _tessdata_dir])
        try:
            with subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            ) as proc:
                assert proc.stdin is not None and proc.stdout is not None
                auto.save(proc.stdin, format="PNG")
                proc.stdin.close()
                out = proc.stdout.read().decode("utf-8", errors="ignore")
                stderr_out = proc.stderr.read().decode("utf-8", errors="ignore") if proc.stderr else ""
                proc.wait(timeout=30)
                if proc.returncode != 0:
                    import sys
                    print(
                        f"⚠️ Tesseract 退出码 {proc.returncode}: {stderr_out.strip()[:200]}",
                        file=sys.stderr,
                        flush=True,
                    )
                    return ""
                return out
        except (OSError, subprocess.TimeoutExpired) as exc:
            import sys
            print(f"⚠️ Tesseract 调用失败: {exc}", file=sys.stderr, flush=True)
            return ""


def _extract_candidates(text: str) -> List[tuple[str, int, str]]:
    compact = re.sub(r"\s+", "", text)
    out: List[tuple[str, int, str]] = []
    seen: set[str] = set()

    patterns = [
        (r"发货单号[：:;]?([0-9]{10,20})", 130, "keyword_strict"),
        (r"发货单号[^0-9]{0,12}([0-9]{10,20})", 115, "keyword_loose"),
        (r"销售出库单[^0-9]{0,20}([0-9]{10,20})", 90, "title_near"),
    ]
    for pattern, score, source in patterns:
        for m in re.finditer(pattern, compact):
            value = normalize_numeric_value(m.group(1))
            if value and value not in seen:
                seen.add(value)
                out.append((value, score + 20, source))

    for m in re.finditer(r"49[0-9]{8,16}", compact):
        value = normalize_numeric_value(m.group(0))
        if value and value not in seen:
            seen.add(value)
            out.append((value, 55 + (20 if value.startswith("4920") else 0), "digits"))
    return out


def scan_fallback(img: Image.Image, rotation: int, lang: str) -> List[DecodeHit]:
    text = _ocr_text(img, lang)
    if not text:
        return []
    return [
        DecodeHit("ocr", value, rotation, "full_ocr", source, score)
        for value, score, source in _extract_candidates(text)
    ]
