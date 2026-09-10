# Round 3: the implementer, three client folders, one cron line

Persona: the implementer from `user.md`. Set up three clients' agents, carries the blame when they drift, wants a repeatable instrument, a report with the tool's name on it per client, and one scheduled line, not three. Comfortable in a shell, not interested in reading code.

The folders: `/tmp/clients/doyle`, `/tmp/clients/northside`, `/tmp/clients/bayside`, each a copy of the round-1 folder. Northside's summary ran this morning; Bayside has no `prompts/` folder.

## What I typed, what came back

### 1. Configure all three at once

```
$ python3 -m watchman init --discover /tmp/clients/doyle /tmp/clients/northside /tmp/clients/bayside
usage: watchman [-h] [--version] [--root DIR] [--config CONFIG] [--json]
                [--findings PATTERN] [--quiet] [--no-write]
                {report,doctor,heartbeat,init,install-cron,intervene,log} ...
watchman: error: unrecognized arguments: /tmp/clients/northside /tmp/clients/bayside
exit=2
```

`init` takes one folder. I ran it three times. Friction: with fifty clients this is a shell loop I have to write myself.

### 2. Doctor over all three

```
$ python3 -m watchman doctor --root /tmp/clients/doyle --root /tmp/clients/northside --root /tmp/clients/bayside
== /tmp/clients/doyle
... 7 ready · 0 to fix ...
Run `python3 -m watchman --root /tmp/clients/doyle` for the board, then `python3 -m watchman install-cron --root /tmp/clients/doyle` so it runs nightly.
== /tmp/clients/northside
... 7 ready · 0 to fix ...
Run `python3 -m watchman --root /tmp/clients/northside` for the board, then ...
== /tmp/clients/bayside
... 6 ready · 0 to fix · off (...): ..., prompt-drift, ...
Run `python3 -m watchman --root /tmp/clients/bayside` for the board, then ...
```

Worked. Bayside correctly has `prompt-drift` off because discovery found no prompts. Friction, minor: the "Run ... for the board" advice is repeated per client and each tells me to schedule that client alone, which is the opposite of what I am doing.

### 3. Boards and reports in one go

```
$ python3 -m watchman --root /tmp/clients/doyle --root /tmp/clients/northside --root /tmp/clients/bayside --findings '/tmp/reports/{name}-{date}.md' --quiet
== /tmp/clients/doyle
[ warn ] heartbeat              no heartbeat at .watchman/heartbeat.json; either this is the first run or nothing has been running
[ FAIL ] stale-state            inbox-summary.md says 2026-09-05, and today is 2026-09-07: 2 day(s) old, grace 1. ...
[ FAIL ] expected-run           1 job(s) fired with no evidence: inbox-summary: due Sun 06 Sep 06:00, newest evidence 2026-09-05 06:00. ...
[ FAIL ] prompt-drift           2 dead path(s) in 2 prompt(s): prompts/daily.md -> invoices/ · prompts/month-end.md -> exports/xero.csv. Fix the path in the prompt or create what it names; ...
[ warn ] absence                1 of 1 gone quiet against their own cadence: notes/ (last dated 2026-08-25, 13d ago, usual gap 4d)

2 passed · 2 warnings · 3 failed · 7 checks ran
findings written to /tmp/reports/doyle-2026-09-07.md

== /tmp/clients/northside
[ warn ] heartbeat              ...
[ FAIL ] prompt-drift           2 dead path(s) in 2 prompt(s): ...
[ warn ] absence                ...

4 passed · 2 warnings · 1 failed · 7 checks ran
findings written to /tmp/reports/northside-2026-09-07.md

== /tmp/clients/bayside
...
2 passed · 2 warnings · 2 failed · 6 checks ran
findings written to /tmp/reports/bayside-2026-09-07.md
exit=1
```

Exactly what I wanted: one command, one heading per client, one report per client named after the folder and the day, exit 1 because something failed somewhere. Northside, whose summary ran this morning, is clean on the two run checks and still shows the dead prompt paths, which is the finding I would bill for.

### 4. The report

```
# Findings

*watchman 0.1.1 over `/tmp/clients/northside`, 2026-09-07. 4 passed, 2 warned, 1 failed, 7 ran.*

## FAIL: prompt-drift
...
**Why this check exists.** A scheduled prompt that names a path which no longer exists fails silently at 4am; ...
```

Friction: the title is "Findings" with the client's name only in the path in italics. I put this in front of a client; the first line should carry their name. The "why this check exists" sentence under each finding is the bit that makes it a report rather than a log; keep that.

The `heartbeat` amber, "either this is the first run or nothing has been running", is in the report. On a first run over a client's folder it is noise in the deliverable, but it is honest and disappears from the second run.

### 5. One cron line

```
$ python3 -m watchman install-cron --root /tmp/clients/doyle --root /tmp/clients/northside --root /tmp/clients/bayside --findings '/tmp/reports/{name}-{date}.md'
  31 1 * * * mkdir -p '/tmp/clients/doyle/.watchman' && cd '...' && '/usr/bin/python3' -m watchman --root '/tmp/clients/doyle' --findings '/tmp/clients/doyle/.watchman/findings-{date}.md' > /tmp/clients/doyle/.watchman/last-board.txt 2>&1
```

Friction, the real one this round: it silently kept the first `--root` and dropped the other two, and ignored my `--findings` pattern in favour of its own. The line it printed would have watched one client and written that client's reports into the client's own folder, which is not where I want them. Nothing said the other roots were ignored.

## Friction, ranked

1. `install-cron` takes one root, silently. Must take all of them and honour `--findings`, so the line it prints is the line I install.
2. `init --discover` takes one folder; should take a list.
3. The findings report's title should name the client.
4. `doctor` over several roots repeats single-client advice.
5. README needs the story written down: one toml per client folder, one cron line, `{name}` in the report path, `{root}` if two clients share a folder name.
