# X Intelligence ingestion benchmark

This workflow evaluates retrieval tools against the supplied X status URLs and preserves evidence before classification. It is a retrieval/analysis staging tool, not a bypass for X access controls.

## Components

- `scripts/x_intelligence_benchmark.py`: runs both adapters per URL, records return status and latency, writes raw stdout/stderr or raw tweet JSON, and produces a comparison report.
- `data/x_intelligence/sources.sample.txt`: small sample for the initial smoke test.
- `tests/test_x_intelligence_benchmark.py`: deterministic, network-free unit tests.
- `artifacts/x_intelligence/evidence/`: local raw evidence; do not commit retrieved user data or session material.
- `artifacts/x_intelligence/retrieval-comparison.json`: per-URL adapter results and measured success rates.

## Setup (local, no paid API)

Run from the repository root with Python 3.12+.

```bash
python -m pip install gallery-dl twscrape
```

Configure `gallery-dl` authentication locally through its supported config/cookie settings. For `twscrape`, configure an authorized account pool in a local SQLite database. Never put cookies, passwords, tokens, or account databases in this repository. The benchmark accepts the database path through `OIS_TWSCRAPE_DB`.

## Run a 3-URL smoke test

```bash
python scripts/x_intelligence_benchmark.py benchmark \
  --urls data/x_intelligence/sources.sample.txt \
  --limit 3 \
  --output artifacts/x_intelligence
```

For all URLs in a manifest, use `--limit 0`. Use a manifest containing one status URL per line; comments beginning with `#` and blank lines are ignored. Duplicate URLs are collapsed in first-seen order.

## Measurement rules

- Both adapters are attempted independently for each URL.
- A successful retrieval means usable adapter data was returned, not that every image/video was downloaded.
- The report records per-adapter status, elapsed time, media references where discoverable, errors, and the evidence path/hash for raw outputs.
- Missing software, missing authentication, rate limits, blocked/private/deleted posts, and timeouts are recorded as outcomes, not silently treated as empty posts.
- Choose a primary adapter only after comparing successful text retrieval, media-reference recovery, latency, and failure causes on the same sample. Do not infer a winner from one success.
- Preserve raw evidence before any AI classification. The evidence is the source of truth; derived records must retain the source URL and evidence hash.
- Respect X's terms, applicable law, account access controls, rate limits, and privacy. Do not use credential stuffing, session sharing, or access-control bypasses.

## Interpretation

`gallery-dl` is primarily a media/gallery downloader with metadata support; `twscrape` returns tweet objects through its account pool. The tools have different strengths, so compare text and media separately. A missing adapter is an environment/setup result, not proof that the post itself is inaccessible.
