---
name: dependabot-triage
description: "Triage Dependabot alerts: assess real impact, dismiss noise"
allowed-tools: Bash(gh:*), Bash(npm:*), Bash(uv:*), Read, Grep, Glob
disable-model-invocation: true
---

Triage the current repository's open Dependabot alerts, separating real vulnerabilities from noise: most alerts on transitive dependencies are not exploitable.

## Fetch

```bash
gh api -X GET repos/{owner}/{repo}/dependabot/alerts --jq '.[] | select(.state == "open") | {number, severity: .security_advisory.severity, package: .security_vulnerability.package.name, ecosystem: .security_vulnerability.package.ecosystem, summary: .security_advisory.summary, cve: .security_advisory.cve_id, manifest: .dependency.manifest_path}'
```

## Trace each alert

For each alert, trace how the dependency enters the project, then classify it:

| Classification | Meaning |
|---|---|
| **Exploitable** | Runs in prod, processes untrusted input, vulnerability is reachable |
| **Theoretical** | Runs in prod but attack vector is implausible for our usage |
| **Build-only** | devDependencies, CI tools, linters, bundler plugins |
| **Tree-shaken** | In dep tree but bundler (Vite/webpack) strips it from runtime output |
| **Unused path** | Transitive dep via a code path we don't exercise |

## Report

Present a table, one row per alert. Keep reasoning to one specific sentence: "transitive of X via Y, only used in Z" not "low risk".

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

**Keep open** Exploitable and Theoretical alerts, and summarize what updating would involve for each.

**Always ask for confirmation before dismissing.** Present the table, get a yes, then dismiss.
