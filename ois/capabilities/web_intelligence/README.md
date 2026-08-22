# OIS Web Intelligence

V1 is intentionally small: one standard-library HTTP acquisition engine, deterministic extraction, bounded routing, validation, provenance hashing, and the existing `CapabilityContract` boundary.

The capability is read-only and inactive by default. Browser automation, crawling, proxying, CAPTCHA handling, credentials, and durable learning are explicitly outside V1 and require separate governed capabilities and evidence.

```text
Request -> Router -> HTTP acquisition -> Validation -> Extraction -> Provenance -> Result
```

The manifest records implementation status separately from activation and production verification.
