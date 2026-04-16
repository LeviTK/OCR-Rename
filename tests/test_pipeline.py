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


class PipelineFixesTest(unittest.TestCase):
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

    def test_batch_continues_after_single_image_exception(self) -> None:
        call_count = 0

        def fake_process_one_timed(src, deep, progress=None, timeout=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return src, pipeline.ProcessOutcome(status="error", error_note="处理异常: RuntimeError: boom"), 0.1
            return src, pipeline.ProcessOutcome(status="ok", final_value="4920000001"), 0.1

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src_dir = root / "001-Pic"
            src_dir.mkdir()
            Image.new("RGB", (100, 100), "white").save(src_dir / "a.jpg")
            Image.new("RGB", (100, 100), "white").save(src_dir / "b.jpg")

            with patch.object(pipeline, "_process_one_timed", fake_process_one_timed):
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    code = pipeline.run_batch(argparse.Namespace(
                        dry_run=True, input=str(src_dir), move=False, pair=False,
                        recursive=False, skip_dirs="", timeout=None,
                        force=True, marker="X",
                    ))
                output = buf.getvalue()

            self.assertEqual(code, 0)
            self.assertIn("处理异常: RuntimeError: boom", output)
            self.assertIn("✅ 1", output)

    def test_dry_run_reserves_duplicate_target_names(self) -> None:
        """两张图识别到相同码值时，dry-run 应生成不同文件名。"""
        call_count = 0

        def fake_process_one_timed(src, deep, progress=None, timeout=None):
            nonlocal call_count
            call_count += 1
            return src, pipeline.ProcessOutcome(status="ok", final_value="4920604114"), 0.1

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src_dir = root / "input"
            src_dir.mkdir()
            Image.new("RGB", (100, 100), "white").save(src_dir / "a.jpg")
            Image.new("RGB", (100, 100), "white").save(src_dir / "b.jpg")

            with patch.object(pipeline, "_process_one_timed", fake_process_one_timed):
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    code = pipeline.run_batch(argparse.Namespace(
                        dry_run=True, input=str(src_dir), move=False, pair=False,
                        recursive=False, skip_dirs="", timeout=None,
                        force=True, marker="X",
                    ))
                output = buf.getvalue()

            self.assertEqual(code, 0)
            self.assertIn("4920604114.jpg", output)
            self.assertIn("4920604114_1.jpg", output)


    def test_dry_run_move_does_not_create_dirs(self) -> None:
        """--dry-run --move 不应在文件系统上创建任何目录。"""
        def fake_process_one_timed(src, deep, progress=None, timeout=None):
            return src, pipeline.ProcessOutcome(status="ok", final_value="4920000001"), 0.1

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src_dir = root / "input"
            src_dir.mkdir()
            Image.new("RGB", (100, 100), "white").save(src_dir / "a.jpg")

            ok_dir = root / "识别正确"
            fail_dir = root / "未识别"

            with patch.object(pipeline, "_process_one_timed", fake_process_one_timed), \
                 patch.object(pipeline, "_DEFAULT_OK_DIR", ok_dir), \
                 patch.object(pipeline, "_DEFAULT_FAIL_DIR", fail_dir):
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    pipeline.run_batch(argparse.Namespace(
                        dry_run=True, input=str(src_dir), move=True, pair=False,
                        recursive=False, skip_dirs="", timeout=None,
                        force=True, marker="X",
                    ))

            self.assertFalse(ok_dir.exists(), "dry-run should not create 识别正确/")
            self.assertFalse(fail_dir.exists(), "dry-run should not create 未识别/")

    def test_recursive_force_rescans_coded_filenames(self) -> None:
        call_count = 0

        def fake_process_one_timed(src, deep, progress=None, timeout=None):
            nonlocal call_count
            call_count += 1
            return src, pipeline.ProcessOutcome(status="ok", final_value="4920000001"), 0.1

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first_dir = root / "a_dir"
            second_dir = root / "b_dir"
            first_dir.mkdir()
            second_dir.mkdir()
            Image.new("RGB", (100, 100), "white").save(first_dir / "sample.jpg")
            Image.new("RGB", (100, 100), "white").save(second_dir / "4920000002.jpg")

            with patch.object(pipeline, "_process_one_timed", fake_process_one_timed):
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    code = pipeline.run_batch(argparse.Namespace(
                        dry_run=True, input=str(root), move=False, pair=False,
                        recursive=True, skip_dirs="", timeout=None,
                        force=True, marker="X",
                    ))
                output = buf.getvalue()

            self.assertEqual(code, 0)
            self.assertEqual(call_count, 2)
            self.assertNotIn("日志跳过", output)

    def test_batch_rename_renames_numeric_filename(self) -> None:
        log_data = {}

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "0202932895.jpg"
            Image.new("RGB", (100, 100), "white").save(path)

            def fake_process_one_timed(src, deep, progress=None, timeout=None):
                return src, pipeline.ProcessOutcome(status="ok", final_value="4920000001"), 0.1

            with patch.object(pipeline, "_process_one_timed", fake_process_one_timed):
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    stats = pipeline._run_batch_rename([path], dry=False, timeout=None, log_data=log_data, base_dir=root)

            self.assertFalse(path.exists())
            self.assertTrue((root / "4920000001.jpg").exists())
            self.assertEqual(stats["ok"], 1)
            self.assertIn("0202932895.jpg", log_data)
            self.assertEqual(log_data["0202932895.jpg"]["status"], "ok")
            self.assertEqual(log_data["0202932895.jpg"]["renamed_to"], "4920000001.jpg")


class PairModeTest(unittest.TestCase):
    def test_pair_assigns_ticket_and_unload(self) -> None:
        from src.pair import assign_pairs

        results = [
            (Path("a_ticket.jpg"), "4920000001"),
            (Path("b_unload.jpg"), ""),
            (Path("c_ticket.jpg"), "4920000002"),
            (Path("d_unload.jpg"), ""),
        ]
        assignments = assign_pairs(results)
        self.assertEqual(len(assignments), 4)
        self.assertEqual(assignments[0].role, "ticket")
        self.assertEqual(assignments[0].new_name, "4920000001.jpg")
        self.assertEqual(assignments[1].role, "unload")
        self.assertEqual(assignments[1].new_name, "4920000001_X.jpg")
        self.assertEqual(assignments[2].role, "ticket")
        self.assertEqual(assignments[2].new_name, "4920000002.jpg")
        self.assertEqual(assignments[3].role, "unload")
        self.assertEqual(assignments[3].new_name, "4920000002_X.jpg")

    def test_pair_unmatched_at_start(self) -> None:
        from src.pair import assign_pairs

        results = [
            (Path("unload_first.jpg"), ""),
            (Path("ticket.jpg"), "4920000001"),
        ]
        assignments = assign_pairs(results)
        self.assertEqual(assignments[0].role, "unmatched")
        self.assertEqual(assignments[1].role, "ticket")

    def test_pair_multiple_unloads(self) -> None:
        from src.pair import assign_pairs

        results = [
            (Path("ticket.jpg"), "4920000001"),
            (Path("unload1.jpg"), ""),
            (Path("unload2.jpg"), ""),
        ]
        assignments = assign_pairs(results)
        self.assertEqual(assignments[1].new_name, "4920000001_X.jpg")
        self.assertEqual(assignments[2].new_name, "4920000001_X_2.jpg")


    def test_pair_classify_by_prefix(self) -> None:
        from src.pair import classify_by_prefix

        self.assertEqual(classify_by_prefix("X_photo.jpg"), "unload")
        self.assertEqual(classify_by_prefix("T_pallet.jpg"), "pallet")
        self.assertEqual(classify_by_prefix("normal.jpg"), "normal")

    def test_pair_pipeline_skips_scan_for_prefix(self) -> None:
        """X/T prefix files should skip scanning and not be renamed."""
        call_count = 0

        def fake_process_one_timed(src, deep, progress=None, timeout=None):
            nonlocal call_count
            call_count += 1
            return src, pipeline.ProcessOutcome(status="ok", final_value="4920000001"), 0.1

        with tempfile.TemporaryDirectory() as tmp:
            src_dir = Path(tmp)
            Image.new("RGB", (100, 100), "white").save(src_dir / "a_ticket.jpg")
            Image.new("RGB", (100, 100), "white").save(src_dir / "X_unload.jpg")
            Image.new("RGB", (100, 100), "white").save(src_dir / "T_pallet.jpg")

            with patch.object(pipeline, "_process_one_timed", fake_process_one_timed):
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    pipeline.run_batch(argparse.Namespace(
                        dry_run=True, input=str(src_dir), move=False, pair=True,
                        recursive=False, skip_dirs="", timeout=None,
                        force=True, marker="X",
                    ))
                output = buf.getvalue()

            # Only ticket image scanned, X/T skipped entirely
            self.assertEqual(call_count, 1)
            self.assertIn("X/T跳过 2", output)
            # X/T files kept original names (not renamed)
            self.assertTrue((src_dir / "X_unload.jpg").exists())
            self.assertTrue((src_dir / "T_pallet.jpg").exists())


class BatchRenameTest(unittest.TestCase):
    def test_validate_detects_duplicate_target(self) -> None:
        from src.batch_rename import validate_mapping

        with tempfile.TemporaryDirectory() as tmp:
            mapping = {"4920000001": "5030000099", "4920000002": "5030000099"}
            valid, conflicts = validate_mapping(mapping, Path(tmp))
            self.assertEqual(len(valid), 0)
            self.assertEqual(len(conflicts), 2)
            self.assertTrue(all(c.status == "dup_target" for c in conflicts))

    def test_validate_detects_file_conflict(self) -> None:
        from src.batch_rename import validate_mapping

        with tempfile.TemporaryDirectory() as tmp:
            existing = Path(tmp) / "5030000099.jpg"
            existing.write_text("dummy")
            mapping = {"4920000001": "5030000099"}
            valid, conflicts = validate_mapping(mapping, Path(tmp))
            self.assertEqual(len(valid), 0)
            self.assertEqual(len(conflicts), 1)

    def test_execute_rename_basic(self) -> None:
        from src.batch_rename import execute_rename

        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "4920000001.jpg").write_text("ticket")
            (d / "4920000001_2.jpg").write_text("unload")

            results = execute_rename({"4920000001": "5030000099"}, d)
            self.assertEqual(results[0].status, "ok")
            self.assertTrue((d / "5030000099.jpg").exists())
            self.assertTrue((d / "5030000099_2.jpg").exists())
            self.assertFalse((d / "4920000001.jpg").exists())

    def test_load_mapping_csv(self) -> None:
        from src.batch_rename import load_mapping

        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "map.csv"
            csv_path.write_text("原始单号,新单号\n4920000001,5030000099\n4920000002,5030000100\n")
            mapping = load_mapping(csv_path)
            self.assertEqual(mapping, {"4920000001": "5030000099", "4920000002": "5030000100"})


if __name__ == "__main__":
    unittest.main()
