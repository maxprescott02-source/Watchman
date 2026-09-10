# The checks

What each check needs the folder to look like, and the defect each descends from.

One term recurs below. A **read-first file** is a file something opens before it starts work and then trusts: a summary, a current-state file, a roster, a running total. It is the file that does the most damage when it is quietly out of date, because nothing that reads it can tell. `expected-run` and `stale-state` are the two `install` proposes; the rest are optional conventions from the author's own folder, each on only when its section is in `watchman.toml`. [README](../README.md) has the sixty-second version.

## The contract

What the folder has to look like for each check to mean anything. "Generic" checks need only the file shapes below. "Opinion" checks encode a convention from one folder that you may not share; turn them off by deleting the section.

| Check | Kind | What it needs from the folder |
|---|---|---|
| stale-state | generic | A read-first file whose head carries a marker. Entry mode: the marker's group is a number (`folded through Entry (\d+)`), compared with the newest entry number in `[log].files`, and the file fails when it is behind by more than `grace_days` of entries. Date mode: the group is a date (`Generated (\d{4}-\d{2}-\d{2})`), compared with the newest change among `sources` globs (mtime or a timestamp written inside), or with today when `sources` is empty. Either way the marker is the file's own claim; the file's mtime is never taken as the claim. |
| degraded-steps | generic | One JSON per job per day in `state_dir`: `{"job","day","ended","artefact","done":{"<step>":{"result":...,"degraded":true}}}`. A step is degraded when it says so, by the flag or by `degraded_marker` appearing in its result text. Nothing is inferred from wording. |
| prompt-drift | generic | Mirror copies of scheduled prompts as markdown. Every path-like token in a mirror must exist relative to root; `exempt` lists tokens that are prose. With `live_dir` set, each mirror is compared byte for byte with the live prompt. |
| closed-sets | generic | Ledgers as markdown tables, keyed by the first header cell named in `key`. Either the state is the `## Heading` a row sits under (every state must keep its heading), or `state_column` names a column in the table. Every state must be in `states`; with `id` set, every ID must parse once. |
| append-only-log | generic | Log files whose entry headings match `[log].heading` with named groups `date` and `n`. Numbers must be distinct and ascending within a file. `watchman log` is the writer: it allocates the next number under `fcntl.flock` and opens the file in append mode. |
| read-budget | generic | Lists of files opened whole and files behind a query tool, with a token ceiling for each (tokens are estimated at 4 characters each). Growth past the size recorded in the previous heartbeat is reported. |
| stated-vs-measured | opinion | Prose claims of the form `~N tokens`, `N entries`, `N tools`, `N passed`, `N checks` in the listed files. Each must name something in `[[stated.measure]]` (a file, measured by size) or a count the log or the board can produce. A claim that names nothing measurable fails: teach it or delete the number. Tolerance is `tolerance`. |
| no-vacuous-pass | opinion | Nothing extra. Every check returns its population and floor; the runner flips a PASS below its floor to FAIL and this line reports the flips. |
| intervention-tally | opinion | A markdown table with `Date, What they had to do, What it cost, What would remove it, Disposition`. Disposition is one of `Rule, Assertion, Tool change, Accepted, Void`, optionally followed by a separator and a reason; `Accepted` without a reason fails. A missing file fails. |
| absence | opinion | `files` whose text contains ISO dates, or `dirs` whose file names do (a folder of daily notes is one series). Cadence is the median gap between the distinct dates in a series with at least `min_dates` of them, never fewer than 5 (below that the line is green and says how much history there is); a series is quiet when today is more than `factor` times that gap past its last date. A folder named for a month (`2026-08`) or a day is expected to stop when that period ends, and a folder whose newest date is the last day of its month is not quiet once today is in a later month. |
| citation-resolves | opinion | Citations matching `pattern` (default `E123`) in the listed files must resolve to an entry number present in the log. |
| cannot-list | opinion | A markdown table keyed by a `Cannot` column with a `Re-test by` date column. Undated rows fail; expired rows warn. |
| expected-run | generic | A schedule (`daily HH:MM`, `weekdays HH:MM`, `mon,thu HH:MM`, `monthly <day|last> HH:MM`, or five-field cron) and an `evidence` path or glob the job touches. With `pattern`, the first group of a matching line is read as the timestamp (`2026-08-31T23:32` or `2026-08-31 23:32`, seconds optional); without one, the file's mtime is the evidence. When a summary file carries a `Generated <date>` head line and a log line names the same job, `init --discover` makes the log the evidence and the summary the `[stale_state]` file, so the board can say the job ran but the summary still says an old date. |
| heartbeat | generic | Written by every run: timestamp, counts, measured sizes, open incidents. A first run is an ok line, not a warning. `watchman heartbeat` from a second runner fails on a missing or stale mark. |

Absent or malformed input: a missing file that a check depends on is a FAIL with the reason, never a PASS over nothing; a malformed row is named in the message; a config section that is missing turns the check off and the board says how many checks ran. A section carrying `guessed = true` (which `init --discover` writes where it inferred rather than read) can warn but never fail. Every red line ends in the thing the operator does next.

## The checks

Each check descends from a specific defect. The one-line reason is the module's docstring; the comment under it cites the assertion or entry in the system it came from.

1. **stale-state.** A read-first file is current only if its own marker names the latest source: the entry number it folded through, or the date it was generated measured against the sources it was generated from. Never the file's mtime: the job that writes the body writes that too, so it can only prove itself.
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

13. **expected-run.** A declared schedule and one file the job touches. Fails when the last expected fire has passed and the file was not touched since. The only check that needs no convention from the agent. A `pattern` that matches no line of an existing evidence file is a config problem, reported as such and never as a missed run.

And the mark that closes "nothing watches the watchman": every run writes a heartbeat with its timestamp, its counts and the sizes it measured. The next run reads it first; a second runner on a different schedule can call `watchman heartbeat` and fail on a stale or missing mark alone.

## The state files the degraded check reads

One JSON per job per day in `state_dir`:

```json
{"job": "nightly", "day": "2026-09-06", "ended": true, "artefact": "now.md",
 "done": {"1-rebuild": {"result": "rebuilt now.md"},
          "2-sweep": {"result": "skipped: not enough context left to sweep", "degraded": true}}}
```

The `degraded` flag is the step's own declaration. Nothing here guesses it from the wording of a skip.
