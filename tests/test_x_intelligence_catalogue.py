"""Tests for deterministic, evidence-grounded X intelligence cataloguing."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.x_intelligence_catalogue import build_catalogue, classify_text


class XIntelligenceCatalogueTests(unittest.TestCase):
    def test_classification_is_deterministic_and_explains_hits(self) -> None:
        text = "An agent workflow automates retrieval and scoring through an API integration."
        first = classify_text(text)
        second = classify_text(text)
        self.assertEqual(first, second)
        self.assertGreaterEqual(first["ois_relevance_score"], 48)
        self.assertIn("automation", first["topics"])
        self.assertIn("workflow", first["evidence_terms"]["ois"])

    def test_catalogue_preserves_source_and_marks_missing_text(self) -> None:
        report = {
            "results": [
                {
                    "url": "https://x.com/person/status/1",
                    "status_id": "1",
                    "twscrape": {"status": "failed"},
                    "gallery_dl": {"status": "failed"},
                }
            ]
        }
        catalogue, backlog = build_catalogue(report)
        self.assertEqual(catalogue[0]["retrieval_status"], "no_text_recovered")
        self.assertEqual(catalogue[0]["source_url"], "https://x.com/person/status/1")
        self.assertEqual(backlog, [])

    def test_catalogue_uses_text_from_twscrape_and_retains_hash(self) -> None:
        report = {
            "results": [
                {
                    "url": "https://x.com/person/status/2",
                    "status_id": "2",
                    "twscrape": {
                        "status": "success",
                        "text": (
                            "An agent workflow improves retrieval, scoring, memory, "
                            "and integration for OIS."
                        ),
                        "raw_evidence": {"sha256": "a" * 64},
                    },
                    "gallery_dl": {"status": "failed"},
                }
            ]
        }
        catalogue, backlog = build_catalogue(report)
        self.assertEqual(catalogue[0]["retrieval_status"], "text_recovered")
        self.assertIn("a" * 64, catalogue[0]["evidence_sha256"])
        self.assertEqual(len(backlog), 1)
        self.assertEqual(backlog[0]["status"], "needs_human_validation")

    def test_gallery_evidence_is_read_without_network(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            evidence = Path(directory) / "raw.jsonl"
            evidence.write_text(
                json.dumps({"text": "A Python automation workflow integrates an AI agent."}) + "\n",
                encoding="utf-8",
            )
            report = {
                "results": [
                    {
                        "url": "https://x.com/person/status/3",
                        "status_id": "3",
                        "twscrape": {"status": "unavailable"},
                        "gallery_dl": {
                            "status": "success",
                            "stdout_evidence": {"path": str(evidence), "sha256": "b" * 64},
                        },
                    }
                ]
            }
            catalogue, _ = build_catalogue(report)
            self.assertEqual(catalogue[0]["retrieval_status"], "text_recovered")
            self.assertIn("Python", catalogue[0]["text"])
            self.assertIn("b" * 64, catalogue[0]["evidence_sha256"])


if __name__ == "__main__":
    unittest.main()
