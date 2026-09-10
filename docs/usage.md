# Usage

The command list, running several client folders from one line, the board over the folder the tool came from, and the self-test. [README](../README.md) has the one-line install.

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
watchman intervene --root FOLDER "restated the rent figure" --cost "a turn" --fix "read the summary first"
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

This is a board over the author's own folder, 6 September 2026, second run, real findings. That
folder is "brain-ops": a personal operations system, a few hundred markdown files that scheduled
agent prompts read and rewrite every night. The checks were written against its failures, which is
why the lines below name files you do not have. Read it for the shape of what a board says, not
for the file names:

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

(Since then the incidents sit above a rule and the summary line counts them.) Two of those lines are things that folder's own smoke test did not report: the second dead path in the maintenance prompt, and the eight duplicate numbers in the sealed August log, which that folder had chosen to seal rather than correct. The full text is in `evidence/board-brain-ops-2026-09-06.txt` and the config that produced it is `brain-ops.toml` at the root.

## Prospective test

Everything above is retrospective: a failure happened, a check was written, a similar failure was caught. That is the weakest kind of evidence. So the checks were frozen at 0.2.0 from the first nightly run on 7 September 2026 and run nightly, over the folder it came from, for 28 days until 5 October 2026. The result will be published as a confusion matrix: true positives, false positives, failures it missed, checks that never fired. `evidence/prospective-ledger.md` carries the columns and fills nightly.

## Where it came from

The checks were learned in that folder, run by scheduled agent prompts through August 2026, one check per failure that had actually happened. The rule underneath all of them: a rule an agent is asked to follow is a suggestion; a rule it cannot break is a mechanism. Most of the work is converting the first into the second.
