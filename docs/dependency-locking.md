# Dependency Locking Strategy

The repository currently declares dependency ranges in pyproject.toml. Release builds must consume a reproducible lock artifact instead of resolving open ranges at deployment time.

Use a pinned lock-generation tool such as uv or pip-tools and commit the generated lock with each release. The lock should include direct and transitive dependencies, exact versions, hashes where supported, Python compatibility, and the generation-tool version.

Release CI should fail when declarations and the committed lock are inconsistent. No production dependency claim should be made from version ranges alone.
