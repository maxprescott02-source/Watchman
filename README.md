# watchman

The case study this comes from: [29 days of file-backed agents: 125 documented failures](case-study.md).

Trace systems tell you whether a run behaved correctly. Watchman checks whether the durable state the next run will trust is still valid.

It is for file-backed agents: the kind that run a person's or a small business's admin from scheduled prompts, append to a log, rebuild a summary file, and keep ledgers. Between runs, all that survives is the folder, and the next run trusts it. Watchman reads the folder and prints a board.

It does not work over "any folder". It works over folders that follow the conventions `watchman.toml` describes, listed under **The contract** below. Pure standard library, Python 3.10 or later, no dependencies, one config file in the folder it watches. Version 0.1.0, frozen on 7 September 2026 for the prospective test described at the end.

## Install

```
pip install .
```

or run it in place:

```
python3 -m watchman --root /path/to/folder
python3 -m watchman --root /path/to/folder --config elsewhere.toml   # paths inside stay relative to root
```

## Use

```
watchman init demo                    # starter watchman.toml plus fixture files
watchman --root demo                  # run every configured check, print the board
watchman --root demo --json           # the same, as JSON
watchman --root demo --quiet          # only warnings and failures
watchman --root demo --findings findings.md   # also write the board as a findings report, the audit deliverable
watchman --root demo heartbeat        # for a second runner: fails if the last mark is stale
watchman --root demo intervene "restated the rent figure" --cost "a turn" --fix "read now.md first"
watchman --root demo log "Rent paid" --body "Receipt filed."
```

Exit codes: 0 when nothing failed, 1 when any check failed (a warning alone exits 0), 2 when the config or a required file cannot be read. The board prints its own counts; no file states them, and a stated count of checks in any swept document is itself a failure.

Each check is on when its section exists in `watchman.toml` and off when it does not.

## A board

This is the board over the folder the tool came from, 6 September 2026, second run, real findings:

```
[  ok  ] heartbeat              last run 0.0h ago reported 6 passed, 2 warned, 5 failed
[  ok  ] stale-state            now.md folded through Entry 482 · 5 written inside the grace period · 502 entries scanned
[ FAIL ] stated-vs-measured     CLAUDE.md:56 states ~1,300 tokens and names nothing this can measure; teach it or delete the number ...
[ FAIL ] degraded-steps         graph-daily step 16 degraded 14 consecutive nights (limit 8): skipped · suppressed by the session floor ...
[ FAIL ] prompt-drift           2 dead path(s) in 9 prompt(s): ...weekly-model-maintenance.md -> skills/batch · ...weekly-model-maintenance.md -> tasks/SPEC.md
[  ok  ] closed-sets            37 rows across 2 ledger(s), all in their closed sets
[ warn ] intervention-tally     13 row(s) · newest 2026-09-06 (0d ago) · 3 awaiting disposition · last 14d: 9, the 14d before: 4. The rate is rising ...
[ warn ] absence                8 of 32 gone quiet against their own cadence: brain/a-thread-is-not-a-memory.md (last dated 2026-08-24, 13d ago, usual gap 4d) ...
[ FAIL ] append-only-log        duplicate entry numbers [12, 13, 16, 23, 25, 26, 27, 28]. Two writers each computed the next number; allocate under a lock
[  ok  ] citation-resolves      1568 citation(s) in 250 file(s) all resolve against 486 entries
[  ok  ] cannot-list            7 cannot(s) on file, all inside their re-test window
[ FAIL ] read-budget            admin/commitments.md ~17,529 is opened whole and over 16,000 · log/2026-08.md ~355,577 is past 250,000; that is a runaway
[  ok  ] no-vacuous-pass        12 checks each declared a floor and met it

6 passed · 2 warnings · 5 failed · 13 checks ran
```

Two of those lines are things the folder's own smoke test did not report: the second dead path in the maintenance prompt, and the eight duplicate numbers in the sealed August log, which that folder had chosen to seal rather than correct. The full text is in `board-brain-ops-2026-09-06.txt` and the config that produced it is `brain-ops.toml`.

## The contract

What the folder has to look like for each check to mean anything. "Generic" checks need only the file shapes below. "Opinion" checks encode a convention from one folder that you may not share; turn them off by deleting the section.

| Check | Kind | What it needs from the folder |
|---|---|---|
| stale-state | generic | A read-first file whose head carries a marker naming the latest source entry it folded, e.g. `folded through Entry 482`. "Source" means the log: the check parses the marker, reads the newest entry number in `[log].files`, and fails if the marker is behind it by more than `grace_days` of entries. mtime and header dates are never read. |
| degraded-steps | generic | One JSON per job per day in `state_dir`: `{"job","day","ended","artefact","done":{"<step>":{"result":...,"degraded":true}}}`. A step is degraded when it says so, by the flag or by `degraded_marker` appearing in its result text. Nothing is inferred from wording. |
| prompt-drift | generic | Mirror copies of scheduled prompts as markdown. Every path-like token in a mirror must exist relative to root; `exempt` lists tokens that are prose. With `live_dir` set, each mirror is compared byte for byte with the live prompt. |
| closed-sets | generic | Ledgers as markdown tables under `## State` headings, keyed by an `ID` column matching `id`. Every heading present must be in `states`; every ID must parse once. |
| append-only-log | generic | Log files whose entry headings match `[log].heading` with named groups `date` and `n`. Numbers must be distinct and ascending within a file. `watchman log` is the writer: it allocates the next number under `fcntl.flock` and opens the file in append mode. |
| read-budget | generic | Lists of files opened whole and files behind a query tool, with a token ceiling for each (tokens are estimated at 4 characters each). Growth past the size recorded in the previous heartbeat is reported. |
| stated-vs-measured | opinion | Prose claims of the form `~N tokens`, `N entries`, `N tools`, `N passed`, `N checks` in the listed files. Each must name something in `[[stated.measure]]` (a file, measured by size) or a count the log or the board can produce. A claim that names nothing measurable fails: teach it or delete the number. Tolerance is `tolerance`. |
| no-vacuous-pass | opinion | Nothing extra. Every check returns its population and floor; the runner flips a PASS below its floor to FAIL and this line reports the flips. |
| intervention-tally | opinion | A markdown table with `Date, What they had to do, What it cost, What would remove it, Disposition`. Disposition is one of `Rule, Assertion, Tool change, Accepted, Void`, optionally followed by a separator and a reason; `Accepted` without a reason fails. A missing file fails. |
| absence | opinion | Files whose text contains ISO dates. Cadence is the median gap between the distinct dates in a file with at least `min_dates` of them; a file is quiet when today is more than `factor` times that gap past its last date. |
| citation-resolves | opinion | Citations matching `pattern` (default `E123`) in the listed files must resolve to an entry number present in the log. |
| cannot-list | opinion | A markdown table keyed by a `Cannot` column with a `Re-test by` date column. Undated rows fail; expired rows warn. |
| heartbeat | generic | Written by every run: timestamp, counts, measured sizes. `watchman heartbeat` from a second runner fails on a missing or stale mark. |

Absent or malformed input: a missing file that a check depends on is a FAIL with the reason, never a PASS over nothing; a malformed row is named in the message; a config section that is missing turns the check off and the board says how many checks ran.

## The checks

Each check descends from a specific defect. The one-line reason is the module's docstring; the comment under it cites the assertion or entry in the system it came from.

1. **stale-state.** A read-first file is current only if its own marker (`folded through Entry N`) names the latest source entry. Never mtime, never a header date: the job that writes the body writes those too, so they can only prove themselves.
2. **stated-vs-measured.** Any `~N tokens`, `N entries` or `N passed` written in prose about a thing the folder can measure is measured on every run. A stated figure that drifts fails. Fix the number, not the tolerance.
3. **no-vacuous-pass.** Every check declares a population and a floor. A pass over fewer items than its floor is flipped to a failure by the runner. A check over zero items has tested that nothing is wrong with nothing.
4. **degraded-steps.** Scheduled jobs write step-state JSON. A step the job itself declared degraded warns on the first night and fails after eight consecutive nights. A job that ended without its primary artefact fails at once.
5. **prompt-drift.** Mirrors of the scheduled prompts are scanned for paths that no longer exist, which fail. With `live_dir` set, each mirror is compared byte for byte with the live prompt.
6. **closed-sets.** Ledger files declare a closed set of states. A row under any other heading fails; so does a disappeared heading, a malformed ID or a duplicate one. "Noted" is not an outcome.
7. **intervention-tally.** `watchman intervene "..."` records each time the human did the agent's job. A missing tally fails rather than scoring zero; dispositions outside the closed set fail; a rising rate warns.
8. **absence.** Files whose dated lines set their own cadence are reported when they have gone quiet for longer than twice their usual gap. Absence is data.
9. **append-only-log.** `watchman log "..."` allocates the next entry number under a file lock and appends. The check fails on a duplicate number or on numbers that do not ascend within a file.
10. **citation-resolves.** Every `E123`-style citation in the knowledge files must resolve to an entry in the log. A citation that reads perfectly and points nowhere is the failure.
11. **cannot-list.** A `cannots.md` of written-down "the tool cannot X" claims, each with a re-test date. An expired one warns; one with no date fails. Re-test a written-down cannot before obeying it.
12. **read-budget.** Files an agent opens whole are capped at a token estimate, files behind a query tool at a much larger one, and growth past the previous run's recorded size fails.

And the mark that closes "nothing watches the watchman": every run writes a heartbeat with its timestamp, its counts and the sizes it measured. The next run reads it first; a second runner on a different schedule can call `watchman heartbeat` and fail on a stale or missing mark alone.

## The state files the degraded check reads

One JSON per job per day in `state_dir`:

```json
{"job": "nightly", "day": "2026-09-06", "ended": true, "artefact": "now.md",
 "done": {"1-rebuild": {"result": "rebuilt now.md"},
          "2-sweep": {"result": "skipped: floor over cap", "degraded": true}}}
```

The `degraded` flag is the step's own declaration. Nothing here guesses it from the wording of a skip.

## Tests

```
python3 -m unittest discover -s tests
```

## Prospective test

Everything above is retrospective: a failure happened, a check was written, a similar failure was caught. That is the weakest kind of evidence. So this version is frozen at 0.1.0 from 7 September 2026 and runs unchanged, nightly, over the folder it came from until 5 October 2026. The result will be published as a confusion matrix: true positives, false positives, failures it missed, checks that never fired. `prospective-ledger.md` beside this file carries the columns and fills nightly.

## Where it came from

The assertion patterns were learned in brain-ops, a personal operations system run by scheduled agent prompts through August 2026. The rule underneath all of them: a rule an agent is asked to follow is a suggestion; a rule it cannot break is a mechanism. Most of the work is converting the first into the second.
