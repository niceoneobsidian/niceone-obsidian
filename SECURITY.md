# Security Policy

## Security Status

Niceone Obsidian (OIS) is an actively developed, pre-production software project.

The project does not currently publish a stable production release series. Security fixes are therefore applied to the active development branch and, where applicable, to supported release branches.

Because OIS is still under active architectural and implementation development, users should not assume that unreleased or experimental capabilities are production-ready.

## Supported Versions

| Version / Branch | Security Support |
|---|---|
| `main` | :white_check_mark: |
| Active release branches | :white_check_mark: |
| Experimental / feature branches | :warning: Best effort only |
| Archived / obsolete branches | :x: |

A specific release-support matrix will be published when OIS begins producing versioned releases.

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues, discussions, or pull requests.**

Preferred reporting method:

1. Use GitHub's **Private Vulnerability Reporting** feature for this repository, if available.
2. Alternatively, contact the project maintainers through the private security contact documented in the repository.

Reports should include, where possible:

- A clear description of the vulnerability.
- The affected component, capability, workflow, or interface.
- Affected version, branch, or commit.
- Steps required to reproduce the issue.
- Security impact and potential exploitation scenario.
- Relevant logs, traces, screenshots, or proof-of-concept material.
- Any suggested mitigation or remediation.

Please avoid including secrets, credentials, API keys, personal information, or unnecessary sensitive data in the report.

## Response Process

The maintainers will:

1. Acknowledge receipt of a report as soon as reasonably possible.
2. Triage and assess the reported security impact.
3. Reproduce and validate the issue where possible.
4. Determine whether the report represents a security vulnerability.
5. Develop and test a remediation when required.
6. Coordinate disclosure with the reporter when appropriate.
7. Publish a security advisory when disclosure is warranted.

Security reports may be accepted, rejected, or reclassified after investigation.

## Disclosure

Please allow the maintainers reasonable time to investigate and remediate a confirmed vulnerability before publicly disclosing technical details.

When a vulnerability is confirmed, disclosure should preferably occur after a fix or mitigation is available.

Where appropriate, the project may use GitHub Security Advisories and request a CVE for a confirmed vulnerability.

## Scope

Security reports are especially valuable for issues involving:

- Authentication and authorization.
- RBAC and policy enforcement.
- Tenant or data isolation.
- Secrets and credential handling.
- Agent, tool, and model authorization.
- Capability activation.
- Execution controls and approval gates.
- Web acquisition and external-provider boundaries.
- Prompt or instruction injection affecting governed execution.
- Unsafe autonomous actions.
- Provenance, evidence, or validation bypasses.
- Memory isolation or unauthorized data access.
- CI/CD and supply-chain security.
- Dependency vulnerabilities.
- Security boundary violations.

## Out of Scope

The following are generally not considered security vulnerabilities unless they demonstrate a meaningful security impact:

- General bugs without security implications.
- Feature requests.
- Documentation errors.
- Performance issues without security impact.
- Issues requiring intentionally compromised developer credentials.
- Issues affecting unsupported or obsolete branches.

## Safe Harbor

Security researchers acting in good faith and following this policy are encouraged to report vulnerabilities responsibly.

Please avoid:

- Accessing or modifying data belonging to other users.
- Disrupting production or shared services.
- Destroying data.
- Performing social engineering.
- Conducting denial-of-service attacks.
- Exfiltrating unnecessary sensitive information.

If you accidentally encounter sensitive information while investigating, stop testing that path and report the discovery privately.

## Security Expectations

OIS follows an evidence-driven security model.

Security-sensitive functionality should not be considered production-ready solely because code exists or tests pass.

Security activation requires appropriate:

- Authorization.
- Policy enforcement.
- Validation.
- Observability.
- Auditability.
- Testing.
- Recovery controls.
- Evidence of successful verification.

The project may explicitly mark capabilities as experimental, designed, implemented, tested, or production-ready depending on available evidence.
