import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from ca_app.runtime.usage_logger import UsageLogger, file_metadata, sanitize_metadata


class UsageLoggerTests(unittest.TestCase):
    def test_writes_jsonl_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            logger = UsageLogger(Path(tmp) / "usage_logs", "v-test")
            logger.log("workspace_changed", workspace="Raman", metadata={"tab": "Baseline"})

            files = list((Path(tmp) / "usage_logs").glob("usage_*.jsonl"))
            self.assertEqual(len(files), 1)
            rows = files[0].read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(rows), 1)
            record = json.loads(rows[0])
            self.assertEqual(record["app_version"], "v-test")
            self.assertEqual(record["event_type"], "workspace_changed")
            self.assertEqual(record["workspace"], "Raman")
            self.assertEqual(record["metadata"]["tab"], "Baseline")

    def test_disabled_logger_does_not_create_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            logger = UsageLogger(Path(tmp) / "usage_logs", "v-test", enabled=False)
            logger.log("app_started")
            self.assertFalse((Path(tmp) / "usage_logs").exists())

    def test_cleanup_old_logs_removes_expired_daily_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp) / "usage_logs"
            log_dir.mkdir()
            old_date = datetime.now() - timedelta(days=40)
            old_path = log_dir / f"usage_{old_date.strftime('%Y%m%d')}.jsonl"
            new_path = log_dir / f"usage_{datetime.now().strftime('%Y%m%d')}.jsonl"
            old_path.write_text("old\n", encoding="utf-8")
            new_path.write_text("new\n", encoding="utf-8")

            UsageLogger(log_dir, "v-test", retention_days=30).cleanup_old_logs()

            self.assertFalse(old_path.exists())
            self.assertTrue(new_path.exists())

    def test_cleanup_runs_once_per_logger_day(self):
        class CountingLogger(UsageLogger):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.cleanup_count = 0

            def cleanup_old_logs(self, now=None):
                self.cleanup_count += 1
                super().cleanup_old_logs(now=now)

        with tempfile.TemporaryDirectory() as tmp:
            logger = CountingLogger(Path(tmp) / "usage_logs", "v-test")
            logger.log("app_started")
            logger.log("workspace_changed")

            self.assertEqual(logger.cleanup_count, 1)

    def test_metadata_is_short_and_file_metadata_has_no_parent_path(self):
        clean = sanitize_metadata(
            {
                "long": "x" * 500,
                "ok": 1,
                "flag": True,
                "full_path": r"C:\secret\sample.txt",
                "raw_data": [1, 2, 3],
                "measured_voltage_v": 1.25,
                "measured_current_mA": 2.5,
                "file_name": "sample.txt",
            }
        )
        self.assertLessEqual(len(clean["long"]), 180)
        self.assertEqual(clean["ok"], 1)
        self.assertTrue(clean["flag"])
        self.assertEqual(clean["full_path"], "[redacted]")
        self.assertEqual(clean["raw_data"], "[redacted]")
        self.assertEqual(clean["measured_voltage_v"], "[redacted]")
        self.assertEqual(clean["measured_current_mA"], "[redacted]")
        self.assertEqual(clean["file_name"], "sample.txt")

        meta = file_metadata(r"C:\secret\folder\data.csv")
        self.assertEqual(meta["file_name"], "data.csv")
        self.assertEqual(meta["extension"], ".csv")

        meta = file_metadata("/secret/folder/other.txt")
        self.assertEqual(meta["file_name"], "other.txt")
        self.assertEqual(meta["extension"], ".txt")


if __name__ == "__main__":
    unittest.main()
