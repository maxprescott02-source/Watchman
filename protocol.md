# Validation protocol, fixed 6 September 2026 before any result exists

Two ledgers, never blended.

## A. Prospective self-test (the author's folder, 7 Sep to 5 Oct 2026)

Watchman 0.1.1, unchanged for the window. The 4am job saves the board nightly to `boards/<date>.txt`. The Sunday pass classifies each non-green line and each documented failure of the week:

- **True positive**: the board went red or amber, and the log for that day or the next documents the failure it named.
- **False positive**: it went red or amber and the Sunday pass, reading the evidence, rules nothing was wrong. The ruling and its reason are the row.
- **Missed**: the log documents an agent failure (a row in the catalogue by the same counting rule as the case study) and no check fired within two nights.
- **Never fired**: recorded per check at the end of the window.
- **True negative** is not counted; there is no honest denominator for it and the case study says so.

Ground truth is the folder's own log and ledgers, read by the Sunday maintenance pass, which is a separate scheduled job from the one that runs watchman. Absence of a log entry on a night the jobs did not run is a `missed` for `expected-run` if it did not fire, not a quiet night.

## B. External folders (anyone else's, from 7 Sep)

One row per folder per run. Configured by the author from the owner's description, never by editing the owner's files. The owner rules true or false positive; the author records it verbatim. A finding the owner says they would plausibly have missed is marked as such; that mark is the only line in this file that sells anything.

Weekly metric, and the only one: **external folders with two or more watchman runs in the previous seven days.** Not stars, not downloads, not HN points, not failures on the author's own system.

Targets set before any data: 1 by 13 Sep, 2 to 3 by 5 Oct, 5 by 31 Oct, one paid by 30 Nov. Zero external repeat usage after 30 to 50 targeted contacts kills or repositions the product regardless of how the self-test reads.
