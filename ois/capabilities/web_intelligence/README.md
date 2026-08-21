# OIS Web Intelligence Capability

`web.intelligence` is the governed facade for web acquisition and knowledge extraction.

## Design

```text
Request
  -> Adaptive Router
  -> Acquisition Engine
  -> Source Validation
  -> Extraction Engine
  -> Evidence / Provenance
  -> Learning Signal
  -> Result
```

The capability intentionally keeps provider-specific integrations behind protocols.
Adapters for Scrapy, Crawlee, Playwright, Puppeteer, Browser-Use, Crawl4AI,
Scrapling, Katana, Firecrawl-compatible services, proxy providers, and browser
session providers can be added without changing the capability contract.

## Safety boundary

The initial implementation is dependency-light and provides a standard-library
HTTP engine plus a deterministic extractor. It does not implement CAPTCHA bypass,
anti-bot evasion, credential handling, unrestricted crawling, or autonomous
external side effects. Those capabilities require explicit OIS policy, provider
contracts, tenant isolation, network controls, and validation before activation.

## Learning

Route outcomes are recorded through `RouteLearner`. This is an in-memory signal
only. Durable learning must be connected to OIS Measurement/Learning with
versioned evidence, attribution, replay/evaluation, and rollback before it can
change production routing.
