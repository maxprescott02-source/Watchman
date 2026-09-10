# Round 4: the operator, same folder, one command

Same persona as rounds 1 and 2 (`user.md`: not an engineer, reads only the first screen, will not write toml). `/tmp/stranger` recreated from the round-1 description: `inbox-summary.md` opening with `Generated 2026-09-05 06:00 from 14 emails`, `runs.log` with six `inbox-summary ok` lines ending 5 September 06:01 and one `month-end-close ok` on 31 August 23:30, `close/2026-08-31.md` with four rows under a Status column, `clients.csv`, `tasks.md`, `prompts/daily.md` (names `invoices/`, which does not exist), `prompts/month-end.md` (names `exports/xero.csv`, which does not exist), and four notes dated 14 to 25 August. Nothing else in the folder. Version under test: 0.2.0, this working copy, Linux sandbox, machine zone UTC+10.

Clock started 00:39, Monday 7 September. The daily job did not run on Sunday morning. The first screen of the README now shows one command and one sentence, so that is all I typed.

## Command 1

```
$ python3 -m watchman install /tmp/stranger
looked at /tmp/stranger and guessed:
  [stale_state]: inbox-summary.md carries 'Generated 2026-09-05 06:00' in its head
  [[expected]] inbox-summary: daily 06:00, evidence inbox-summary.md
  [[expected]] month-end-close: monthly last 23:30, evidence runs.log (schedule guessed)
  [prompts]: 2 file(s) naming paths in backticks: prompts/daily.md, prompts/month-end.md
  [absence]: notes/ (4 dated files)
  [[ledgers]]: close/2026-08-31.md, column 'Status' with states ['Outstanding', 'Paid', 'Partial']
wrote /tmp/stranger/watchman.toml · sections marked `guessed = true` warn but never fail until you confirm them (`python3 -m watchman confirm --root /tmp/stranger`)

ready  [watchman]       heartbeat          times are UTC+10 (from the toml); heartbeat goes to .watchman/heartbeat.json
ready  [stale_state]    stale-state        guessed, warns but never fails until confirmed · inbox-summary.md says 2026-09-05; measured against today, grace 1 day(s) (date mode)
ready  [[expected]]     expected-run       inbox-summary: daily 06:00, last due Sun 06 Sep 06:00, 1 matching line(s) in inbox-summary.md
ready  [[expected]]     expected-run       guessed, warns but never fails until confirmed · month-end-close: monthly last 23:30, last due Mon 31 Aug 23:30, 1 matching line(s) in runs.log
ready  [prompts]        prompt-drift       2 prompt(s), 5 path(s) in backticks
ready  [[ledgers]]      closed-sets        guessed, warns but never fails until confirmed · close/2026-08-31.md: 4 row(s), states ['Outstanding', 'Paid', 'Partial']
ready  [absence]        absence            0 file(s) and 1 folder(s) with their own cadence

7 ready · 0 to fix · 6 checks fit this folder. The others need conventions this folder does not use, and stay off.

new:         inbox-summary did not run, or this machine was off or asleep at Sun 06 Sep 06:00 (newest evidence 2026-09-05 06:00); inbox-summary.md is 2 day(s) old (it says 2026-09-05, today is 2026-09-07). Re-run the job inbox-summary; it was due Sun 06 Sep 06:00. If it ran, check why it did not update inbox-summary.md.
new:         prompts/daily.md names invoices/, which does not exist. Fix the path in prompts/daily.md or create invoices/.
new:         prompts/month-end.md names exports/xero.csv, which does not exist. Fix the path in prompts/month-end.md or create exports/xero.csv.
------------------------------------------------------------------------
[  ok  ] heartbeat              first run over this folder; the next run will compare against it
[ warn ] stale-state            unconfirmed: inbox-summary.md is 2 day(s) old (it says 2026-09-05, today is 2026-09-07), grace 1. The job that rebuilds it did not run, or this machine was off or asleep when it was due, and anything reading the file does not know. Re-run the job that writes inbox-summary.md; it was due by 2026-09-06. If it ran, check why it did not update the file.
[ FAIL ] expected-run           1 job(s) fired with no evidence: inbox-summary did not run, or this machine was off or asleep at Sun 06 Sep 06:00 (newest evidence 2026-09-05 06:00). A scheduler that says healthy is not sufficient evidence; the file the job touches is · 2 job(s) declared, 1 evidenced, 0 inside grace · times are UTC+10. Re-run the job inbox-summary; it was due Sun 06 Sep 06:00. If it ran, check why it did not update inbox-summary.md.
[ FAIL ] prompt-drift           2 dead path(s) in 2 prompt(s): prompts/daily.md -> invoices/ · prompts/month-end.md -> exports/xero.csv. The agent is told to read something that is not there. Fix the path in the prompt or create what it names.
[  ok  ] closed-sets            4 rows across 1 ledger(s), all in their closed sets
[  ok  ] absence                not enough history to know the cadence yet (4 dated files; 5 needed per series)
[  ok  ] no-vacuous-pass        6 checks each declared a floor and met it

3 incidents (3 new) · 2 checks failed · 1 warned · 7 ran (4 confirmed, 3 unconfirmed)

wrote WATCHMAN.md in /tmp/stranger; read it each morning, it lists only what needs you
`crontab -` refused the line: /var/spool/cron/: mkstemp: Permission denied. Put it in by hand with `crontab -e`:

  31 1 * * * mkdir -p '/tmp/stranger/.watchman' && cd '/sessions/.../mnt/brain-ops/projects/watchman' && '/usr/bin/python3' -m watchman --root '/tmp/stranger' --findings '{root}/.watchman/findings-{date}.md' > '/tmp/stranger/.watchman/last-board.txt' 2>&1
The nightly run is not in place until that line is in; everything else is.
Done. Watchman checks /tmp/stranger every night at 01:31 and writes WATCHMAN.md when something needs you.
exit=0
```

What I read, top to bottom, without knowing the internals: it looked at my folder and named my files; every section it proposed was mine; "6 checks fit this folder. The others need conventions this folder does not use, and stay off" told me the missing checks are not my problem, and I did not have to learn their names. Then three lines under `new:`, each a full sentence that ends with what to do, and then the detail under a rule.

The first `new:` line is the one that matters: the inbox summary did not run Sunday morning, or the machine was asleep, and the file is two days old. One line, not two. Round 2 gave me the same fact twice and I read it as two problems. The action is exactly what I would do: re-run the job, and if it did run, look at why the file did not change.

The other two are dead paths in my prompts I did not know about. Same shape: the file, the path, the fix.

Under the rule, `stale-state` is amber and starts with `unconfirmed:`. I did not need to understand why; the incident above it already told me. The word "guessed" appears in the doctor lines, and the install output told me what it means and what command confirms.

The nightly schedule: the sandbox this ran in refuses `crontab -` (permission denied on the spool), and the tool said so in one line and printed the crontab line to paste, then still said Done. On a machine where crontab works it appends the line itself; on a Mac it writes the launchd plist and loads it. Neither could be exercised here (see "What I could not do").

## WATCHMAN.md, after command 1

```
- new: inbox-summary did not run, or this machine was off or asleep at Sun 06 Sep 06:00 (newest evidence 2026-09-05 06:00); inbox-summary.md is 2 day(s) old (it says 2026-09-05, today is 2026-09-07). Re-run the job inbox-summary; it was due Sun 06 Sep 06:00. If it ran, check why it did not update inbox-summary.md.
- new: prompts/daily.md names invoices/, which does not exist. Fix the path in prompts/daily.md or create invoices/.
- new: prompts/month-end.md names exports/xero.csv, which does not exist. Fix the path in prompts/month-end.md or create exports/xero.csv.

2026-09-07 00:41 · full board: .watchman/last-board.txt
```

This is the file I would read on my phone. Three lines, three things to do, no check names, no counts, then the date and where the full board is.

## The next morning (second run, nothing changed)

Run by hand, standing in for the nightly job:

```
$ python3 -m watchman --root /tmp/stranger
ongoing (since 2026-09-07): inbox-summary did not run, or this machine was off or asleep at Sun 06 Sep 06:00 (newest evidence 2026-09-05 06:00); inbox-summary.md is 2 day(s) old (it says 2026-09-05, today is 2026-09-07). Re-run the job inbox-summary; it was due Sun 06 Sep 06:00. If it ran, check why it did not update inbox-summary.md.
ongoing (since 2026-09-07): prompts/daily.md names invoices/, which does not exist. Fix the path in prompts/daily.md or create invoices/.
ongoing (since 2026-09-07): prompts/month-end.md names exports/xero.csv, which does not exist. Fix the path in prompts/month-end.md or create exports/xero.csv.
------------------------------------------------------------------------
[  ok  ] heartbeat              last run 0.0h ago reported 4 passed, 1 warned, 2 failed
[ warn ] stale-state            unconfirmed: inbox-summary.md is 2 day(s) old (it says 2026-09-05, today is 2026-09-07), grace 1. The job that rebuilds it did not run, or this machine was off or asleep when it was due, and anything reading the file does not know. Re-run the job that writes inbox-summary.md; it was due by 2026-09-06. If it ran, check why it did not update the file.
[ FAIL ] expected-run           1 job(s) fired with no evidence: inbox-summary did not run, or this machine was off or asleep at Sun 06 Sep 06:00 (newest evidence 2026-09-05 06:00). A scheduler that says healthy is not sufficient evidence; the file the job touches is · 2 job(s) declared, 1 evidenced, 0 inside grace · times are UTC+10. Re-run the job inbox-summary; it was due Sun 06 Sep 06:00. If it ran, check why it did not update inbox-summary.md.
[ FAIL ] prompt-drift           2 dead path(s) in 2 prompt(s): prompts/daily.md -> invoices/ · prompts/month-end.md -> exports/xero.csv. The agent is told to read something that is not there. Fix the path in the prompt or create what it names.
[  ok  ] closed-sets            4 rows across 1 ledger(s), all in their closed sets
[  ok  ] absence                not enough history to know the cadence yet (4 dated files; 5 needed per series)
[  ok  ] no-vacuous-pass        6 checks each declared a floor and met it

3 incidents (3 ongoing) · 2 checks failed · 1 warned · 7 ran (4 confirmed, 3 unconfirmed)
exit=1
```

`ongoing (since 2026-09-07)` on all three. Nothing new, so nothing to read again; the heartbeat line is green and says what last night reported.

## After fixing two of the three

I re-ran the summary job (the file now says `Generated 2026-09-07 06:00`) and changed `invoices/` to `close/` in the daily prompt. Then:

```
$ python3 -m watchman --root /tmp/stranger
ongoing (since 2026-09-07): prompts/month-end.md names exports/xero.csv, which does not exist. Fix the path in prompts/month-end.md or create exports/xero.csv.
resolved:    inbox-summary did not run, or this machine was off or asleep at Sun 06 Sep 06:00; inbox-summary.md is 2 day(s) old.
resolved:    prompts/daily.md names invoices/, which does not exist.
------------------------------------------------------------------------
[  ok  ] heartbeat              last run 0.0h ago reported 4 passed, 1 warned, 2 failed
[  ok  ] stale-state            inbox-summary.md says 2026-09-07 · 0 day(s) old, within 1 · measured against today (no sources listed)
[  ok  ] expected-run           every declared job left evidence after its last expected fire · 2 job(s) declared, 2 evidenced, 0 inside grace · times are UTC+10
[ FAIL ] prompt-drift           1 dead path(s) in 2 prompt(s): prompts/month-end.md -> exports/xero.csv. The agent is told to read something that is not there. Fix the path in the prompt or create what it names.
[  ok  ] closed-sets            4 rows across 1 ledger(s), all in their closed sets
[  ok  ] absence                not enough history to know the cadence yet (4 dated files; 5 needed per series)
[  ok  ] no-vacuous-pass        6 checks each declared a floor and met it

1 incident (1 ongoing) · 2 resolved · 1 check failed · 7 ran (4 confirmed, 3 unconfirmed)
exit=1
```

Two `resolved:` lines, printed this once and never again, and the month-end path still `ongoing`. WATCHMAN.md now carries only the one open item:

```
- ongoing (since 2026-09-07): prompts/month-end.md names exports/xero.csv, which does not exist. Fix the path in prompts/month-end.md or create exports/xero.csv.

2026-09-07 00:41 · full board: .watchman/last-board.txt
```

## After fixing the last one

Created `exports/xero.csv`:

```
$ python3 -m watchman --root /tmp/stranger
resolved:    prompts/month-end.md names exports/xero.csv, which does not exist.
------------------------------------------------------------------------
[  ok  ] heartbeat              last run 0.0h ago reported 6 passed, 0 warned, 1 failed
[  ok  ] stale-state            inbox-summary.md says 2026-09-07 · 0 day(s) old, within 1 · measured against today (no sources listed)
[  ok  ] expected-run           every declared job left evidence after its last expected fire · 2 job(s) declared, 2 evidenced, 0 inside grace · times are UTC+10
[  ok  ] prompt-drift           5 path(s) across 2 prompt(s) all resolve · no live_dir set, mirrors unverified
[  ok  ] closed-sets            4 rows across 1 ledger(s), all in their closed sets
[  ok  ] absence                not enough history to know the cadence yet (4 dated files; 5 needed per series)
[  ok  ] no-vacuous-pass        6 checks each declared a floor and met it

0 incidents · 1 resolved · 0 checks failed · 7 ran (4 confirmed, 3 unconfirmed)
exit=0
```

And WATCHMAN.md:

```
Healthy: nothing needs you.

2026-09-07 00:41 · full board: .watchman/last-board.txt
```

The file is still there and says so. Exit code 0.

## Off the first screen: confirming the guesses

Curious what `unconfirmed` meant, I ran the command the install output named:

```
$ python3 -m watchman confirm --root /tmp/stranger
3 guessed section(s) in /tmp/stranger/watchman.toml. Each can warn but never fail until you confirm it.

  [stale_state] inbox-summary.md  (line 18)
    to confirm: delete the `guessed = true` line at line 18, after checking the section above it says what your folder does
  [[expected]] month-end-close  (line 33)
    to confirm: delete the `guessed = true` line at line 33, after checking the section above it says what your folder does
  [[ledgers]] close/2026-08-31.md  (line 50)
    to confirm: delete the `guessed = true` line at line 50, after checking the section above it says what your folder does

Or confirm all of them at once: python3 -m watchman confirm --all --root <folder>
```

It changed nothing and told me how to. `confirm --all` removed the three lines; after that `stale-state` on a stale file goes red instead of amber (checked separately, not part of the timed run).

## Friction

1. The install output is long for a phone: the discover lines, the doctor lines, the board and the schedule note all scroll past before "Done". The persona reads the top and the bottom; the middle is for the engineer. A `--quiet` on install that keeps only the incidents and the Done line would suit the first-screen reader.
2. The `resolved:` line is the fact without its parentheses. It still says "2 day(s) old" on the day the file is fresh, which is what was resolved, so it reads as history rather than as a current claim; acceptable.
3. On a sandbox with no working crontab the schedule step prints the line and still ends with Done. It now says, the line before, that the nightly run is not in place until that line is in; the Done sentence itself is unchanged, so a reader who only reads the last line still over-trusts it.
4. The month-end job guessed from one run is marked guessed and cannot fail; correct, and the operator would not know that `monthly last 23:30` was inferred from a single line unless they ran `confirm`.

## Measured

- Commands to the first meaningful red line: **1** (`install`). Round 2 was 3, round 1 was 16 minutes of hand-written toml.
- Commands to a scheduled nightly run and a morning file: **1**, the same one (the schedule step fell back to printing the crontab line in this sandbox).
- Time: under a minute of typing; the install output takes about two minutes to read in full, ten seconds to read the top three lines.
- Files written into the folder: `watchman.toml`, `WATCHMAN.md`, `.watchman/heartbeat.json`, `.watchman/last-board.txt`. Nothing else touched.

## What I could not do

- Actually append to a crontab or load a launchd plist: the sandbox has no writable cron spool and no launchd. The code paths are exercised in the tests only through `WATCHMAN_DRY_SCHEDULE=1`, which prints what would be done. The macOS path (write the plist, `launchctl unload` then `load`) has not been run on a Mac from this working copy.
- Wait a real night between runs: the `ongoing (since <date>)` state was produced by a second run minutes later, so the date is the same on both. The mechanism (the previous heartbeat's open incidents, matched on file and job keys) is the same either way.
