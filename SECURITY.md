# Security Policy

## Supported Project

Security reports are accepted for the current `main` branch of YONEPSE.

## Reporting a Vulnerability

Please do not open a public issue for security-sensitive problems.

Report privately through GitHub Security Advisories if available:

https://github.com/Shubhamnpk/yonepse/security/advisories/new

If advisories are unavailable, open a GitHub issue with only a minimal non-sensitive summary and ask for a private contact path.

## What to Report

Good security reports include:

- Cross-site scripting or unsafe HTML rendering.
- Workflow or GitHub Actions risks that could expose write access.
- Scraper behavior that could leak secrets or credentials.
- Dependency vulnerabilities with a practical impact on this project.
- API documentation that encourages unsafe use of the data.

## Out of Scope

- Market data being delayed, missing, or inaccurate. Use the data issue template for that.
- Denial-of-service testing against third-party data sources.
- Automated vulnerability scanner output without a practical exploit path.

## Secrets

Do not commit API keys, cookies, session tokens, or credentials. The current project is designed to run without private secrets.

