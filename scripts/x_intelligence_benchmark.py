"""Benchmark X post retrieval adapters and preserve raw evidence before analysis.

The command is intentionally API-key-free. twscrape requires a locally configured
account pool; gallery-dl may use browser cookies configured outside the repository.
Never commit cookies, account databases, or raw private session material.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

STATUS_RE = re.compile(r"/status/(\d+)")
DEFAULT_SAMPLE = Path("data/x_intelligence/sources.sample.txt")


def load_urls(path: Path) -> list[str]:
    """Load unique X status URLs while retaining their first-seen order."""
    urls: list[str] = []
    seen: set[str] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        value = raw.strip()
        if not value or value.startswith("#"):
            continue
        if not is_x_status_url(value):
            raise ValueError(f"Not a supported X status URL: {value}")
        if value not in seen:
            urls.append(value)
            seen.add(value)
    return urls


def is_x_status_url(value: str) -> bool:
    """Return whether value is an HTTP(S) X/Twitter status URL."""
    try:
        parsed = urlparse(value)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    return (
        parsed.scheme in {"http", "https"}
        and host in {"x.com", "www.x.com", "twitter.com", "www.twitter.com"}
        and STATUS_RE.search(parsed.path) is not None
    )


def status_id(url: str) -> str:
    """Extract a numeric status ID from a validated X status URL."""
    match = STATUS_RE.search(urlparse(url).path)
    if not match:
        raise ValueError(f"Not a supported X status URL: {url}")
    return match.group(1)


def write_evidence(path: Path, payload: bytes) -> dict[str, Any]:
    """Write immutable-by-convention evidence bytes and return integrity metadata."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return {
        "path": str(path),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "bytes": len(payload),
    }


def run_gallery_dl(url: str, evidence_dir: Path, timeout: int) -> dict[str, Any]:
    """Capture gallery-dl metadata output and media URL references without classifying."""
    executable = shutil.which("gallery-dl")
    if executable is None:
        return {"adapter": "gallery-dl", "status": "unavailable", "error": "gallery-dl not on PATH"}
    started = time.monotonic()
    try:
        result = subprocess.run(
            [executable, "--dump-json", url],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        stdout = result.stdout.encode("utf-8", errors="replace")
        stderr = result.stderr.encode("utf-8", errors="replace")
        stamp = status_id(url)
        raw = write_evidence(evidence_dir / "gallery-dl" / f"{stamp}.stdout.jsonl", stdout)
        log = write_evidence(evidence_dir / "gallery-dl" / f"{stamp}.stderr.txt", stderr)
        records: list[Any] = []
        parse_errors: list[str] = []
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                parse_errors.append(str(exc))
        media_refs = sorted({item for item in _find_urls(records) if _looks_like_media(item)})
        status = "success" if result.returncode == 0 and records else "failed"
        return {
            "adapter": "gallery-dl",
            "status": status,
            "returncode": result.returncode,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "records": len(records),
            "media_references": media_refs,
            "parse_errors": parse_errors,
            "stdout_evidence": raw,
            "stderr_evidence": log,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "adapter": "gallery-dl",
            "status": "timeout",
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "error": f"Timed out after {timeout}s",
            "stdout_evidence": write_evidence(
                evidence_dir / "gallery-dl" / f"{status_id(url)}.timeout.stdout.txt",
                (exc.stdout or b"") if isinstance(exc.stdout, bytes) else (exc.stdout or "").encode(),
            ),
        }


def _find_urls(value: Any) -> list[str]:
    found: list[str] = []
    if isinstance(value, str) and value.startswith(("http://", "https://")):
        found.append(value)
    elif isinstance(value, dict):
        for child in value.values():
            found.extend(_find_urls(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(_find_urls(child))
    return found


def _looks_like_media(url: str) -> bool:
    lowered = url.lower()
    return any(
        token in lowered
        for token in ("pbs.twimg.com", "video.twimg.com", "ton.twitter.com", "twimg.com")
    )


async def _fetch_twscrape(url: str, db_path: str) -> dict[str, Any]:
    try:
        from twscrape import API
    except ImportError:
        return {"adapter": "twscrape", "status": "unavailable", "error": "Install optional twscrape package"}

    try:
        api = API(db_path)
        tweet = await api.tweet_details(int(status_id(url)))
        if tweet is None:
            return {"adapter": "twscrape", "status": "failed", "error": "No tweet returned"}
        raw = tweet.dict() if hasattr(tweet, "dict") else tweet.model_dump()
        return {"adapter": "twscrape", "status": "success", "record": raw}
    except Exception as exc:  # External adapter errors must be reported, not hidden.
        return {"adapter": "twscrape", "status": "failed", "error": f"{type(exc).__name__}: {exc}"}


def run_twscrape(url: str, evidence_dir: Path, db_path: str, timeout: int) -> dict[str, Any]:
    started = time.monotonic()
    try:
        result = asyncio.run(asyncio.wait_for(_fetch_twscrape(url, db_path), timeout=timeout))
    except TimeoutError:
        result = {"adapter": "twscrape", "status": "timeout", "error": f"Timed out after {timeout}s"}
    result["elapsed_seconds"] = round(time.monotonic() - started, 3)
    if "record" in result:
        # Preserve the adapter's complete returned object before extracting fields.
        raw = json.dumps(result.pop("record"), ensure_ascii=False, sort_keys=True, default=str).encode()
        result["raw_evidence"] = write_evidence(
            evidence_dir / "twscrape" / f"{status_id(url)}.json", raw
        )
        record = json.loads(raw)
        result["text"] = record.get("rawContent") or record.get("text")
        result["media_references"] = _find_urls(record.get("media") or [])
        result["status"] = "success" if result["text"] or result["media_references"] or record else "empty"
    else:
        payload = json.dumps(result, ensure_ascii=False, sort_keys=True).encode()
        result["raw_evidence"] = write_evidence(
            evidence_dir / "twscrape" / f"{status_id(url)}.result.json", payload
        )
    return result


def compare(args: argparse.Namespace) -> int:
    urls = load_urls(args.urls)
    if args.limit is not None:
        urls = urls[: args.limit]
    if not urls:
        raise ValueError("No URLs found in the input manifest")
    evidence_dir = args.output / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    report: list[dict[str, Any]] = []
    for index, url in enumerate(urls, start=1):
        # Both adapters are attempted independently; neither failure suppresses the other.
        gallery = run_gallery_dl(url, evidence_dir, args.timeout)
        twscrape = run_twscrape(url, evidence_dir, args.db_path, args.timeout)
        row = {
            "source_index": index,
            "url": url,
            "status_id": status_id(url),
            "retrieved_at": datetime.now(UTC).isoformat(),
            "gallery_dl": gallery,
            "twscrape": twscrape,
        }
        report.append(row)
        print(
            f"[{index}/{len(urls)}] {status_id(url)} "
            f"gallery-dl={gallery['status']} twscrape={twscrape['status']}",
            flush=True,
        )
    payload = {
        "schema_version": "1.0",
        "created_at": datetime.now(UTC).isoformat(),
        "input_manifest": str(args.urls),
        "sample_size": len(urls),
        "results": report,
        "summary": _summary(report),
        "notice": "Raw adapter outputs are preserved as evidence. No AI classification was run.",
    }
    output_path = args.output / "retrieval-comparison.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Report: {output_path}")
    print(json.dumps(payload["summary"], indent=2))
    return 0


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    summary: dict[str, Any] = {"total_urls": total}
    for key, label in (("gallery_dl", "gallery_dl"), ("twscrape", "twscrape")):
        counts: dict[str, int] = {}
        for row in rows:
            status = row[key].get("status", "unknown")
            counts[status] = counts.get(status, 0) + 1
        summary[label] = {
            "status_counts": counts,
            "success_rate": round(counts.get("success", 0) / total, 4) if total else 0.0,
        }
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    bench = sub.add_parser("benchmark", help="Compare twscrape and gallery-dl on supplied X URLs")
    bench.add_argument("--urls", type=Path, default=DEFAULT_SAMPLE, help="One X status URL per line")
    bench.add_argument("--limit", type=int, default=3, help="Number of first URLs to test; use 0 for all")
    bench.add_argument("--output", type=Path, default=Path("artifacts/x_intelligence"))
    bench.add_argument("--db-path", default=os.environ.get("OIS_TWSCRAPE_DB", "accounts.db"))
    bench.add_argument("--timeout", type=int, default=45)
    bench.set_defaults(func=compare)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.limit == 0:
        args.limit = None
    try:
        return args.func(args)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
