---
description: Triage Dependabot alerts — assess real impact, dismiss noise
allowed-tools: Bash(gh:*), Bash(npm:*), Bash(uv:*), Read, Grep, Glob
---

Triage open Dependabot alerts for the current repository. The goal is distinguishing real vulnerabilities from noise — most Dependabot alerts on transitive dependencies are not exploitable.

## Fetch

```bash
gh api -X GET repos/{owner}/{repo}/dependabot/alerts --jq '.[] | select(.state == "open") | {number, severity: .security_advisory.severity, package: .security_vulnerability.package.name, ecosystem: .security_vulnerability.package.ecosystem, summary: .security_advisory.summary, cve: .security_advisory.cve_id, manifest: .dependency.manifest_path}'
```

If zero open alerts, say so and stop.

## Trace each alert

For each alert, trace the dependency to understand how it enters the project:

- **npm**: `npm ls <package>` in the directory containing the manifest
- **pip**: check pyproject.toml, requirements files, or `uv pip list`

Then classify:

| Classification | Meaning |
|---|---|
| **Exploitable** | Runs in prod, processes untrusted input, vulnerability is reachable |
| **Theoretical** | Runs in prod but attack vector is implausible for our usage |
| **Build-only** | devDependencies, CI tools, linters, bundler plugins |
| **Tree-shaken** | In dep tree but bundler (Vite/webpack) strips it from runtime output |
| **Unused path** | Transitive dep via a code path we don't exercise |

Key questions: Is it direct or transitive? Does it run at runtime or only during build/test? For frontend JS — does it end up in the browser bundle? Does our code use the vulnerable function?

## Report

Present a table, one row per alert. Keep reasoning to one specific sentence — "transitive of X via Y, only used in Z" not "low risk".

```
| # | Sev | Package | Manifest | Classification | Reasoning |
```

## Act

**Dismiss** Build-only, Tree-shaken, and Unused path alerts:
```bash
gh api -X PATCH repos/{owner}/{repo}/dependabot/alerts/{number} \
  -f state=dismissed -f dismissed_reason=not_used \
  -f dismissed_comment="<one-sentence reason>"
```

Valid dismiss reasons: `fix_started`, `inaccurate`, `no_bandwidth`, `not_used`, `tolerable_risk`. Use `not_used` for tree-shaken/build-only, `tolerable_risk` for theoretical.

**Don't dismiss** Exploitable or Theoretical alerts. For those, summarize what updating would involve.

**Always ask for confirmation before dismissing.** Present the table, get a yes, then dismiss.
