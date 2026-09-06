# watchman

Watchman tells you the next morning when one of your scheduled file-producing jobs silently stopped updating its output, and tells you what to do next. Trace systems tell you whether a run behaved correctly. Watchman checks whether the durable state the next run will trust is still valid.

The case study this comes from: [29 days of file-backed agents: 125 documented failures](case-study.md).

It is for file-backed agents: the kind that run a person's or a small business's admin from scheduled prompts, append to a log, rebuild a summary file, and keep ledgers. Between runs, all that survives is the folder, and the next run trusts it. Watchman reads the folder and prints a board. Pure standard library, Python 3.10 or later, no dependencies, one config file in the folder it watches, and it proposes that file itself. Version 0.2.0: incidents with state across nights, `WATCHMAN.md`, and `install`, added 7 September 2026 after an outside review of the onboarding. The checks are the 0.1.1 set from the prospective test described at the end; what changed is how their findings are folded and worded, that `absence` wants five dated files before it calls a cadence, and that a guessed section cannot fail.

## Who it is for

One operator with two to ten scheduled jobs that each leave a file behind (a summary, a close, a ledger, a log line), running Claude Cowork, Claude for Small Business, ChatGPT Work or an OpenClaw-style agent, who has already been burnt by a stale output nobody noticed. And the consultant who set that up for five to fifty clients and carries the blame when it drifts. If you have an observability platform and an engineer to wire it, LangSmith, Braintrust, Langfuse or Arize will do most of this over traces; watchman is for the folder with nobody watching it. If you use Cowork's own scheduler and will not touch cron, `launch/cowork-task-prompt.md` has a task you can paste.

## Sixty seconds: what it catches that a passing run does not

Your nightly job rebuilds `now.md` from the log. Tonight the log reached Entry 482. The rebuild ran, exited 0, and wrote a file whose head still says `folded through Entry 470`, because the step that folds new entries skipped itself over a token budget and recorded the skip in a place nothing reads. Every session tomorrow opens `now.md` first and trusts it.

Your run logs say: `nightly ok, 2.1s`. Your smoke test says: `now.md present, modified 03:02`. Watchman says:

```
[ FAIL ] stale-state   now.md folded through Entry 470, but 12 newer entries are not in it. Every session reads it without them
[ FAIL ] degraded-steps nightly step 2-sweep degraded 1 night: skipped: floor over cap
```

Trace evals inspect what happened during a run. Watchman verifies durable state before another run trusts it. That is the whole difference, and it is why it needs no telemetry from the agent: it reads the files the agent already leaves.

## From nothing to a red line

Two lines. `FOLDER` is the folder your agent works over. Run them from this directory (or `pip install .` first, and `watchman` replaces `python3 -m watchman`).

```
python3 -m watchman install FOLDER
```

then read `FOLDER/WATCHMAN.md` each morning; it only lists what needs you.

`install` reads the folder and proposes `FOLDER/watchman.toml` (asking nothing), says which checks fit, prints the board, writes `WATCHMAN.md`, and schedules the nightly run (launchd on a Mac, cron elsewhere). It ends with "Done. Watchman checks FOLDER every night at 01:31 and writes WATCHMAN.md when something needs you." only once it has read the schedule back (`crontab -l` shows the line, or `launchctl list` shows the label); if the scheduler refused or is missing, the last two lines are the crontab line to paste and `WATCHMAN IS NOT SCHEDULED. ...`, and it exits 3. If any section was guessed it says so, with the `confirm` command that settles it. `--at HH:MM` moves the time; `--no-schedule` does everything but the last step.

`WATCHMAN.md` looks like this when something is wrong, and says `Healthy: nothing needs you.` when nothing is (the file stays; a file that disappears looks like a tool that died). Its first line is always when watchman last ran, so a reader can tell when watchman itself has stopped:

```
Last checked: 2026-09-07 06:02 UTC+10

- new: inbox-summary left no expected evidence for its Sun 06 Sep 06:00 run (newest evidence 2026-09-05 06:00): it may not have run, this machine may have been off or asleep, or it may have run without updating inbox-summary.md; inbox-summary.md is 2 days old (it says 2026-09-05, today is 2026-09-07). Check the inbox-summary job. If it is safe to rerun, run it now; if it already ran, check why inbox-summary.md was not updated.
- new: prompts/daily.md names invoices/, which does not exist. Fix the path in prompts/daily.md or create invoices/.

full board: .watchman/last-board.txt
```

One line per underlying thing, not per check: a stale summary and the missed run that would have rebuilt it are one incident. Each carries a state against the previous night (`new`, `ongoing (since <date>)`, or `resolved`, printed once) and ends in the thing to do.

### Step by step

The same path as five commands, for people who want to see each step:

```
pip install .                                      # optional; or run in place from here
python3 -m watchman init --discover FOLDER         # reads the folder, writes FOLDER/watchman.toml, asks nothing
python3 -m watchman doctor --root FOLDER           # one line per section: can it check this folder, and what is missing
python3 -m watchman --root FOLDER                  # the board. Red lines name the file and say what to do
python3 -m watchman install-cron --root FOLDER     # the one line that runs it nightly; on a Mac add --write
```

`init --discover` looks for a summary file with a "Generated <date>" line in its head, a log where lines start with a timestamp, prompts that name paths in backticks, folders of dated notes, and tables with a Status column. Each becomes a section in `watchman.toml` with a comment saying why. Where it guessed, the section carries `guessed = true`: that check can warn but never fail, and its line starts with `unconfirmed:`, until you delete the line (`python3 -m watchman confirm --root FOLDER` lists them, one line each with what it was guessed from, the `confirm --all` that accepts them all and the toml line to edit instead; `confirm --all` deletes every one). Delete a section to turn that check off. Times on the board are your machine's local time unless `utc_offset_hours` says otherwise.

What the board looks like over a small-business folder whose daily summary did not run this morning and whose month-end prompt names a folder that no longer exists:

```
new:         inbox-summary left no expected evidence for its Sun 06 Sep 06:00 run (newest evidence 2026-09-05 06:00): it may not have run, this machine may have been off or asleep, or it may have run without updating inbox-summary.md; inbox-summary.md is 2 days old (it says 2026-09-05, today is 2026-09-07). Check the inbox-summary job. If it is safe to rerun, run it now; if it already ran, check why inbox-summary.md was not updated.
new:         prompts/daily.md names invoices/, which does not exist. Fix the path in prompts/daily.md or create invoices/.
new:         prompts/month-end.md names exports/xero.csv, which does not exist. Fix the path in prompts/month-end.md or create exports/xero.csv.
------------------------------------------------------------------------
[  ok  ] heartbeat              first run over this folder; the next run will compare against it
[ warn ] stale-state            unconfirmed: inbox-summary.md is 2 days old (it says 2026-09-05, today is 2026-09-07), grace 1. The rebuild may not have run, this machine may have been off or asleep, or the rebuild may have run without updating it; anything reading the file does not know. Check the job that writes inbox-summary.md; it was due by 2026-09-06. If it is safe to rerun, run it now; if it already ran, check why inbox-summary.md was not updated.
[ FAIL ] expected-run           1 job fired with no evidence: inbox-summary left no expected evidence for its Sun 06 Sep 06:00 run (newest evidence 2026-09-05 06:00): it may not have run, this machine may have been off or asleep, or it may have run without updating inbox-summary.md. A scheduler that says healthy is not sufficient evidence; the file the job touches is · 2 jobs declared, 1 evidenced, 0 inside grace · times are UTC+10. Check the inbox-summary job. If it is safe to rerun, run it now; if it already ran, check why inbox-summary.md was not updated.
[ FAIL ] prompt-drift           2 dead paths in 2 prompts: prompts/daily.md -> invoices/ · prompts/month-end.md -> exports/xero.csv. The agent is told to read something that is not there. Fix the path in the prompt or create what it names.
[  ok  ] closed-sets            4 rows across 1 ledger, all in their closed sets
[  ok  ] absence                not enough history to know the cadence yet (4 dated files; 5 needed per series)
[  ok  ] no-vacuous-pass        6 checks each declared a floor and met it

3 incidents (3 new) · 2 checks failed · 1 warned · 7 ran (4 confirmed, 3 unconfirmed)
```

## If your scheduled task has ever silently stopped

The check that needs nothing from your agent at all is `expected-run`. Declare when a job should fire and one file it touches:

```toml
[[expected]]
name = "nightly close"
schedule = "daily 03:00"          # or "weekdays 09:00", "mon,thu 18:30", "monthly last 23:30", or 5-field cron
evidence = "reports/close-*.md"   # a glob it writes, or a log it appends to
grace_minutes = 90
```

For a log the job appends to, add `pattern = '^(\S+) close'` and the captured group is read as the timestamp; without a pattern, the file's modification time is the evidence.

If the last expected fire has passed and nothing matching `evidence` was touched since, the board goes red with the time it was due, worded as "left no expected evidence for its <due> run: it may not have run, this machine may have been off or asleep, or it may have run without updating <file>", because from the folder those three look the same, and the action is to check the job, rerun it if that is safe, and if it already ran, find out why the file did not move. A scheduler that says healthy is not sufficient evidence; the file the job touches is. This is the detector for the pattern in anthropics/claude-code issues #55378 and #47899.

## Install

```
pip install .
```

or run it in place from this directory:

```
python3 -m watchman --root /path/to/folder
python3 -m watchman --root /path/to/folder --config elsewhere.toml   # paths inside stay relative to root
```

## Use

```
watchman install FOLDER               # discover, doctor, the board, WATCHMAN.md, and the nightly schedule, in one go
watchman init --discover FOLDER       # propose FOLDER/watchman.toml from what is there; existing toml is kept, proposal goes beside it
watchman init --demo sandbox          # a demo folder of fixture files that produces a mixed board (never on top of your files); `demo/` here is one already
watchman doctor --root FOLDER         # per section: ready, or what to fix. Reads only, exits 0. --verbose names the checks that are off
watchman confirm --root FOLDER        # list the guessed sections; --all deletes every `guessed = true` line so those checks can fail
watchman --root FOLDER                # run every configured check, print the board
watchman --root FOLDER --json         # the same, as JSON
watchman --root FOLDER --quiet        # only warnings and failures
watchman --root FOLDER --findings reports/{name}-{date}.md   # also write the findings report; {name} is the folder's name
watchman --root A --root B            # several folders, one board each, exit code is the worst
watchman install-cron --root FOLDER   # print the crontab line; on a Mac, --write saves a launchd plist and prints the launchctl line
watchman heartbeat --root FOLDER      # for a second runner: fails if the last mark is stale
watchman intervene --root FOLDER "restated the rent figure" --cost "a turn" --fix "read now.md first"
watchman log --root FOLDER "Rent paid" --body "Receipt filed."
```

`--root`, `--config`, `--findings`, `--json` and `--quiet` may go before or after the command word.

Exit codes: 0 when nothing failed, 1 when any check failed (a warning alone exits 0), 2 when the config or a required file cannot be read. The board prints its own counts; no file states them, and a stated count of checks in any swept document is itself a failure.

Each check is on when its section exists in `watchman.toml` and off when it does not.

Every run writes `WATCHMAN.md` at the root of the folder (unresolved incidents only, or `Healthy: nothing needs you.`), the full board to `.watchman/last-board.txt`, and the heartbeat. `attention_file = ""` under `[watchman]` turns the first off; any other name moves it.

### Several clients from one place

An implementer with client folders keeps one `watchman.toml` in each and runs them all from one line:

```
watchman init --discover /clients/doyle /clients/northside /clients/bayside
watchman doctor --root /clients/doyle --root /clients/northside --root /clients/bayside
watchman install-cron --root /clients/doyle --root /clients/northside --root /clients/bayside --findings '/reports/{name}-{date}.md'
```

The last command prints the one crontab line (or, on a Mac with `--write`, one launchd plist) that runs every folder nightly. Each client gets a board under its own `== /clients/name` heading, a findings report named after the folder (`{root}` instead of `{name}` if two clients share a folder name), and a heartbeat in its own `.watchman/`. The board text of the whole run lands beside the reports. The findings report is the deliverable: the client's name in the title, one section per red or amber line with the check's reason for existing, then the list of what passed.

## A board

This is the board over the folder the tool came from, 6 September 2026, second run, real findings:

```
[  ok  ] heartbeat              last run 0.0h ago reported 6 passed, 2 warned, 5 failed
[  ok  ] stale-state            now.md folded through Entry 482 · 5 written inside the grace period · 502 entries scanned
[ FAIL ] stated-vs-measured     CLAUDE.md:56 states ~1,300 tokens and names nothing this can measure; teach it or delete the number ...
[ FAIL ] degraded-steps         graph-daily step 16 degraded 14 consecutive nights (limit 8): skipped · suppressed by the session floor ...
[ FAIL ] prompt-drift           2 dead paths in 9 prompts: ...weekly-model-maintenance.md -> skills/batch · ...weekly-model-maintenance.md -> tasks/SPEC.md
[  ok  ] closed-sets            37 rows across 2 ledgers, all in their closed sets
[ warn ] intervention-tally     13 rows · newest 2026-09-06 (0d ago) · 3 awaiting disposition · last 14d: 9, the 14d before: 4. The rate is rising ...
[ warn ] absence                8 of 32 gone quiet against their own cadence: brain/a-thread-is-not-a-memory.md (last dated 2026-08-24, 13d ago, usual gap 4d) ...
[ FAIL ] append-only-log        duplicate entry numbers [12, 13, 16, 23, 25, 26, 27, 28]. Two writers each computed the next number; allocate under a lock
[  ok  ] citation-resolves      1568 citations in 250 files all resolve against 486 entries
[  ok  ] cannot-list            7 cannots on file, all inside their re-test window
[ FAIL ] read-budget            admin/commitments.md ~17,529 is opened whole and over 16,000 · log/2026-08.md ~355,577 is past 250,000; that is a runaway
[  ok  ] no-vacuous-pass        12 checks each declared a floor and met it

6 passed · 2 warnings · 5 failed · 13 checks ran
```

(That is the 0.1.1 board shape; from 0.2.0 the incidents sit above a rule and the summary line counts them.) Two of those lines are things the folder's own smoke test did not report: the second dead path in the maintenance prompt, and the eight duplicate numbers in the sealed August log, which that folder had chosen to seal rather than correct. The full text is in `board-brain-ops-2026-09-06.txt` and the config that produced it is `brain-ops.toml`.

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
| absence | opinion | `files` whose text contains ISO dates, or `dirs` whose file names do (a folder of daily notes is one series). Cadence is the median gap between the distinct dates in a series with at least `min_dates` of them, never fewer than 5 (below that the line is green and says how much history there is); a series is quiet when today is more than `factor` times that gap past its last date. |
| citation-resolves | opinion | Citations matching `pattern` (default `E123`) in the listed files must resolve to an entry number present in the log. |
| cannot-list | opinion | A markdown table keyed by a `Cannot` column with a `Re-test by` date column. Undated rows fail; expired rows warn. |
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

13. **expected-run.** A declared schedule and one file the job touches. Fails when the last expected fire has passed and the file was not touched since. The only check that needs no convention from the agent.

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

Everything above is retrospective: a failure happened, a check was written, a similar failure was caught. That is the weakest kind of evidence. So the checks were frozen at 0.1.1 on 7 September 2026 (0.1.0 plus `expected-run`, added the same day before the window opened) and run nightly, over the folder it came from until 5 October 2026. The result will be published as a confusion matrix: true positives, false positives, failures it missed, checks that never fired. `prospective-ledger.md` beside this file carries the columns and fills nightly. The 0.2.0 changes to wording, incident folding, the absence floor and the guessed cap are recorded there as a break in the series on the night they landed.

## Where it came from

The assertion patterns were learned in brain-ops, a personal operations system run by scheduled agent prompts through August 2026. The rule underneath all of them: a rule an agent is asked to follow is a suggestion; a rule it cannot break is a mechanism. Most of the work is converting the first into the second.
