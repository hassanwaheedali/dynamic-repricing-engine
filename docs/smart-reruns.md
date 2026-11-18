# Smart change detection and targeted re-runs

Both repricing (including personal commission) and Market Range support:

```powershell
python index.py -i data/inputs/catalog.csv --rerun targeted
python index.py -i data/inputs/catalog.csv --rerun full
python index.py -r -i data/inputs/models.csv --rerun targeted
python index.py -m 5 -i data/inputs/catalog.csv --rerun targeted
```

`--fresh` / `--no-resume` mean full processing and conflict with `--rerun targeted`.
Without an explicit choice, a terminal offers targeted/full processing only when a
compatible baseline contains changed, new, removed, or pending rows. Unchanged
input runs a full refresh without prompting; headless execution also defaults to a
full refresh. An incompatible baseline is reported before automatic full processing.
A targeted first run
with no prior state processes all rows. A targeted request with corrupt, legacy,
or incompatible state does **not** silently become a full run: choose full explicitly
in the terminal, or rerun with `--rerun full` after the headless error.

## What is reused

Only uniquely occurring, identical input content with compatible completed results
is reused. All supplied input columns participate. `S.NO` and its aliases are
display-only and remain optional; their values and row positions never establish
identity. Current input ordering and serial-number behavior are preserved.

For change reporting only, the same full Brand + Name must occur exactly once in
each catalog before column differences are attributed. Renamed products are
reported as unmatched rather than given fabricated histories. Duplicate/ambiguous
content is processed again without prompting when the catalog is unchanged.
Failed/incomplete discovery and unresolved variant ambiguity are retried;
completed candidate rejections remain terminal review outcomes.

The summary includes prior observation times. Targeted reuse retains those market
observations; choose full when every product needs fresh marketplace discovery.
Affected rows always run the existing complete worker pipeline.

## State and compatibility

Versioned working checkpoints and completed snapshots live in `data/.checkpoints/`,
namespaced by canonical source path and mode. Each worker's outcome is saved
atomically. Working generations are usable only with valid manifests, compatible
dependencies, and the current completed snapshot as parent. Superseded work cannot
override a newer snapshot, even if interruption leaves its file behind.

Processing signatures include audited configuration, actual matching-registry
contents, relevant runtime versions, and engine source provenance. Source changes
in an already-running interpreter require restarting it. Export-only changes
regenerate artifacts from compatible unformatted results. Signatures persist safe
component labels and digests, never environment dumps, credentials, or sessions.
Shared-source changes invalidate conservatively where finer dependencies are not
proven. Legacy files are recognized but never trusted for incompatible reuse.
Distinct retained legacy name columns keep their existing precedence. Processing
dependencies are checked again before publication so a run cannot publish results
evaluated under a changed configuration or registry. Untracked request headers
disable persisted reuse while full runs remain supported; a run-private keyed
digest detects header mutation without recording authentication material.

Runs acquire nonblocking OS locks for shared input, state, and output resources.
The lock registry is in the current user's OS temporary directory, shared across
working directories/checkouts. A conflicting run exits with an actionable error;
ownership releases on normal exit or process termination. Stable lock files are
not themselves evidence of a running process and must not be deleted to unlock.

## Publication and recovery

Each artifact is staged beside its destination, flushed, and replaced atomically.
There is **no transaction across CSV, XLSX, platform, and winner files**. A durable
publication journal records intent, expected digest, file identity, and actual
outcome. Required CSV failures retain working state; existing optional XLSX and
dedicated-export failures remain warnings. Only verified current paths are
reported as updated. Timestamp collisions add a numeric suffix to the paired audit
filenames instead of replacing history; latest filenames retain their usual names.

On interruption, use targeted processing to recover compatible saved rows and
regenerate a complete output. Full processing still refreshes every row. Input
changes during a run stop publication and retain recovery state.

Zero-winner cleanup is limited to the exact managed latest winner paths for the
current catalog/destination/commission. Deletion requires a valid previous
publication receipt **and matching file identity and contents**. Historical,
unverified, externally edited, and symlinked files are not removed. Locked or
unverified retained files are reported as stale; standalone exporter calls without
ownership receipts do not delete winner files.
