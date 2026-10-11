"""Unit tests for the X intelligence retrieval benchmark helpers."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.x_intelligence_benchmark import (
    _summary,
    is_x_status_url,
    load_urls,
    status_id,
    write_evidence,
)


class XIntelligenceBenchmarkTests(unittest.TestCase):
    def test_accepts_x_and_legacy_twitter_status_urls(self) -> None:
        self.assertTrue(is_x_status_url("https://x.com/person/status/12345"))
        self.assertTrue(is_x_status_url("https://twitter.com/person/status/12345"))
        self.assertFalse(is_x_status_url("https://x.com/person"))
        self.assertFalse(is_x_status_url("https://example.com/person/status/12345"))

    def test_extracts_status_id(self) -> None:
        self.assertEqual(status_id("https://x.com/person/status/12345?s=20"), "12345")

    def test_loads_unique_urls_in_original_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "urls.txt"
            manifest.write_text(
                "# comment\nhttps://x.com/a/status/1\n\nhttps://x.com/a/status/1\n"
                "https://x.com/b/status/2\n",
                encoding="utf-8",
            )
            self.assertEqual(
                load_urls(manifest),
                ["https://x.com/a/status/1", "https://x.com/b/status/2"],
            )

    def test_rejects_non_status_urls(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "urls.txt"
            manifest.write_text("https://example.com/not-a-status\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_urls(manifest)

    def test_evidence_records_hash_and_byte_count(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "raw.json"
            record = write_evidence(target, b'{"ok":true}')
            self.assertEqual(record["bytes"], 11)
            self.assertEqual(len(record["sha256"]), 64)
            self.assertEqual(target.read_bytes(), b'{"ok":true}')

    def test_summary_reports_adapter_success_rates(self) -> None:
        rows = [
            {"gallery_dl": {"status": "success"}, "twscrape": {"status": "failed"}},
            {"gallery_dl": {"status": "failed"}, "twscrape": {"status": "success"}},
        ]
        summary = _summary(rows)
        self.assertEqual(summary["total_urls"], 2)
        self.assertEqual(summary["gallery_dl"]["success_rate"], 0.5)
        self.assertEqual(summary["twscrape"]["success_rate"], 0.5)


if __name__ == "__main__":
    unittest.main()
