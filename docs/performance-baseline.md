# Performance and Load-Test Baselines

Performance claims require measured evidence.

Measure at minimum: single execution latency; concurrent executions; duplicate delivery under contention; worker takeover after lease expiry; checkpoint throughput; outbox throughput; recovery after process termination.

Record environment, Python version, dependency-lock identifier, database/Redis versions, CPU, memory, concurrency, sample count, p50/p95/p99 latency, throughput, error rate, and recovery time.

No baseline numbers are asserted until produced by a reproducible benchmark.
