# User-simulation loop, 6 to 7 September 2026

Four rounds over a folder that is not shaped like brain-ops (`/tmp/stranger`: a daily inbox summary with a `Generated <date>` line, a month-end close, a client CSV, a task list, a run log, two prompts, a notes folder that stopped twelve days ago). Rounds 1, 2 and 4 are the operator from `user.md`; round 3 is the implementer. Full transcripts in `round1.md`, `round2.md`, `round3.md`, `round4.md`.

## Round 1: the operator, version 0.1.1 as found

Sixteen minutes to one meaningful red line, and only by writing toml by hand, which the persona will not do. Friction, in order of damage:

1. `watchman init DIR` on a folder that already had files wrote thirteen demo files into it (`now.md`, `admin/`, `brain/`, `subjects/`, a `log/`, a `tasks/` folder beside the real `tasks.md`). The board then reported three red lines, none about a file the persona owned.
2. No way to get a config from the folder's own shape; every path in the starter was someone else's.
3. `stale-state` crashed with `ValueError: invalid literal for int()` on a `Generated 2026-09-05` marker. The check the README leads with could not read a date.
4. Board times were UTC with no hint that they were; `newest evidence 2026-09-04 20:01` for a file the persona saw modified at 06:01.
5. `unreadable schedule 'monthly'` named no readable forms, and there was no monthly form for the month-end job.
6. A config mistake in one `[[expected]]` job was counted and worded as a job that went silent.
7. A missing `schedule` key surfaced as a raw Python `'schedule'`.
8. Nothing said which of the fourteen board lines applied to this folder before they were on the board.
9. Nothing on the first screen said how to run it nightly.

## Fixed after round 1

- `watchman init --discover DIR`: reads the folder and proposes `watchman.toml`, asking nothing. Finds head lines like `Generated <date>` (date-mode `[stale_state]` plus an `[[expected]]` job with the time), files whose lines start with a timestamp (one `[[expected]]` per job name, schedule guessed from the stamps: daily, weekdays, weekly, monthly on a day or on the last day), markdown naming paths in backticks (`[prompts]`), folders of date-named files (`[absence] dirs`), tables with a Status-like column (`[[ledgers]]` with `state_column`), and the brain-ops shape (`Entry N` headings and `folded through`) when present. Every section carries a comment saying why; guesses carry `# TODO confirm`. An existing toml is never overwritten; the proposal goes to `watchman.proposed.toml`. A CSV with a status column is named in a comment as not readable.
- `init` on a folder with files now discovers by default; `--demo` is required for the fixture and is refused on a non-empty folder with both alternatives printed.
- `stale-state` date mode: when the marker's group is a date, it is compared with the newest change among `sources` globs (mtime or a timestamp written inside), or with today when `sources` is empty. Entry mode is unchanged. A marker that captures neither says so; a numeric marker with no log entries says so and shows the date form.
- `watchman doctor`: one line per section, `ready` or `fix` with what is missing (file absent, glob matches nothing, regex matches nothing, schedule unreadable, key missing), a count, the list of checks that are off, and the next command. Reads only, exits 0.
- `watchman install-cron`: prints the crontab line (with `mkdir -p` for the output folder and a `cd` so `python3 -m watchman` works uninstalled); on macOS prints the launchd plist, or with `--write` saves it under `~/Library/LaunchAgents` and prints the `launchctl load` line. Never loads or schedules anything itself.
- Times default to the machine's own zone when `utc_offset_hours` is absent; the board and the doctor say which zone they are using.
- `expected-run`: `monthly <day|last> HH:MM` forms; cron day-of-month is honoured; unreadable schedules list the accepted forms; a missing `schedule` or `evidence` line is named as such; config mistakes are reported as "could not be checked" in a separate clause from jobs that really went silent; "no evidence" says whether the file is absent or the pattern matched nothing; timestamps with trailing text parse.
- `closed-sets` with `state_column` no longer demands a `## Heading` per state. `absence` accepts `dirs`.
- Global options (`--root`, `--config`, `--findings`, `--json`, `--quiet`, `--no-write`) may follow the subcommand, so `watchman doctor --root DIR` works as the next-step lines print it.
- A TOML that does not parse is reported in one sentence instead of a traceback.
- The README's first screen became the five commands.

## Round 2: the operator, same folder, new first screen

**Three commands to the first meaningful red line, about three minutes, no toml written by hand.** `init --discover` proposed six sections, all naming the persona's own files; `doctor` said `7 ready · 0 to fix`; the board's first red line was the missed Sunday inbox summary, the second the same fact from the file's side, the third two dead paths in the prompts that the persona did not know about. `install-cron` printed the line. `init --discover` a second time went to `watchman.proposed.toml`; `init --demo` on the real folder was refused.

Friction, all minor: `prompt-drift` named the dead paths without saying what to do; `crontab -e` may open vi with no hint how to leave it; the `[[ledgers]]` guess points at a dated file (`close/2026-08-31.md`) with no note that next month's file will need the path changed; `no-vacuous-pass` is jargon on a green line.

## Fixed after round 2

`prompt-drift` failures end with "fix the path in the prompt or create what it names"; `install-cron` gives the vi keystrokes; the ledger proposal marks a dated file with `# TODO confirm`. The jargon on the green line was left alone.

## Round 3: the implementer, three client folders

`--root` repeated gave one board per client under its own heading and `--findings '/reports/{name}-{date}.md'` wrote one report per client with the tool's name on it; exit code the worst of the three. Friction: `init --discover` took one folder; `install-cron` silently kept only the first `--root` and ignored `--findings`, so the line it printed was not the line to install; the report's title did not carry the client's name; `doctor` over several roots repeated single-client advice; the README had no multi-client story.

## Fixed after round 3

`init --discover` takes a list of folders. `install-cron` takes every `--root` and honours `--findings`; with several roots the reports and the board text land together in the pattern's folder, with one root they land in its `.watchman/` (`{root}` in the pattern is expanded per folder). The findings title is `Findings: <folder name>`. `doctor` drops the per-client advice line when there are several roots. README gained "Several clients from one place" with the three commands.

## What remains

- Discovery reads markdown tables only; a CSV with a status column is noted in a comment and not checked.
- Discovery's schedule guess for a job seen once is marked as guessed rather than derived. A `monthly last` job seen once on a month's last day is guessed correctly; one seen on the 28th would be proposed as `daily`.
- `[stale_state]` date mode compares against today when `sources` is empty; the proposal leaves `sources = []` with a TODO, because the sources of an inbox summary are usually outside the folder.
- `install` loads launchd on a Mac and appends the crontab line on Linux; neither path has been run for real from this working copy (the sandbox has no writable cron spool and no launchd), only through `WATCHMAN_DRY_SCHEDULE=1`.
- The `[[ledgers]]` proposal for a dated close file has to be re-pointed by hand when the next month's file appears.
- `no-vacuous-pass` still reads as jargon to the operator.
- The brain-ops board is unchanged at 14 checks ran; `expected-run` for the evening entry now says the pattern matched nothing in the log instead of "no evidence at all", which is the same failure with the reason attached.

## Outside review, after round 3

An outside reviewer played the operator and a sceptical engineer over the round-2 onboarding. Their findings, all implemented as 0.2.0 on 7 September:

- Two red lines for one missed run. Now one incident: check lines that share a file, or a job whose name is the file's stem, fold into one line above the board, with a state against the previous night (`new`, `ongoing (since <date>)`, `resolved` printed once). The summary line counts incidents.
- Nothing to read in the morning but a terminal. Every run writes `WATCHMAN.md` at the root of the folder: unresolved incidents with one action each, or `Healthy: nothing needs you.`, then the date and the path to the full board. `attention_file = ""` turns it off.
- Red lines that stopped at the fact. Every red line now ends in the operator's next action: re-run the job that writes the file, open the folder and decide, edit the row, fix the path.
- Guesses that could go red. `init --discover` writes `guessed = true` where it inferred; a guessed section warns but never fails and its line starts with `unconfirmed:`. `watchman confirm` lists them; `confirm --all` deletes the lines. The summary counts confirmed and unconfirmed checks.
- The first run was amber. It is now a green line saying the next run will compare against it.
- "Did not run" asserted the scheduler was broken. From the folder, a job that did not fire and a laptop that was asleep look the same, and the wording now says so.
- Four dated notes were called a cadence. `absence` wants five before it warns; below that it is a green line naming how much history there is.
- Five commands. `watchman install FOLDER` does discover, doctor, the board, `WATCHMAN.md`, and the schedule (launchd loaded on a Mac; crontab appended on Linux when `crontab` exists, printed otherwise), ending in one fixed sentence. The README's first screen is that command and "read FOLDER/WATCHMAN.md each morning".
- Seven internal names on the doctor's summary line. Now "n checks fit this folder. The others need conventions this folder does not use, and stay off"; `--verbose` names them.

## Round 4: the operator, same folder, one command

**One command to the first meaningful red line, and to a morning file and a scheduled run.** `install` proposed six sections, said six checks fit, and printed three incidents above the board: the missed Sunday summary and the two-day-old file as one line ending in "Re-run the job inbox-summary", and one line per dead prompt path. `WATCHMAN.md` carried the same three lines and nothing else. A second run marked all three `ongoing`; after two fixes the board printed two `resolved:` lines once and the file carried the one open item; after the third it said `Healthy: nothing needs you.` and still existed. Friction: the install output is long for a phone; the Done sentence stands even when the schedule step had to fall back to printing the crontab line (the line before says so); the operator only learns that `monthly last 23:30` was inferred from one line by running `confirm`.

## Measured

Time-to-first-red-line for the operator in round 4: **1 command** (`install`), under a minute, with the nightly run scheduled (or its line printed) and `WATCHMAN.md` written by the same command. Round 2: **3 commands** (`init --discover`, `doctor`, the board), about three minutes, of which `doctor` is optional; the board alone at command 2 shows the same red line. Round 1 was 16 minutes and required hand-written toml.

Tests: 75, all passing (`python3 -m unittest discover -s tests`).
