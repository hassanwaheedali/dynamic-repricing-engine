# Smart re-run verification and adversarial review

The user required separate adversarial review agents before subsequent commits.
State/provenance, execution selection, publication, and the final bounded input/
dependency changes were reviewed separately. The optional external cross-model
review was offered and explicitly declined.

## Findings reconciled

| Finding | Classification and resolution |
| --- | --- |
| Working state missing mandatory fields could interrupt selection despite a valid snapshot | Actionable: validate provenance, record shapes, observation coverage, indices and completed-snapshot phase before selection. |
| Relative lock registries allowed overlapping runs from different working directories | Actionable: use one user-wide OS temporary lock registry; test independent processes, inputs and working directories. |
| Platform/query children could outlive a failed worker | Actionable: share cancellation/join ownership at platform, waterfall-query and page boundaries, preserving successful discovery policy. |
| Effective personal commission selector was absent from dependencies | Actionable: include the existing default selector and selected vendor settings; preserve all commission math. |
| Optional Excel runtime metadata could abort CSV processing | Actionable: represent unavailable optional runtime in the export signature. |
| Disk hashes could mislabel already-loaded code | Actionable: capture immutable implementation provenance at earliest package initialization and require restart after source changes. |
| Recovery could adopt identical-content unowned winner files | Actionable: persist staged identity before replacement; require identity and digest during crash acknowledgement. |
| Completion trusted publication status without checking current files | Actionable: verify destination identity/content before promotion and suppress invalid optional output links. |
| Same-second runs could overwrite audit history | Actionable: allocate collision-safe paired audit filenames while preserving latest names. |
| Unreadable optional destinations could abort recovery | Actionable: record failed/unverified recovery outcomes; continue required publication. |
| Signature fallback disabled full-run dependency checks | Actionable: retain bounded public signatures, disable reuse explicitly, and compare a nonpersisted run-private request-context digest before publication. |
| Extracted name helper allegedly changed alias precedence | Retracted after checking actual HEAD/main: Product Title already preceded Model. Existing precedence remains unchanged. |

No actionable findings remained in the final bounded reviews. Tests reproduce the
actionable failures, including interruption before/after replacement, duplicate
content, renamed models, missing serials, dependency mutation, and locked outputs.

## User-directed follow-up review

The user's subsequent staged/unstaged changes were reviewed separately before
commit. Automatic unchanged-input execution now performs a full refresh without
prompting, including unchanged duplicate rows. Prompting depends on actual input
content changes or pending state, rather than conservative cache-reuse uncertainty.
Completed candidate rejections are terminal; dependency diagnostics identify safe
changed component labels.

The user's capacity/anchor/query changes and ADR-008 were retained. Review found
that bare `IN` exclusion lost screen-size protection; bounded screen shorthand is
now canonicalized with regression coverage for 32/40-inch mismatch and existing
prose-preposition cases. The user explicitly confirmed their Book1 color and SKU
suffix edits as verified corrections and instructed preserving them.

## Verification

- Pre-change baseline: 1,277 tests passed, 28 warnings; Ruff and strict Mypy passed.
- Intermediate full regression checkpoint: 1,321 tests passed, 65 warnings.
- Final verification is recorded in `tasks/todo.md` after the current full run.
- Coverage uses standard-library executable-line tracing because the optional
  `coverage` package is not installed; no dependency was added for this check.

Final scoped verification: 1,344 tests passed (73 warnings), Ruff passed, strict
Mypy passed for 28 source files. This ran in an isolated copy with HEAD matching
code/catalog fixtures, because the user explicitly excluded concurrent matching
edits from this commit. The live combined workspace is not claimed regression-free.
Matcher, capacity, matcher tests, Book1 edits and ADR-008 remain outside this commit.

Optional XLSX warnings remain nonfatal. Publication is atomic per file, not a
transaction across all artifacts. Reused rows keep their original observation
times. No live marketplace result equivalence is claimed; deterministic network
fixtures and the existing representative regression suite establish equivalence.
