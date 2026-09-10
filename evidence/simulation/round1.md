# Round 1: the operator, on the stranger's folder

Persona: the operator from `user.md`. Not an engineer. Has a folder at `/tmp/stranger` that a scheduled agent works over (a daily inbox summary, a month-end close, a client list, a task list, a run log, two prompts, a notes folder that stopped twelve days ago). Fifteen minutes. Reads only the first screen of the README: the title, the sixty-second proof, the `expected-run` section, Install, Use.

Clock started 23:40. Version under test: 0.1.1 as checked out, before any change.

## The folder

```
clients.csv            close/2026-08-31.md      inbox-summary.md
notes/2026-08-14.md    notes/2026-08-18.md      notes/2026-08-21.md    notes/2026-08-25.md
prompts/daily.md       prompts/month-end.md     runs.log               tasks.md
```

`inbox-summary.md` opens with `Generated 2026-09-05 06:00 from 14 emails`. `runs.log` ends with `2026-09-05T06:01:12 inbox-summary ok`. It is 6 September, 23:50 local. The daily job did not run this morning. That is the red line the persona is looking for, though the persona does not yet know it.

## What I typed, what came back

### 1. The obvious first command

The Install block says `python3 -m watchman --root /path/to/folder`. So:

```
$ python3 -m watchman --root /tmp/stranger
no watchman.toml in /tmp/stranger. Run `watchman init /tmp/stranger` to write a starter.
exit=1
```

Fine, it told me what to do next. I did it.

### 2. `init` wrote thirteen files into my real folder

```
$ python3 -m watchman init /tmp/stranger
wrote 13 files into /tmp/stranger/ · run: watchman --root /tmp/stranger

$ ls /tmp/stranger
admin  brain  cannots.md  clients.csv  close  docs  inbox-summary.md  interventions.md
log  notes  now.md  prompts  runs.log  state  subjects  tasks  tasks.md  watchman.toml
```

Friction, severe. I now have `now.md`, `admin/`, `brain/`, `subjects/`, `interventions.md`, `cannots.md` and a `log/` folder in the folder my agent works over. My agent's prompt says "tick anything in `tasks.md`"; there is now also a `tasks/` folder next to it. Nothing warned me that `init` on a folder that already has things in it would fill it with someone else's demo. The Use block says `watchman init demo  # starter watchman.toml plus fixture files`; I read "fixture files" as something about the config, not as eleven new files about coffee grinders and Pokemon.

### 3. The board is about the demo, not about me

```
$ python3 -m watchman --root /tmp/stranger
[ warn ] heartbeat              no heartbeat at .watchman/heartbeat.json; either this is the first run or nothing has been running
[ FAIL ] stale-state            now.md folded through Entry 3, but 1 older entry is not in it: [4]. Every session reads it without them
[  ok  ] stated-vs-measured     1 measurable(s) under ceiling (now.md ~51) · 1 stated number(s) all within 30%
[ warn ] degraded-steps         1 step(s) degraded, longest nightly step 2-sweep at 2 of 8 nights: skipped · DEGRADED: session floor over cap · 2 state file(s), 2 step(s) examined
[  ok  ] expected-run           every declared job left evidence after its last expected fire · 1 job(s) declared, 1 evidenced, 0 inside grace
[  ok  ] prompt-drift           3 path(s) across 1 prompt(s) all resolve · no live_dir set, mirrors unverified
[ FAIL ] closed-sets            admin/commitments.md: 'C003' carries 'Noted', outside ['Done', 'Dropped', 'Open', 'Void']
[ warn ] intervention-tally     5 row(s) · newest 2026-09-05 (1d ago) · 2 awaiting disposition · last 14d: 4, the 14d before: 1. The rate is rising; each row is a rule that was never written
[ warn ] absence                1 of 2 gone quiet against their own cadence: subjects/pokemon.md (last dated 2026-08-07, 30d ago, usual gap 7d)
[  ok  ] append-only-log        5 entries across 1 file(s), all distinct and ascending · newest 2026-09-06
[ FAIL ] citation-resolves      1 of 2 citation(s) resolve to no entry: brain/notes.md:3 E009. Read the number back after the append; never assume what it will allocate
[ warn ] cannot-list            1 of 2 cannot(s) past their re-test date: 'edit live prompts from a cloud session' (due 2026-08-27). Re-test a written-down cannot before obeying it
[  ok  ] read-budget            3 file(s) opened whole under 16,000 · 1 behind a tool under 250,000 · session floor ~51/14,000
[  ok  ] no-vacuous-pass        13 checks each declared a floor and met it

6 passed · 5 warnings · 3 failed · 14 checks ran
```

Three red lines and none of them is about a file I own. `now.md folded through Entry 3`: I do not have a `now.md`, or entries. `admin/commitments.md: 'C003' carries 'Noted'`: not my file. `expected-run` is green because the demo's own `state/nightly-*.json` was written a second ago. My inbox summary, which did not run this morning, is not mentioned anywhere. Eight minutes gone.

Words on the board I did not understand: "folded through Entry", "session floor", "degraded", "closed sets", "intervention tally", "disposition", "no-vacuous-pass", "citation", "cannot(s)". I did not know which of the fourteen lines I was allowed to ignore.

### 4. Cleaning up by hand

I deleted the eleven demo files and folders by hand and started again. Nothing told me which files were the demo's; I had to compare against my memory of the folder. The persona in `user.md` would have stopped here. I carried on because I was asked to reach a red line.

### 5. Writing the `[[expected]]` block from the README

The README's `expected-run` block is the one thing on the first screen that looks like it needs nothing from me but a schedule and a file. I copied it and changed the names:

```toml
[[expected]]
name = "inbox summary"
schedule = "daily 06:00"
evidence = "inbox-summary.md"
grace_minutes = 90
```

```
$ python3 -m watchman --root /tmp/stranger
[ warn ] heartbeat              no heartbeat at .watchman/heartbeat.json; either this is the first run or nothing has been running
[ FAIL ] expected-run           1 job(s) fired with no evidence: inbox summary: due Sun 06:00, newest evidence 2026-09-04 20:01. A schedule that says healthy is not evidence; the file the job touches is · 1 job(s) declared, 0 evidenced, 0 inside grace
[  ok  ] no-vacuous-pass        2 checks each declared a floor and met it

1 passed · 1 warnings · 1 failed · 3 checks ran
```

A real red line, at minute twelve. But: `newest evidence 2026-09-04 20:01`. The file says `Generated 2026-09-05 06:00` and Finder says it was modified 5 September at 06:01. Watchman is in UTC because I did not write a `[watchman] utc_offset_hours` line, and nothing on the first screen told me that or told me the time on the board was not my time. I spent two minutes wondering whether the file had been touched at eight at night by something else. `due Sun 06:00` is in the same unknown zone.

### 6. The month-end job

The README says schedules are `"daily HH:MM"`, `"weekdays HH:MM"`, `"mon,thu HH:MM"`, or five-field cron. My second job runs on the last day of the month. I guessed:

```toml
[[expected]]
name = "month end close"
schedule = "monthly"
evidence = "close/*.md"
```

```
[ FAIL ] expected-run           2 job(s) fired with no evidence: inbox summary: due Sun 06:00, newest evidence 2026-09-04 20:01; month end close: unreadable schedule 'monthly'. A schedule that says healthy is not evidence; the file the job touches is · 2 job(s) declared, 0 evidenced, 0 inside grace
```

`unreadable schedule 'monthly'` and nothing about what would be readable. I do not know cron. A real job merged into the same red line as a config mistake, so the count "2 job(s) fired with no evidence" is wrong: one fired with no evidence, one was never checked.

### 7. A typo

I mistyped `schedule` as `schedul` while editing:

```
[ FAIL ] expected-run           1 job(s) fired with no evidence: inbox summary: 'schedule'. A schedule that says healthy is not evidence; the file the job touches is · 1 job(s) declared, 0 evidenced, 0 inside grace
```

`inbox summary: 'schedule'` is a Python KeyError shown raw. It does not say "the job has no schedule line".

### 8. Trying the sixty-second check on my own summary file

The sixty-second proof is about a file whose head says when it was last rebuilt. Mine says `Generated 2026-09-05 06:00`. The starter toml I saw earlier had `[stale_state]` with `marker = 'folded through Entry (\d+)'`, so I tried the same shape with my line:

```toml
[stale_state]
file = "inbox-summary.md"
marker = 'Generated (\d{4}-\d{2}-\d{2})'
```

```
[ FAIL ] stale-state            the check itself raised ValueError: invalid literal for int() with base 10: '2026-09-05'. A check that crashes is not a check that passed
```

The one check the README leads with cannot read a date. It wants an entry number and a log that I do not have. The contract table (below the first screen, which the persona would not have read) says this, but the sixty-second proof does not say "only if your file counts log entries".

Clock stopped at 23:56. Sixteen minutes, one meaningful red line (the missed inbox summary), reached only by writing toml by hand, which `user.md` says this persona will not do.

## Friction, ranked

1. `init DIR` on a folder that already has files writes the demo into it. Must not happen. `init` should look at what is there and propose a config, or refuse.
2. There is no way to get a config from the folder's own shape. Every path the starter names is someone else's.
3. `stale-state` cannot read a date marker; it crashes with a Python error on the very file the README's proof is about.
4. Times on the board are UTC unless told otherwise, with no hint that they are.
5. `unreadable schedule 'monthly'` names no readable forms; there is no monthly form at all, and month-end is the small-business job.
6. A config mistake in one `[[expected]]` job is reported in the same sentence, and counted the same, as a job that really went silent.
7. A missing key is shown as a raw `'schedule'`.
8. Nothing tells me which of the fourteen lines matter for my folder before they are on the board, so I cannot tell a check that does not apply from a check that found something.
9. Nothing on the first screen says how to make it run every night. The persona does not know cron.
