# Release Audit

Audit date: 2026-07-04

## Conclusion

This public release is approved for publication after privacy cleanup, license-scope clarification, evidence-level tightening, and adversarial review.

The repository contains 20 structured claims, 16 source records, 3 unresolved-source records, and a test suite that validates data integrity, evidence boundaries, latest corpus updates, and public-release safety.

## Taixu Five-Turn Summary

| Turn | Output | Key signal |
|---|---|---|
| 散怀 | Considered a public Skill package, a private-source mirror, a GitHub knowledge base, and a minimal evidence index. | The safest public shape is an evidence index plus scripts and docs, not a mirrored article corpus. |
| 澄源 | Core assertions were separated into privacy safety, copyright scope, evidence reliability, and investment-safety boundaries. | Public release must not expose local paths, must not relicense third-party content, and must not turn indexed snippets into A-level facts. |
| 叩实 | Ran data validation, coverage audit, public-release audit, unit tests, source lookups, and sensitive-marker scans. | Validation passed after tightening rules and removing private paths. |
| 破妄 | Three adversarial reviews checked privacy/security, copyright/source boundaries, and evidence/investment-misuse risk. | Required fixes were applied before publication. |
| 归真 | Preserved useful value: searchable evidence cards, source gaps, and current-market verification discipline. | Public package remains useful without copying full posts or private notes. |

## Addressed Findings

- Removed local absolute paths and non-public design-document references from public data.
- Replaced private-note wording with neutral user-side or redacted secondary-source wording.
- Added `LICENSE-SCOPE.md` to clarify that MIT does not cover third-party content.
- Added a takedown process with rights-holder notice fields, temporary hiding, review, deletion, downgrading, excerpt removal, or repository takedown.
- Tightened A/B evidence rules: search-index snippets can be B at most.
- Added machine checks that `primary_indexed` claims remain B-level and disclose missing full-text context.
- Downgraded the inferred 2026-06-30 post date to an indexed relative-date line discovered on 2026-07-04.
- Strengthened trade-sensitive usage restrictions for defensive-deleveraging and auto-standard-rotation claims.

## Verification

```bash
python3 scripts/validate_claims.py
python3 scripts/audit_coverage.py --json
python3 scripts/audit_public_release.py
python3 -m unittest discover -s tests -p 'test_*.py'
```

Final status:

- Claims validation: passed.
- Coverage audit: 20 claims, evidence levels A2 / B6 / D8 / U4.
- Public release audit: passed.
- Unit tests: 25 passed.
- Sensitive-marker scan: no matches for private paths, old workspace references, cloud-sync names, internal investing-tool names, token markers, cookie markers, secret markers, or private-note markers.

## Publication Boundary

This repository is not a complete archive of all public statements by the original author. It does not copy full Xueqiu posts, does not distribute third-party repository content, and does not provide investment advice.

Search-indexed snippets are preserved only as indexed evidence with explicit uncertainty. Any current-market use must re-check real-world facts, dates, policies, prices, and company fundamentals before applying the historical framework.

## Post-Release Security Fixes (2026-07-04)

After the initial public push, an adversarial security review identified two issues that were fixed:

- **Removed explicit sensitive-marker lists from `scripts/audit_public_release.py` and `tests/test_public_release.py`.** The original FORBIDDEN list used string concatenation to prevent self-matching, but this inadvertently exposed what specific personal paths, service names, credential types, and internal project codenames had been cleaned. Replaced with generic credential-leakage patterns that do not reveal any maintainer-specific information.
- **Changed persona self-reference from "窝" to "冰冰小美".** Updated `SKILL.md` and all example files to use the full pen-name as the default first-person pronoun, removing the informal contraction that belonged to the original author's personal style.

All 25 unit tests continue to pass after these changes.
