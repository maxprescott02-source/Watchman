# Prospective ledger, watchman 0.1.0 over brain-ops, 7 Sep to 5 Oct 2026

*One row per night. Filled by the 4am sweeper from the saved board and the next day's log. Nothing in watchman changes during the window; a bug found in it is a row here, not a fix.*

| Date | Check | Outcome | What happened | Cite |
|---|---|---|---|---|
| 2026-09-06 | prompt-drift | true positive (example row) | flagged tasks/SPEC.md in the maintenance prompt; the folder's own check had not | board-brain-ops-2026-09-06.txt |

Outcomes: `true positive` (it fired and the failure was real), `false positive` (it fired and nothing was wrong), `missed` (a failure was documented in the log and no check fired), `never fired` (recorded at the end of the window per check).
