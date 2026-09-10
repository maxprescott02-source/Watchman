# Findings

*watchman 0.1.0 over `~/Desktop/brain-ops`, 2026-09-06. 6 passed, 2 warned, 5 failed, 13 ran.*

## FAIL: append-only-log

duplicate entry numbers [12, 13, 16, 23, 25, 26, 27, 28]. Two writers each computed the next number; allocate under a lock

**Why this check exists.** Every writer that computes the next entry number itself produces duplicates; numbers are allocated under a lock and the log fails on a duplicate or a step backwards.

## FAIL: degraded-steps

graph-daily step 16 degraded 14 consecutive nights (limit 8): skipped · suppressed by the session floor: -2179 tokens of headroom and a mark costs about 8. The headroom is the Sunday · 81 state file(s), 60 step(s) examined

**Why this check exists.** A step that skipped because it could not do its job leaves no bytes anywhere a check looks; age the skips the step itself declared degraded, and fail a job that ended without the thing it exists to produce.

## FAIL: prompt-drift

2 dead path(s) in 9 prompt(s): tasks/brain-ops--weekly-model-maintenance.md -> skills/batch · tasks/brain-ops--weekly-model-maintenance.md -> tasks/SPEC.md

**Why this check exists.** A scheduled prompt that names a path which no longer exists fails silently at 4am; a mirror that drifts from the live prompt is worse than no mirror.

## FAIL: read-budget

admin/commitments.md ~17,956 is opened whole and over 16,000; give it a query tool or split it · log/2026-08.md ~355,577 is past 250,000; behind a tool or not, that is a runaway

**Why this check exists.** What costs context is what enters the window, not what exists; files an agent opens whole are capped, and growth past the last run is a bug wherever it sits.

## FAIL: stated-vs-measured

CLAUDE.md:56 states ~1,300 tokens and names nothing this can measure; teach it or delete the number · CLAUDE.md:78 states ~48,000 tokens and names nothing this can measure; teach it or delete the number · README.md:83 states ~840 tokens and names nothing this can measure; teach it or delete the number · README.md:84 states ~400 tokens and names nothing this can measure; teach it or delete the number

**Why this check exists.** A number written in prose about a thing the folder can measure is measured on every run; a figure nobody has checked since it was typed is the defect.

## WARN: absence

8 of 32 gone quiet against their own cadence (node names withheld from the public copy)

**Why this check exists.** A subject that has gone quiet relative to its own cadence is a finding; runs of silence are data, and nothing else on the board can see them.

## WARN: intervention-tally

13 row(s) · newest 2026-09-06 (0d ago) · 3 awaiting disposition · last 14d: 9, the 14d before: 4. The rate is rising; each row is a rule that was never written

**Why this check exists.** Every time the human did the agent's job is evidence a rule was never written down; count it, and a rising rate is the signal, not the individual row.

## Passed

heartbeat, stale-state, closed-sets, citation-resolves, cannot-list, no-vacuous-pass
