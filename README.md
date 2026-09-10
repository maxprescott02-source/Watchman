# watchman

Watchman tells you the next morning when one of your scheduled file-producing jobs silently stopped updating its output, and tells you what to do next. Trace systems tell you whether a run behaved correctly. Watchman checks whether the durable state the next run will trust is still valid.

It is for one operator with two to ten scheduled jobs that each leave a file behind (a summary, a close, a ledger, a log line), running Claude Cowork, Claude for Small Business, ChatGPT Work or an OpenClaw-style agent, who has already been burnt by a stale output nobody noticed. And for the consultant who set that up for five to fifty clients and carries the blame when it drifts. If you have an observability platform and an engineer to wire it, LangSmith, Braintrust, Langfuse or Arize will do most of this over traces; watchman is for the folder with nobody watching it. Pure standard library, Python 3.10 or later, no dependencies, one config file in the folder it watches, and it proposes that file itself. Version 0.2.0, frozen from the first nightly run on 7 September 2026 for the 28-day self-test. The case study it comes from: [29 days of file-backed agents: 125 documented failures](case-study.md).

If you would rather read one page than a README: [`index.html`](index.html) is a plain-English explainer of the failure this is built for, what it leaves in your folder, and three questions that tell you whether it is any use to you. Open it in a browser after cloning; it is a single file and needs no network.

## Sixty seconds: what it catches that a passing run does not

Your nightly job rebuilds `now.md` from the log. Tonight the log reached Entry 482. The rebuild ran, exited 0, and wrote a file whose head still says `folded through Entry 470`, because the step that folds new entries skipped itself over a token budget and recorded the skip in a place nothing reads. Every session tomorrow opens `now.md` first and trusts it.

Your run logs say: `nightly ok, 2.1s`. Your smoke test says: `now.md present, modified 03:02`. Watchman says:

```
[ FAIL ] stale-state   now.md folded through Entry 470, but 12 newer entries are not in it. Every session reads it without them
[ FAIL ] degraded-steps nightly step 2-sweep degraded 1 night: skipped: floor over cap
```

Trace evals inspect what happened during a run. Watchman verifies durable state before another run trusts it, from the files the agent already leaves: expected-run needs nothing from the agent; degraded-steps needs the job to write its own step-state.

## Install

One line. `FOLDER` is the folder your agent works over. Run it from this directory (or `pip install .` first, and `watchman` replaces `python3 -m watchman`).

```
python3 -m watchman install FOLDER
```

then read `FOLDER/WATCHMAN.md` each morning; it only lists what needs you.

`install` reads the folder and proposes `FOLDER/watchman.toml` (asking nothing), says which checks fit, prints the board, writes `WATCHMAN.md`, and schedules the nightly run (launchd on a Mac, cron elsewhere). It ends with "Done. Watchman checks FOLDER every night at 01:31 and writes WATCHMAN.md when something needs you." only once it has read the schedule back; if the scheduler refused or is missing, the last two lines are the line to paste and `WATCHMAN IS NOT SCHEDULED. ...`, and it exits 3. Where it guessed, a section carries `guessed = true` and can warn but never fail until `python3 -m watchman confirm --root FOLDER` settles it. If nothing in the folder carries a timestamp, a dated line or a rebuilt file that a scheduled job leaves behind, there is nothing here for it to check: it says so, refuses to schedule itself, and exits 4, rather than reporting `Healthy: nothing needs you.` every morning over a folder it is not watching. `--at HH:MM` moves the time; `--no-schedule` does everything but the last step. If you use Cowork's own scheduler and will not touch cron, `launch/cowork-task-prompt.md` has a task you can paste.

## WATCHMAN.md

It looks like this when something is wrong, and says `Healthy: nothing needs you.` when nothing is (the file stays; a file that disappears looks like a tool that died). Its first line is always when watchman last ran, so a reader can tell when watchman itself has stopped:

```
Last checked: 2026-09-07 06:02 UTC+10

- new: inbox-summary ran at 2026-09-07 06:01 but inbox-summary.md still says 2026-09-04. The job ran without updating its output; check what it wrote and where.
- new: ledger-sync left no expected evidence for its Mon 07 Sep 07:00 run (newest evidence 2026-09-06 07:00): it may not have run, this machine may have been off or asleep, or it may have run without updating runs.log. Check the ledger-sync job. If it is safe to rerun, run it now; if it already ran, check why runs.log was not updated.

full board: .watchman/last-board.txt
```

One line per underlying thing, not per check: a job's log line and the summary it failed to rebuild are one incident; two jobs that share a log are two. Each carries a state against the previous night (`new`, `ongoing (since <date>)`, or `resolved`, printed once) and ends in the thing to do.

## If your scheduled task has ever silently stopped

`expected-run` needs nothing from your agent. Declare when a job should fire and one file it touches:

```toml
[[expected]]
name = "nightly close"
schedule = "daily 03:00"          # or "weekdays 09:00", "mon,thu 18:30", "monthly last 23:30", or 5-field cron
evidence = "reports/close-*.md"   # a glob it writes, or a log it appends to
grace_minutes = 90
```

For a log the job appends to, add a `pattern` whose first group captures the timestamp, in either form the log uses (`2026-08-31T23:32 close ok` or `2026-08-31 23:32 close ok`):

```toml
pattern = '^(\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?)?)\s+close\b'
```

Without a pattern, the file's modification time is the evidence. A pattern that matches no line of an existing file is reported as a config problem to fix, never as a missed run.

If the last expected fire has passed and nothing matching `evidence` was touched since, the board goes red with the time it was due, worded as "left no expected evidence for its <due> run: it may not have run, this machine may have been off or asleep, or it may have run without updating <file>", because from the folder those three look the same, and the action is to check the job, rerun it if that is safe, and if it already ran, find out why the file did not move. A scheduler that says healthy is not sufficient evidence; the file the job touches is. This is the detector for the pattern in anthropics/claude-code issues #55378 and #47899.

## Step by step

The same path as separate commands, for people who want to see each step:

```
python3 -m watchman init --discover FOLDER         # reads the folder, writes FOLDER/watchman.toml, asks nothing
python3 -m watchman doctor --root FOLDER           # one line per section: can it check this folder, and what is missing
python3 -m watchman --root FOLDER                  # the board. Red lines name the file and say what to do
```

The full command list, running several client folders from one line, and the self-test are in [docs/usage.md](docs/usage.md). Tests: `python3 -m unittest discover -s tests`.

## Advanced checks

`expected-run` and `stale-state` are the two the installer proposes. The others (`degraded-steps`, `prompt-drift`, `closed-sets`, `append-only-log`, `read-budget`, `stated-vs-measured`, `no-vacuous-pass`, `intervention-tally`, `absence`, `citation-resolves`, `cannot-list`, and the `heartbeat` every run writes) are optional conventions from the author's own folder, each on only when its section is in `watchman.toml`. What each needs the folder to look like, and the defect each descends from, is in [docs/checks.md](docs/checks.md).

See [NOTICE.md](NOTICE.md) about the name.
