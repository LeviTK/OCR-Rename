from __future__ import annotations

import argparse
import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from src import pipeline
from src.models import DecodeHit


class PipelineTest(unittest.TestCase):
    def test_process_one_scans_numeric_filename_without_special_case(self) -> None:
        original_barcode = pipeline.scan_barcodes
        original_qr = pipeline.scan_qr

        def fake_barcode(img, rotation):
            if rotation == 0:
                return [DecodeHit("barcode", "4920000001", rotation, "full", "fake", 100)]
            return []

        def fake_qr(img, rotation, deep=False):
            return []

        pipeline.scan_barcodes = fake_barcode
        pipeline.scan_qr = fake_qr
        try:
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "0202932895.jpg"
                Image.new("RGB", (100, 100), "white").save(path)
                outcome = pipeline.process_one(path, deep=False)
                self.assertEqual(outcome.status, "ok")
                self.assertEqual(outcome.final_value, "4920000001")
        finally:
            pipeline.scan_barcodes = original_barcode
            pipeline.scan_qr = original_qr

    def test_fast_scan_aggregates_across_rotations(self) -> None:
        original_barcode = pipeline.scan_barcodes
        original_qr = pipeline.scan_qr

        def fake_barcode(img, rotation):
            if rotation == 0:
                return [DecodeHit("barcode", "4920000001", rotation, "full", "fake", 100)]
            if rotation == 180:
                return [DecodeHit("barcode", "4920000002", rotation, "full", "fake", 100)]
            return []

        def fake_qr(img, rotation, deep=False):
            if rotation == 180:
                return [DecodeHit("qrcode", "4920000002", rotation, "full", "fake", 180)]
            return []

        pipeline.scan_barcodes = fake_barcode
        pipeline.scan_qr = fake_qr
        try:
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "sample.jpg"
                Image.new("RGB", (1200, 800), "white").save(path)
                outcome = pipeline.process_one(path, deep=False)
                self.assertEqual(outcome.status, "ok")
                self.assertEqual(outcome.final_value, "4920000002")
        finally:
            pipeline.scan_barcodes = original_barcode
            pipeline.scan_qr = original_qr

    def test_run_batch_continues_after_single_image_exception(self) -> None:
        call_count = 0

        def fake_process_one_timed(src, deep, progress=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return src, pipeline.ProcessOutcome(status="error", error_note="处理异常: RuntimeError: boom"), 0.1
            return src, pipeline.ProcessOutcome(status="ok", final_value="4920000001"), 0.1

        with tempfile.TemporaryDirectory() as tmp:
            src_dir = Path(tmp)
            Image.new("RGB", (100, 100), "white").save(src_dir / "a.jpg")
            Image.new("RGB", (100, 100), "white").save(src_dir / "b.jpg")

            with patch.object(pipeline, "_process_one_timed", fake_process_one_timed):
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    code = pipeline.run_batch(argparse.Namespace(dry_run=True, input=str(src_dir)))
                output = buf.getvalue()

            self.assertEqual(code, 0)
            self.assertIn("处理异常: RuntimeError: boom", output)
            self.assertIn("✅ 1", output)

    def test_dry_run_reserves_duplicate_target_names(self) -> None:
        def fake_process_one_timed(src, deep, progress=None):
            return src, pipeline.ProcessOutcome(status="ok", final_value="4920604114"), 0.1

        with tempfile.TemporaryDirectory() as tmp:
            src_dir = Path(tmp)
            Image.new("RGB", (100, 100), "white").save(src_dir / "a.jpg")
            Image.new("RGB", (100, 100), "white").save(src_dir / "b.jpg")

            with patch.object(pipeline, "_process_one_timed", fake_process_one_timed):
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    code = pipeline.run_batch(argparse.Namespace(dry_run=True, input=str(src_dir)))
                output = buf.getvalue()

            self.assertEqual(code, 0)
            self.assertIn("4920604114.jpg", output)
            self.assertIn("4920604114_1.jpg", output)

    def test_run_batch_renames_detected_files(self) -> None:
        def fake_process_one_timed(src, deep, progress=None):
            return src, pipeline.ProcessOutcome(status="ok", final_value="4920000001"), 0.1

        with tempfile.TemporaryDirectory() as tmp:
            src_dir = Path(tmp)
            Image.new("RGB", (100, 100), "white").save(src_dir / "sample.jpg")

            with patch.object(pipeline, "_process_one_timed", fake_process_one_timed):
                code = pipeline.run_batch(argparse.Namespace(dry_run=False, input=str(src_dir)))

            self.assertEqual(code, 0)
            self.assertFalse((src_dir / "sample.jpg").exists())
            self.assertTrue((src_dir / "4920000001.jpg").exists())

    def test_run_batch_returns_error_for_missing_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing"
            code = pipeline.run_batch(argparse.Namespace(dry_run=True, input=str(missing)))
            self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
