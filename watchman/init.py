"""`watchman init DIR`: a starter watchman.toml and a fixture folder that produces a mixed board.

The fixture is deliberately not clean. A demo that is all green teaches nothing
about what the board looks like when it earns its keep.
"""
import datetime
import json
import os

TOML = """# watchman.toml. Every section switches on one check; delete a section to turn it off.
[watchman]
utc_offset_hours = {utc}
heartbeat = ".watchman/heartbeat.json"
heartbeat_max_age_hours = 30

[log]                      # append-only-log, and the source every other check reads
files = ["log/*.md"]
heading = '^##\\s+(?P<date>\\d{{4}}-\\d{{2}}-\\d{{2}}).*?Entry\\s+(?P<n>\\d+)'
write_to = "log/{month}.md"
write_format = "## {{date}} Entry {{n}} {{title}}"
floor = 1
quiet_days = 3

[stale_state]              # the read-first file, measured against the log by marker
file = "now.md"
marker = 'folded through Entry (\\d+)'
grace_days = 1

[stated]                   # numbers in prose that the folder can measure
files = ["docs/*.md", "now.md"]
tolerance = 0.30
[[stated.measure]]
name = "now.md"
file = "now.md"
ceiling = 4000

[degraded]                 # step-state JSON written by scheduled jobs
state_dir = "state"
fail_after = 8

[[expected]]               # when a job should fire and one file it touches; needs nothing else
name = "nightly"
schedule = "daily 03:00"
evidence = "state/nightly-*.json"
grace_minutes = 90

[prompts]                  # mirrors of the scheduled prompts; set live_dir to compare bytes
mirrors = ["tasks/*.md"]
floor = 1
# live_dir = "~/Claude/Scheduled"

[[ledgers]]                # closed sets of states; the heading is the state
file = "admin/commitments.md"
key = "ID"
id = "C\\d{{3}}"
states = ["Open", "Done", "Dropped", "Void"]

[interventions]
file = "interventions.md"
stale_days = 14
window_days = 14
rising_floor = 3

[absence]                  # files whose dated lines set their own cadence
files = ["subjects/*.md"]
min_dates = 3
factor = 2.0

[citations]
files = ["brain/**/*.md"]
pattern = '\\bE(\\d{{3,}})\\b'

[cannots]
file = "cannots.md"

[read_budget]
opened_whole = ["now.md", "docs/*.md", "tasks/*.md"]
behind_a_tool = ["log/*.md"]
limit_tokens = 16000
runaway_tokens = 250000
session_floor = ["now.md"]
session_floor_limit = 14000
"""


def _d(t, days):
    return (t - datetime.timedelta(days=days)).isoformat()


def write_fixture(root, today, utc_offset=0):
    t = today
    files = {}
    files["watchman.toml"] = TOML.format(utc=utc_offset, month=t.strftime("%Y-%m"))
    files[f"log/{t.strftime('%Y-%m')}.md"] = "".join(
        f"## {_d(t, 4 - i)} Entry {i + 1} {title}\n\n{body}\n\n" for i, (title, body) in enumerate([
            ("Opening the folder", "First entry. The system starts here."),
            ("Coffee grinder settled", "Chose the burr grinder after three weeks of reading."),
            ("Rent paid", "Paid on the 1st, receipt filed."),
            ("Gym moved to mornings", "Evening sessions kept losing to work. Mornings hold."),
            ("Menu costing started", "Opened the spreadsheet, priced four dishes."),
        ]))
    files["now.md"] = ("# Now (folded through Entry 3)\n\nThe current state, rebuilt nightly. "
                       "Read this before answering anything.\n\n- Rent is paid for the month.\n"
                       "- The grinder decision is made.\n- Gym: evenings, five nights a week.\n")
    files["docs/guide.md"] = (f"# Guide\n\n`now.md` is read whole by every session and costs "
                              f"~{len(files['now.md'].encode()) // 4} tokens.\n")
    for back in (1, 0):
        files[f"state/nightly-{_d(t, back)}.json"] = json.dumps({
            "job": "nightly", "day": _d(t, back), "ended": True, "artefact": "now.md",
            "done": {"1-rebuild": {"result": "rebuilt now.md"},
                     "2-sweep": {"result": "skipped · DEGRADED: session floor over cap",
                                 "degraded": True}}}, indent=1)
    files["tasks/nightly.md"] = ("# Nightly\n\nRead `now.md`, then append to `log/` via "
                                 "`watchman log`. Close any row in `admin/commitments.md` "
                                 "that resolved today.\n")
    files["admin/commitments.md"] = (
        "# Commitments\n\n## Open\n\n| ID | What | Due |\n|---|---|---|\n"
        f"| C001 | Renew car rego | {_d(t, -20)} |\n\n## Done\n\n| ID | What | Due |\n|---|---|---|\n"
        f"| C002 | Pay rent | {_d(t, 5)} |\n\n## Noted\n\n| ID | What | Due |\n|---|---|---|\n"
        f"| C003 | Dentist, sometime | |\n\n## Dropped\n\n## Void\n")
    files["interventions.md"] = (
        "# Interventions\n\n| Date | What they had to do | What it cost | What would remove it | Disposition |\n"
        "|---|---|---|---|---|\n"
        f"| {_d(t, 20)} | Restated the rent amount | a turn | read now.md first | Rule |\n"
        f"| {_d(t, 8)} | Split a paste by hand | a session | a size guard | Tool change |\n"
        f"| {_d(t, 5)} | Answered which CV is current | a turn | route it | Accepted: one-off |\n"
        f"| {_d(t, 3)} | Re-ran the nightly job | ten minutes | none | |\n"
        f"| {_d(t, 1)} | Fixed a heading by hand | a turn | append via the tool | |\n")
    files["subjects/coffee.md"] = "# Coffee\n\n" + "".join(
        f"- {_d(t, d)}: grinder notes\n" for d in (16, 9, 2))
    files["subjects/pokemon.md"] = "# Pokemon\n\n" + "".join(
        f"- {_d(t, d)}: set review\n" for d in (51, 44, 37, 30))
    files["brain/notes.md"] = ("# Grinder choice\n\nChosen after reading (E002). The rego "
                               "deadline was moved (E009).\n")
    files["cannots.md"] = (
        "# Cannots\n\nThings a tool was found unable to do. Re-test before obeying.\n\n"
        "| Date | Cannot | Re-test by |\n|---|---|---|\n"
        f"| {_d(t, 40)} | edit live prompts from a cloud session | {_d(t, 10)} |\n"
        f"| {_d(t, 5)} | rename files on the mount | {_d(t, -25)} |\n")
    for rel, text in files.items():
        p = os.path.join(root, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(text)
    return sorted(files)
