# Round 2: the operator again, same folder, new first screen

Same persona, same `/tmp/stranger` with the round-1 leftovers removed (`watchman.toml`, `.watchman/`). Internals forgotten as far as possible: I typed only what the README's "From nothing to a red line" block shows, substituting my folder for `FOLDER`, and read only what came back. It is 7 September, a few minutes after midnight local.

Clock started 00:06.

## Command 1

```
$ python3 -m watchman init --discover /tmp/stranger
looked at /tmp/stranger and guessed:
  [stale_state]: inbox-summary.md carries 'Generated 2026-09-05 06:00' in its head
  [[expected]] inbox-summary: daily 06:00, evidence inbox-summary.md
  [[expected]] month-end-close: monthly last 23:30, evidence runs.log (schedule guessed)
  [prompts]: 2 file(s) naming paths in backticks: prompts/daily.md, prompts/month-end.md
  [absence]: notes/ (4 dated files)
  [[ledgers]]: close/2026-08-31.md, column 'Status' with states ['Outstanding', 'Paid', 'Partial']
wrote /tmp/stranger/watchman.toml · lines marked `# TODO confirm` are guesses
next: python3 -m watchman doctor --root /tmp/stranger    (says what each section can and cannot check)
```

Every line names one of my files, and I recognised what each guess meant from the file name alone. "schedule guessed" on the month-end job was right to flag: it saw one run on 31 August at 23:30 and inferred last-day-of-month, which happens to be correct. Nothing was written except `watchman.toml`. I did not open it.

Minor: `[[ledgers]]` with the double brackets, and `[stale_state]` with one pair, is a distinction I do not understand and do not need to. It is the toml's problem, not mine.

## Command 2

```
$ python3 -m watchman doctor --root /tmp/stranger
ready  [watchman]       heartbeat          times are UTC+10 (from the toml); heartbeat goes to .watchman/heartbeat.json
ready  [stale_state]    stale-state        inbox-summary.md says 2026-09-05; measured against today, grace 1 day(s) (date mode)
ready  [[expected]]     expected-run       inbox-summary: daily 06:00, last due Sun 06 Sep 06:00, 1 matching line(s) in inbox-summary.md
ready  [[expected]]     expected-run       month-end-close: monthly last 23:30, last due Mon 31 Aug 23:30, 1 matching line(s) in runs.log
ready  [prompts]        prompt-drift       2 prompt(s), 6 path(s) in backticks
ready  [[ledgers]]      closed-sets        close/2026-08-31.md: 4 row(s), states ['Outstanding', 'Paid', 'Partial']
ready  [absence]        absence            0 file(s) and 1 folder(s) with their own cadence

7 ready · 0 to fix · off (no section in watchman.toml): stated-vs-measured, degraded-steps, intervention-tally, append-only-log, citation-resolves, cannot-list, read-budget
Run `python3 -m watchman --root /tmp/stranger` for the board, then `python3 -m watchman install-cron --root /tmp/stranger` so it runs nightly.
```

"7 ready, 0 to fix" answered the question I had at this point, which was "is it going to complain about things I do not have". The "off" list is seven names I do not recognise, but the word "off" told me I can ignore them. `times are UTC+10` is my zone; round 1's confusion is gone.

## Command 3: the red line

```
$ python3 -m watchman --root /tmp/stranger
[ warn ] heartbeat              no heartbeat at .watchman/heartbeat.json; either this is the first run or nothing has been running
[ FAIL ] stale-state            inbox-summary.md says 2026-09-05, and today is 2026-09-07: 2 day(s) old, grace 1. The job that rebuilds it has not run, and anything reading it does not know
[ FAIL ] expected-run           1 job(s) fired with no evidence: inbox-summary: due Sun 06 Sep 06:00, newest evidence 2026-09-05 06:00. A schedule that says healthy is not evidence; the file the job touches is · 2 job(s) declared, 1 evidenced, 0 inside grace · times are UTC+10
[ FAIL ] prompt-drift           2 dead path(s) in 2 prompt(s): prompts/daily.md -> invoices/ · prompts/month-end.md -> exports/xero.csv
[  ok  ] closed-sets            4 rows across 1 ledger(s), all in their closed sets
[ warn ] absence                1 of 1 gone quiet against their own cadence: notes/ (last dated 2026-08-25, 13d ago, usual gap 4d)
[  ok  ] no-vacuous-pass        6 checks each declared a floor and met it

2 passed · 2 warnings · 3 failed · 7 checks ran
```

Clock: 00:09. Three commands, three minutes, and the first red line is the real problem: the inbox summary did not run on Sunday morning. The second red line is the same fact from the other side (the file is two days old). The third is something I did not know: my month-end prompt tells the agent to read `exports/xero.csv`, and there is no such file, and the daily prompt mentions an `invoices/` folder that does not exist. The amber line about `notes/` is true; I stopped writing them.

Friction, all minor:

1. `prompt-drift` names the dead paths but not what to do about them. The other red lines end with a sentence about what it means; this one just stops. I would have liked "fix the path in the prompt, or create it".
2. Two red lines for one missed run. Correct, and they say different things, but on a phone at 5am I would read them as two problems.
3. `no-vacuous-pass ... declared a floor and met it` is green and I do not know what it means. I let it go because it is green.
4. `heartbeat` amber on the first run, saying it might be the first run. It was. Fine.

## Command 4

```
$ python3 -m watchman install-cron --root /tmp/stranger
# watchman 0.1.1 nightly over /tmp/stranger at 01:31

The crontab line (any Linux or Mac with cron):

  31 1 * * * mkdir -p '/tmp/stranger/.watchman' && cd '/sessions/.../projects/watchman' && '/usr/bin/python3' -m watchman --root '/tmp/stranger' --findings '/tmp/stranger/.watchman/findings-{date}.md' > /tmp/stranger/.watchman/last-board.txt 2>&1

To install it: run `crontab -e`, paste the line, save. `crontab -l` shows what is installed.
Each run leaves the board in .watchman/last-board.txt and a findings report beside it.
```

I do not know what `crontab -e` will open. On this Linux box it is vi, and a non-engineer will not know how to leave vi. The README says a Mac gets `--write` and a launchd file instead, which is the right move for the primary user, but the Linux path needs a sentence about the editor.

## Two things I tried that were not on the first screen

Ran `init --discover` a second time to see if it would clobber the config: it wrote `watchman.proposed.toml` beside it and said so. Good. Ran `init --demo` on my folder out of curiosity: refused, named both alternatives, exit 2. Good; that is the round-1 disaster, closed.

Clock stopped at 00:12. Six minutes total, red line at minute three, on command three.

## Measured

- Commands to first meaningful red line: **3** (`init --discover`, `doctor`, the board). `doctor` is optional on the path; the board alone at command 2 would have shown the same red line.
- Time: about three minutes, none of it writing toml.
- Nothing written into the folder except `watchman.toml` and, after the board, `.watchman/heartbeat.json`.
