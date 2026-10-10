"""Build a transparent, heuristic intelligence catalogue from preserved X evidence.

No network calls or LLM/API usage occur in this stage. Every derived row retains its
source URL and raw evidence hashes; scores are heuristics, not model judgments.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

TOPICS: dict[str, tuple[str, ...]] = {
    "ai_tools": ("agent", "llm", "model", "claude", "gpt", "gemini", "ai tool", "mcp", "rag"),
    "coding": ("python", "typescript", "javascript", "code", "github", "repo", "api", "sdk", "cli"),
    "design": ("figma", "design system", "ui", "ux", "component", "prototype", "visual"),
    "automation": ("automation", "workflow", "n8n", "trigger", "pipeline", "orchestration", "agentic"),
    "resources": ("open source", "github.com", "documentation", "tutorial", "library", "framework", "repo"),
    "growth": ("viral", "hook", "retention", "content", "audience", "engagement", "distribution"),
}
OIS_TERMS = (
    "agent", "workflow", "automation", "memory", "rag", "retrieval", "scoring", "pipeline",
    "orchestration", "api", "integration", "observability", "evaluation", "guardrail",
    "classification", "content", "growth", "signal", "knowledge",
)


def _evidence_hashes(value: Any, found: list[str]) -> None:
    if isinstance(value, dict):
        for key in ("raw_evidence", "stdout_evidence", "stderr_evidence"):
            evidence = value.get(key)
            if isinstance(evidence, dict) and isinstance(evidence.get("sha256"), str):
                found.append(evidence["sha256"])
        for child in value.values():
            _evidence_hashes(child, found)
    elif isinstance(value, list):
        for child in value:
            _evidence_hashes(child, found)


def _text_from_value(value: Any) -> list[str]:
    texts: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower() in {"text", "rawcontent", "full_text", "description", "title", "note_tweet"}:
                if isinstance(child, str) and child.strip():
                    texts.append(child.strip())
            else:
                texts.extend(_text_from_value(child))
    elif isinstance(value, list):
        for child in value:
            texts.extend(_text_from_value(child))
    return texts


def _gallery_evidence_text(row: dict[str, Any]) -> list[str]:
    """Read and parse previously preserved gallery-dl JSONL; never make network calls."""
    evidence = row.get("gallery_dl", {}).get("stdout_evidence", {})
    evidence_path = evidence.get("path") if isinstance(evidence, dict) else None
    if not isinstance(evidence_path, str):
        return []
    path = Path(evidence_path)
    if not path.is_file():
        return []
    texts: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            texts.extend(_text_from_value(json.loads(line)))
        except json.JSONDecodeError:
            # Malformed lines remain in raw evidence and are not treated as content.
            continue
    return texts


def classify_text(text: str) -> dict[str, Any]:
    """Classify with explicit keyword evidence and return reproducible heuristic scores."""
    normalized = re.sub(r"\s+", " ", text.lower()).strip()
    topic_hits = {
        topic: [term for term in terms if term in normalized]
        for topic, terms in TOPICS.items()
    }
    topic_hits = {topic: hits for topic, hits in topic_hits.items() if hits}
    ois_hits = [term for term in OIS_TERMS if term in normalized]
    relevance = min(100, len(set(ois_hits)) * 12)
    distinct_tokens = set(re.findall(r"[a-z0-9_+#.-]{3,}", normalized))
    novelty_proxy = min(100, len(distinct_tokens) * 2)
    return {
        "topics": topic_hits,
        "ois_relevance_score": relevance,
        "novelty_proxy_score": novelty_proxy,
        "confidence": "low" if len(normalized) < 80 else "medium",
        "scoring_method": "keyword_heuristic_v1",
        "evidence_terms": {"ois": ois_hits},
    }


def build_catalogue(report: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    catalogue: list[dict[str, Any]] = []
    backlog: list[dict[str, Any]] = []
    for row in report.get("results", []):
        twscrape = row.get("twscrape", {})
        texts = [twscrape.get("text")] if isinstance(twscrape.get("text"), str) else []
        texts.extend(_gallery_evidence_text(row))
        text = max((item for item in texts if item), key=len, default="")
        hashes: list[str] = []
        _evidence_hashes(row, hashes)
        unique_hashes = sorted(set(hashes))
        media_references = sorted(set(
            (twscrape.get("media_references") or [])
            + (row.get("gallery_dl", {}).get("media_references") or [])
        ))
        if not text:
            catalogue.append({
                "source_url": row.get("url"),
                "status_id": row.get("status_id"),
                "retrieval_status": "no_text_recovered",
                "text": None,
                "media_references": media_references,
                "evidence_sha256": unique_hashes,
                "classification": None,
            })
            continue
        classification = classify_text(text)
        record = {
            "source_url": row.get("url"),
            "status_id": row.get("status_id"),
            "retrieval_status": "text_recovered",
            "text": text,
            "media_references": media_references,
            "evidence_sha256": unique_hashes,
            "classification": classification,
        }
        catalogue.append(record)
        if classification["ois_relevance_score"] >= 24:
            backlog.append({
                "source_url": row.get("url"),
                "status_id": row.get("status_id"),
                "priority": "P1" if classification["ois_relevance_score"] >= 48 else "P2",
                "title": "Review recovered post for OIS implementation opportunity",
                "proposed_action": (
                    "Manually validate the cited post, extract the concrete mechanism, "
                    "map it to an existing OIS capability, then add acceptance tests before implementation."
                ),
                "ois_relevance_score": classification["ois_relevance_score"],
                "topics": classification["topics"],
                "evidence_sha256": unique_hashes,
                "status": "needs_human_validation",
            })
    catalogue.sort(
        key=lambda item: (
            item.get("classification", {}).get("ois_relevance_score", -1)
            if item.get("classification") else -1
        ),
        reverse=True,
    )
    backlog.sort(key=lambda item: item["ois_relevance_score"], reverse=True)
    return catalogue, backlog


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=Path("artifacts/x_intelligence/retrieval-comparison.json"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/x_intelligence"))
    args = parser.parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8"))
    catalogue, backlog = build_catalogue(report)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "intelligence-catalogue.json").write_text(
        json.dumps({"schema_version": "1.0", "method": "keyword_heuristic_v1", "records": catalogue},
                   ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (args.output / "implementation-backlog.json").write_text(
        json.dumps({"schema_version": "1.0", "items": backlog}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8"
    )
    print(f"Catalogue records: {len(catalogue)}; backlog candidates: {len(backlog)}")
    print("Scores are provisional heuristics. Validate each source post before implementation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
