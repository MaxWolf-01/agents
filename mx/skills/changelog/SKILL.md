---
name: changelog
description: Update CHANGELOG.md with notable changes since the last release. Use when preparing a release, or when asked for the changelog or release notes.
---

If `CHANGELOG.md` does not exist, use `CHANGELOG` instead.

## Step-by-Step Process

### 1. Determine baseline version

If no baseline version is provided, use the most recent git tag.

### 2. Read what landed

```
git log --first-parent --format='%h %s%n%b' <baseline-version>..HEAD
```

The first-parent line holds one commit per merged branch, plus any commit made straight on the trunk. A merge's body opens with a paragraph on what the whole branch changed: write that branch's entries from it, and read the branch's own commits (`git log <merge>^1..<merge>^2`) only where the paragraph leaves a notable change unclear.

### 3. Update the changelog

Read the existing changelog file and check if there are changes not yet incorporated, then add them. Always add them to the "Unreleased" section only. If there is none yet, add it at the top in the same style as the existing changelog (for example, `## Unreleased` vs `## [Unreleased]`).

## Ground Rules When Writing Changelogs

### Content Guidelines

- Focus on **notable changes** that affect users (features, fixes, breaking changes)
- Mention pull requests (`#NUMBER`) when available, but not raw commit hashes
- Ignore insignificant changes (typo fixes, internal refactoring, minor documentation updates)
- Order entries by importance: breaking changes first, then features, then fixes

### Style Guidelines

- Start each entry with a past-tense verb or descriptive phrase

### Example Format

```
## 2.13.0

* Added multi-key support to the `|sort` filter.  #827
* Fix `not undefined` with strict undefined behavior.  #838
* Added support for free threading Python.  #841

## 2.12.0

* Item or attribute lookup will no longer swallow all errors in Python.  #814
* Added `|zip` filter.  #818
* Fix `break_on_hyphens` for the `|wordwrap` filter.  #823
* Prefer error message from `unknown_method_callback`.  #824
* Ignore `.jinja` and `.jinja2` as extensions in auto escape.  #832
```

## Notes

- Preserve the existing changelog style and formatting (headings, bullet style, ordering, and spacing)
- When in doubt about whether a change is significant, err on the side of including it
