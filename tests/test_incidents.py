"""Incidents with state across runs, WATCHMAN.md, guessed sections and `confirm`,
`install`, and the wording every red line ends in. Run with:
python3 -m unittest discover -s tests"""
import datetime
import io
import json
import os
import re
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

from test_commands import stranger
from watchman import cli, confirm, discover, install, report, toml_min
from watchman.checks import expected_run
from watchman.checks._util import Result
from watchman.config import Config, local_utc_offset

HERE = os.path.dirname(os.path.abspath(__file__))
TOP = os.path.dirname(HERE)


def run_cli(*args):
    out = io.StringIO()
    with redirect_stdout(out):
        code = cli.main(list(args))
    return code, out.getvalue()


class Folder(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="watchman-inc-")
        self.today = datetime.date.today()
        stranger(self.root, self.today)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def write(self, rel, text):
        p = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(text)

    def read(self, rel):
        with open(os.path.join(self.root, rel), encoding="utf-8") as fh:
            return fh.read()

    def toml_for_missed_run(self):
        """A confirmed config where the summary is 3 days old and the daily job
        that writes it is overdue: the same fact from two checks."""
        old = (self.today - datetime.timedelta(days=3)).isoformat()
        self.write("inbox-summary.md", f"# Inbox summary\n\nGenerated {old} 06:00 from 14 emails\n")
        self.write("watchman.toml",
                   f'[watchman]\nutc_offset_hours = {local_utc_offset():g}\n\n'
                   '[stale_state]\nfile = "inbox-summary.md"\n'
                   "marker = 'Generated\\s*(\\d{4}-\\d{2}-\\d{2})'\ngrace_days = 1\n\n"
                   '[[expected]]\nname = "inbox-summary"\nschedule = "daily 00:00"\n'
                   'evidence = "inbox-summary.md"\n'
                   "pattern = 'Generated\\s*(\\d{4}-\\d{2}-\\d{2}(?:[T ]\\d{2}:\\d{2})?)'\n"
                   "grace_minutes = 0\n")


class TestIncidents(Folder):
    def test_stale_file_and_missed_run_are_one_incident(self):
        self.toml_for_missed_run()
        results = report.run_all(Config.load(self.root))
        live = [i for i in results.incidents if i.state != "resolved"]
        self.assertEqual(len(live), 1)
        inc = live[0]
        self.assertEqual(inc.state, "new")
        self.assertEqual(inc.status, "FAIL")
        # the job name leads, the file follows, and the action is the re-run
        self.assertTrue(inc.text.startswith("inbox-summary left no expected evidence for its"))
        self.assertIn("inbox-summary.md is 3 days old", inc.text)
        self.assertTrue(inc.action.startswith("Check the inbox-summary job."))
        text = report.render(results)
        self.assertTrue(text.startswith("new:"))
        self.assertIn(report.RULE, text)
        self.assertIn("1 incident (1 new) · 2 checks failed", text)

    def test_state_goes_new_ongoing_resolved(self):
        self.toml_for_missed_run()
        first = report.run_all(Config.load(self.root))
        self.assertEqual([i.state for i in first.incidents], ["new"])
        second = report.run_all(Config.load(self.root))
        self.assertEqual([i.state for i in second.incidents], ["ongoing"])
        self.assertEqual(second.incidents[0].since, self.today.isoformat())
        self.assertIn(f"ongoing (since {self.today.isoformat()}):", report.render(second))
        self.assertIn("1 incident (1 ongoing)", report.render(second))
        # the job runs: both lines go green, the incident is printed once as resolved
        self.write("inbox-summary.md", f"# Inbox summary\n\nGenerated {self.today.isoformat()} 06:00\n")
        third = report.run_all(Config.load(self.root))
        self.assertEqual([i.state for i in third.incidents], ["resolved"])
        self.assertIn("resolved:", report.render(third))
        self.assertIn("0 incidents · 1 resolved", report.render(third))
        fourth = report.run_all(Config.load(self.root))
        self.assertEqual(fourth.incidents, [])
        self.assertNotIn("resolved", report.render(fourth))

    def test_unrelated_lines_stay_separate(self):
        self.write("watchman.toml", '[watchman]\nutc_offset_hours = 0\n\n[prompts]\nmirrors = ["prompts/*.md"]\n')
        self.write("prompts/month-end.md", "Read `exports/xero.csv` and `close/`.\n")
        results = report.run_all(Config.load(self.root), write=False)
        texts = sorted(i.text for i in results.incidents)
        self.assertEqual(len(texts), 2)
        self.assertIn("prompts/daily.md names invoices/, which does not exist", texts)
        self.assertIn("prompts/month-end.md names exports/xero.csv, which does not exist", texts)

    def test_json_carries_incidents(self):
        self.toml_for_missed_run()
        data = json.loads(report.render_json(report.run_all(Config.load(self.root), write=False)))
        self.assertEqual(data["incidents"][0]["state"], "new")
        self.assertIn("inbox-summary", data["incidents"][0]["text"])


class TestAttentionFile(Folder):
    def test_written_every_run_and_lists_only_incidents(self):
        self.toml_for_missed_run()
        report.run_all(Config.load(self.root))
        text = self.read("WATCHMAN.md")
        lines = text.splitlines()
        self.assertTrue(lines[0].startswith("Last checked: "))
        self.assertTrue(lines[2].startswith("- new: inbox-summary left no expected evidence"))
        self.assertIn("Check the inbox-summary job", lines[2])
        self.assertIn("full board: .watchman/last-board.txt", lines[-1])
        self.assertTrue(os.path.exists(os.path.join(self.root, ".watchman", "last-board.txt")))
        self.assertNotIn("[ FAIL ]", text)

    def test_healthy_file_still_exists_and_says_so(self):
        self.toml_for_missed_run()
        self.write("inbox-summary.md", f"# Inbox summary\n\nGenerated {self.today.isoformat()} 06:00\n")
        report.run_all(Config.load(self.root))
        text = self.read("WATCHMAN.md")
        self.assertEqual(text.splitlines()[2], "Healthy: nothing needs you.")
        self.assertIn(self.today.isoformat(), text.splitlines()[0])

    def test_resolved_incident_is_not_in_the_file(self):
        self.toml_for_missed_run()
        report.run_all(Config.load(self.root))
        self.write("inbox-summary.md", f"# Inbox summary\n\nGenerated {self.today.isoformat()} 06:00\n")
        results = report.run_all(Config.load(self.root))
        self.assertEqual(results.incidents[0].state, "resolved")
        self.assertIn("\nHealthy: nothing needs you.\n", self.read("WATCHMAN.md"))

    def test_can_be_turned_off_or_renamed(self):
        self.toml_for_missed_run()
        self.write("watchman.toml", self.read("watchman.toml").replace(
            "[watchman]\n", '[watchman]\nattention_file = ""\n'))
        report.run_all(Config.load(self.root))
        self.assertFalse(os.path.exists(os.path.join(self.root, "WATCHMAN.md")))
        self.write("watchman.toml", self.read("watchman.toml").replace('attention_file = ""', 'attention_file = "ATTENTION.md"'))
        report.run_all(Config.load(self.root))
        self.assertTrue(os.path.exists(os.path.join(self.root, "ATTENTION.md")))

    def test_first_line_is_last_checked(self):
        # item 2: the reader can tell whether watchman itself has stopped
        self.toml_for_missed_run()
        cfg = Config.load(self.root)
        report.run_all(cfg)
        lines = self.read("WATCHMAN.md").splitlines()
        stamp = lines[0]
        self.assertRegex(stamp, r"^Last checked: \d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC[+-]?\d*$")
        self.assertEqual(stamp.split()[-1], report.zone(cfg))
        self.assertEqual(lines[1], "")
        self.assertTrue(lines[2].startswith("- new: "))
        self.assertEqual(lines[-1], "full board: .watchman/last-board.txt")

    def test_no_write_does_not_touch_it(self):
        self.toml_for_missed_run()
        report.run_all(Config.load(self.root), write=False)
        self.assertFalse(os.path.exists(os.path.join(self.root, "WATCHMAN.md")))


class TestActions(Folder):
    def test_expected_run_ends_in_the_re_run(self):
        self.toml_for_missed_run()
        b = {r.check: r for r in report.run_all(Config.load(self.root), write=False)}
        m = b["expected-run"].message
        self.assertIn("A scheduler that says healthy is not sufficient evidence; the file the job touches is", m)
        self.assertTrue(m.endswith("if it already ran, check why inbox-summary.md was not updated."))
        self.assertTrue(b["stale-state"].message.startswith("inbox-summary.md is 3 days old"))

    def test_missed_run_claims_no_cause(self):
        # item 4: three things look the same from the folder, so the line names all three
        self.toml_for_missed_run()
        results = report.run_all(Config.load(self.root), write=False)
        b = {r.check: r for r in results}
        m = b["expected-run"].message
        self.assertRegex(m, r"inbox-summary left no expected evidence for its \w{3} \d{2} \w{3} \d{2}:\d{2} run \(newest evidence [^)]+\): it may not have run, this machine may have been off or asleep, or it may have run without updating inbox-summary.md")
        self.assertIn("Check the inbox-summary job. If it is safe to rerun, run it now; if it already ran, check why inbox-summary.md was not updated.", m)
        s = b["stale-state"].message
        self.assertNotIn("did not run", s)
        self.assertIn("Check the job that writes inbox-summary.md", s)
        self.assertTrue(s.endswith("if it already ran, check why inbox-summary.md was not updated."))
        inc = results.incidents[0]
        self.assertNotIn("did not run", inc.text)
        self.assertEqual(inc.action, "Check the inbox-summary job. If it is safe to rerun, run it now; if it already ran, check why inbox-summary.md was not updated.")

    def test_counts_agree_with_their_nouns(self):
        # item 5: no "(s)" anywhere a count is rendered
        self.toml_for_missed_run()
        results = report.run_all(Config.load(self.root), write=False)
        text = report.render(results)
        self.assertNotIn("(s)", text)
        self.assertIn("inbox-summary.md is 3 days old", text)
        self.assertIn("1 job fired with no evidence", text)
        self.assertIn("1 job declared", text)
        self.assertIn("2 checks failed", text)
        self.assertIn("1 incident (1 new)", text)
        self.write("inbox-summary.md", f"# Inbox summary\n\nGenerated {(self.today - datetime.timedelta(days=1)).isoformat()} 06:00\n")
        self.write("watchman.toml", self.read("watchman.toml").replace("grace_days = 1", "grace_days = 0"))
        b = {r.check: r for r in report.run_all(Config.load(self.root), write=False)}
        self.assertIn("inbox-summary.md is 1 day old", b["stale-state"].message)
        for base, _dirs, files in os.walk(os.path.join(TOP, "watchman")):
            for f in files:
                if f.endswith(".py"):
                    with open(os.path.join(base, f), encoding="utf-8") as fh:
                        self.assertNotRegex(fh.read(), r"""f["'][^"'\n]*[a-z]\(s\)""", f"a count with (s) in {f}")

    def test_prompt_drift_action_is_last(self):
        self.write("watchman.toml", '[prompts]\nmirrors = ["prompts/*.md"]\n')
        r = {r.check: r for r in report.run_all(Config.load(self.root), write=False)}["prompt-drift"]
        self.assertTrue(r.message.endswith("Fix the path in the prompt or create what it names."))
        self.assertEqual(r.items[0]["action"], "Fix the path in prompts/daily.md or create invoices/.")

    def test_absence_action_names_the_folder(self):
        for n in (30, 26, 22, 18, 14):
            self.write(f"notes/{(self.today - datetime.timedelta(days=n)).isoformat()}.md", "# n\n")
        self.write("watchman.toml", '[absence]\ndirs = ["notes"]\n')
        r = {r.check: r for r in report.run_all(Config.load(self.root), write=False)}["absence"]
        self.assertEqual(r.status, "WARN")
        self.assertTrue(r.message.endswith("Open notes/ and decide whether it is really quiet or whether the notes moved."))

    def test_closed_sets_names_row_and_states(self):
        self.write("watchman.toml", '[[ledgers]]\nfile = "close/2026-08-31.md"\nkey = "Client"\n'
                   'state_column = "Status"\nstates = ["Paid"]\n')
        r = {r.check: r for r in report.run_all(Config.load(self.root), write=False)}["closed-sets"]
        self.assertEqual(r.status, "FAIL")
        self.assertIn("Edit row 'Northside' in close/2026-08-31.md: set its 'Status' column to one of Paid", r.message)

    def test_heartbeat_stale_ends_in_an_action(self):
        self.write("watchman.toml", '[watchman]\nutc_offset_hours = 0\n')
        cfg = Config.load(self.root)
        report.run_all(cfg)
        hb = json.load(open(cfg.heartbeat))
        hb["ran_at"] = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=60)).isoformat()
        json.dump(hb, open(cfg.heartbeat, "w"))
        r = report.run_all(cfg, write=False)[0]
        self.assertEqual(r.status, "FAIL")
        self.assertIn("off or asleep", r.message)
        self.assertTrue(r.message.endswith("run the board once by hand."))

    def test_no_old_evidence_sentence_anywhere(self):
        for base, dirs, files in os.walk(TOP):
            dirs[:] = [d for d in dirs if d not in ("simulation", "boards", ".git", "__pycache__")]
            for f in files:
                if f.endswith((".py", ".md")) and not f.startswith("board-"):
                    with open(os.path.join(base, f), encoding="utf-8") as fh:
                        self.assertNotIn("healthy is not " + "evidence;", fh.read(), f"old sentence in {f}")


class TestGuessed(Folder):
    def test_discover_writes_the_key_and_the_comment(self):
        run_cli("init", "--discover", self.root)
        text = self.read("watchman.toml")
        self.assertIn("guessed = true    # TODO confirm", text)
        data = Config.load(self.root).data
        self.assertTrue(data["stale_state"]["guessed"])
        self.assertTrue(data["ledgers"][0]["guessed"])
        by_name = {e["name"]: e for e in data["expected"]}
        self.assertTrue(by_name["month-end-close"]["guessed"])
        self.assertNotIn("guessed", by_name["inbox-summary"])

    def test_guessed_section_caps_at_warn(self):
        self.toml_for_missed_run()
        self.write("watchman.toml", self.read("watchman.toml").replace("grace_days = 1", "grace_days = 1\nguessed = true"))
        results = report.run_all(Config.load(self.root), write=False)
        b = {r.check: r for r in results}
        self.assertEqual(b["stale-state"].status, "WARN")
        self.assertTrue(b["stale-state"].message.startswith("unconfirmed:"))
        self.assertEqual(b["expected-run"].status, "FAIL")
        self.assertIn("(3 confirmed, 1 unconfirmed)", report.render(results))
        # still one incident: the confirmed failure and the unconfirmed warning share the file
        self.assertEqual(len(results.incidents), 1)
        self.assertEqual(results.incidents[0].status, "FAIL")

    def test_guessed_expected_entry_warns_alone(self):
        self.toml_for_missed_run()
        self.write("watchman.toml", self.read("watchman.toml").replace("grace_minutes = 0", "grace_minutes = 0\nguessed = true"))
        r = {r.check: r for r in report.run_all(Config.load(self.root), write=False)}["expected-run"]
        self.assertEqual(r.status, "WARN")
        self.assertTrue(r.message.startswith("unconfirmed:"))

    def test_confirm_lists_then_all_removes(self):
        run_cli("init", "--discover", self.root)
        code, out = run_cli("confirm", "--root", self.root)
        self.assertEqual(code, 0)
        self.assertIn("3 guessed sections", out)
        self.assertIn("[stale_state] inbox-summary.md", out)
        self.assertIn("[[expected]] month-end-close", out)
        self.assertIn("guessed = true", self.read("watchman.toml"))        # listing changed nothing
        code, out = run_cli("confirm", "--all", "--root", self.root)
        self.assertIn("confirmed 3 sections", out)
        text = self.read("watchman.toml")
        self.assertFalse(any(l.startswith("guessed") for l in text.splitlines()))
        self.assertIn("# TODO confirm: how many days old", text)             # other comments survive
        self.assertEqual(confirm.guessed_sections(text), [])
        _code, out = run_cli("confirm", "--root", self.root)
        self.assertIn("every section is confirmed", out)


    def test_confirm_lists_evidence_and_both_commands_on_one_line(self):
        # item 3: what it is, what it was guessed from, accept-all, or the toml line to edit
        run_cli("init", "--discover", self.root)
        _code, out = run_cli("confirm", "--root", self.root)
        rows = [l for l in out.splitlines() if l.startswith(("[", "(top)"))]
        self.assertEqual(len(rows), 3)
        accept = f"To accept: python3 -m watchman confirm --all --root {self.root}."
        for row in rows:
            self.assertIn("guessed from: ", row)
            self.assertIn(accept, row)
            self.assertRegex(row, r"To change: edit line \d+ of watchman\.toml \(.+\)")
            self.assertRegex(row, r"then delete line \d+ \(guessed = true\)\.$")
        expected = next(r for r in rows if r.startswith("[[expected]] month-end-close"))
        self.assertIn("guessed from: 1 line in runs.log start with a timestamp and name 'month-end-close'", expected)
        self.assertIn('(schedule = "monthly last 23:30")', expected)
        toml = self.read("watchman.toml").splitlines()
        n = int(re.search(r"To change: edit line (\d+)", expected).group(1))
        self.assertTrue(toml[n - 1].startswith('schedule = "monthly last 23:30"'))
        g = int(re.search(r"then delete line (\d+)", expected).group(1))
        self.assertTrue(toml[g - 1].startswith("guessed = true"))
        # and install says how many were guessed, with the command
        os.environ["WATCHMAN_DRY_SCHEDULE"] = "1"
        try:
            _code, out = run_cli("install", self.root)
        finally:
            os.environ.pop("WATCHMAN_DRY_SCHEDULE", None)
        self.assertIn(f"3 rules were guessed and will only warn until you confirm them: python3 -m watchman confirm --root {self.root}", out)


class TestFirstRunAndSparse(Folder):
    def test_first_run_is_ok(self):
        self.write("watchman.toml", '[watchman]\nutc_offset_hours = 0\n')
        results = report.run_all(Config.load(self.root))
        self.assertEqual(results[0].status, "PASS")
        self.assertEqual(results[0].message, "first run over this folder; the next run will compare against it")
        self.assertEqual(report.exit_code(results), 0)
        self.assertEqual(report.run_all(Config.load(self.root))[0].status, "PASS")
        self.assertIn("last run", report.run_all(Config.load(self.root))[0].message)

    def test_absence_needs_five_dated_files(self):
        self.write("watchman.toml", '[absence]\ndirs = ["notes"]\nmin_dates = 2\n')
        r = {r.check: r for r in report.run_all(Config.load(self.root), write=False)}["absence"]
        self.assertEqual(r.status, "PASS")
        self.assertEqual(r.message, "not enough history to know the cadence yet (4 dated files; 5 needed per series)")
        self.write("notes/2026-08-10.md", "# n\n")
        r = {r.check: r for r in report.run_all(Config.load(self.root), write=False)}["absence"]
        self.assertEqual(r.status, "WARN")
        self.assertIn("notes/ (last dated 2026-08-25", r.message)


class TestInstall(Folder):
    def setUp(self):
        super().setUp()
        os.environ["WATCHMAN_DRY_SCHEDULE"] = "1"

    def tearDown(self):
        os.environ.pop("WATCHMAN_DRY_SCHEDULE", None)
        super().tearDown()

    def test_one_command_does_all_of_it(self):
        code, out = run_cli("install", self.root, "--at", "02:15")
        self.assertEqual(code, 0)
        self.assertTrue(os.path.exists(os.path.join(self.root, "watchman.toml")))
        self.assertTrue(os.path.exists(os.path.join(self.root, "WATCHMAN.md")))
        self.assertTrue(os.path.exists(os.path.join(self.root, ".watchman", "heartbeat.json")))
        self.assertIn("looked at", out)                        # discover
        self.assertIn("checks fit this folder", out)           # doctor
        self.assertIn("[ FAIL ] prompt-drift", out)            # the board
        self.assertIn("wrote WATCHMAN.md", out)
        self.assertTrue("would append to crontab: 15 2 * * *" in out or "would write" in out)
        self.assertTrue(out.rstrip().endswith(
            f"Done. Watchman checks {self.root} every night at 02:15 and writes WATCHMAN.md when something needs you."))

    def test_existing_toml_is_kept_and_no_schedule(self):
        self.write("watchman.toml", '[prompts]\nmirrors = ["prompts/*.md"]\n# mine\n')
        code, out = run_cli("install", self.root, "--no-schedule")
        self.assertEqual(code, 0)
        self.assertIn("using the watchman.toml already in", out)
        self.assertIn("# mine", self.read("watchman.toml"))
        self.assertIn("Not scheduled (--no-schedule)", out)
        self.assertNotIn("would append", out)
        self.assertNotIn("Done. Watchman checks", out)
        self.assertTrue(out.rstrip().endswith(f"the nightly line is `python3 -m watchman install-cron --root {self.root}`."))

    def test_unscheduled_install_says_so_and_exits_3(self):
        # item 1: no Done line unless the schedule was read back; the line to paste is last but one
        os.environ.pop("WATCHMAN_DRY_SCHEDULE", None)
        with mock.patch.object(install.sys, "platform", "linux"), \
                mock.patch.object(install.shutil, "which", return_value=None):
            code, out = run_cli("install", self.root, "--at", "02:15")
        self.assertEqual(code, 3)
        lines = out.rstrip().splitlines()
        self.assertEqual(lines[-1], cli.NOT_SCHEDULED)
        self.assertEqual(lines[-1], "WATCHMAN IS NOT SCHEDULED. Paste the line above into crontab (crontab -e) before you close this terminal. Everything else is in place.")
        self.assertTrue(lines[-2].strip().startswith("15 2 * * * "))
        self.assertIn("-m watchman --root", lines[-2])
        self.assertNotIn("Done. Watchman checks", out)
        self.assertTrue(os.path.exists(os.path.join(self.root, "WATCHMAN.md")))
        # `crontab -` returning 0 is not enough either: the line has to show in `crontab -l`
        fake = mock.Mock(returncode=0, stdout="", stderr="")
        with mock.patch.object(install.sys, "platform", "linux"), \
                mock.patch.object(install.shutil, "which", return_value="/usr/bin/crontab"), \
                mock.patch.object(install.subprocess, "run", return_value=fake):
            code, out = run_cli("install", self.root)
        self.assertEqual(code, 3)
        self.assertEqual(out.rstrip().splitlines()[-1], cli.NOT_SCHEDULED)
        self.assertIn("does not show the line", out)
        # and when it does show, the Done line is the last thing said
        cron = install.cron_line([self.root], "01:31")[0]
        shown = mock.Mock(returncode=0, stdout=cron + "\n", stderr="")
        with mock.patch.object(install.sys, "platform", "linux"), \
                mock.patch.object(install.shutil, "which", return_value="/usr/bin/crontab"), \
                mock.patch.object(install.subprocess, "run", return_value=shown):
            code, out = run_cli("install", self.root)
        self.assertEqual(code, 0)
        self.assertTrue(out.rstrip().endswith("when something needs you."))

    def test_schedule_dry_on_both_platforms(self):
        lines, how = install.schedule([self.root], "01:31", platform="linux")
        self.assertEqual(how, "dry")
        self.assertIn("31 1 * * *", lines[0])
        lines, how = install.schedule([self.root], "01:31", platform="darwin")
        self.assertEqual(how, "dry")
        self.assertIn("launchctl load", lines[0])
        self.assertFalse(os.path.exists(os.path.expanduser("~/Library/LaunchAgents/com.watchman."
                                                           + os.path.basename(self.root) + ".plist")))

    def test_not_a_folder(self):
        code, out = run_cli("install", os.path.join(self.root, "nope"))
        self.assertEqual(code, 2)
        self.assertIn("is not a folder", out)


class TestReadme(unittest.TestCase):
    def test_first_screen_is_two_lines(self):
        with open(os.path.join(TOP, "README.md"), encoding="utf-8") as fh:
            text = fh.read()
        head = text[:text.index("## Step by step")]
        self.assertIn("python3 -m watchman install FOLDER", head)
        self.assertIn("then read `FOLDER/WATCHMAN.md` each morning; it only lists what needs you", head)
        self.assertNotIn("install-cron", head)
        self.assertIn("## Step by step", text)
        self.assertIn("A scheduler that says healthy is not sufficient evidence; the file the job touches is.", text)

    def test_first_sentence_says_what_it_is_for(self):
        # item 6
        with open(os.path.join(TOP, "README.md"), encoding="utf-8") as fh:
            lines = [l for l in fh.read().splitlines() if l.strip()]
        self.assertEqual(lines[0], "# watchman")
        first = "Watchman tells you the next morning when one of your scheduled file-producing jobs silently stopped updating its output, and tells you what to do next."
        self.assertTrue(lines[1].startswith(first + " Trace systems tell you whether a run behaved correctly."))


class TestReviewRoundTwo(Folder):
    """The seven fixes from the second pair of outside reviews, one test each."""

    def runs_log(self, lines):
        self.write("runs.log", "".join(lines))

    def d(self, n):
        return (self.today - datetime.timedelta(days=n)).isoformat()

    def test_1_space_separated_stamps_are_evidence(self):
        # "2026-08-31 23:32 job ok" was proposed a pattern that only matched the T form
        self.runs_log([f"{self.d(n)} 07:00:0{n} ledger-sync ok\n" for n in (5, 4, 3, 2, 1, 0)])
        text, _ = discover.discover(self.root)
        spec = next(e for e in toml_min.loads(text)["expected"] if e["name"] == "ledger-sync")
        self.assertEqual(spec["pattern"], r"^(\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?)?)\s+ledger-sync\b")
        for form in (f"{self.d(0)} 07:00:00 ledger-sync ok", f"{self.d(0)}T07:00 ledger-sync ok", f"{self.d(0)} ledger-sync ok"):
            m = re.match(spec["pattern"], form)
            self.assertIsNotNone(m, form)
            self.assertEqual(expected_run._parse_stamp(m.group(1), None).date(), self.today)
        self.write("watchman.toml", '[watchman]\nutc_offset_hours = %g\n\n[[expected]]\nname = "ledger-sync"\n'
                   'schedule = "daily 00:00"\nevidence = "runs.log"\npattern = %s\ngrace_minutes = 0\n'
                   % (local_utc_offset(), "'" + spec["pattern"] + "'"))
        r = {r.check: r for r in report.run_all(Config.load(self.root), write=False)}["expected-run"]
        self.assertEqual(r.status, "PASS", r.message)

    def test_2_pattern_matching_nothing_is_broken_not_silent(self):
        self.runs_log([f"{self.d(0)} 07:00:00 ledger-sync ok\n"])
        self.write("watchman.toml", '[watchman]\nutc_offset_hours = 0\n\n[[expected]]\nname = "ledger-sync"\n'
                   'schedule = "daily 00:00"\nevidence = "runs.log"\npattern = "^(\\\\S+) other-job"\ngrace_minutes = 0\n')
        results = report.run_all(Config.load(self.root), write=False)
        r = {r.check: r for r in results}["expected-run"]
        self.assertEqual(r.status, "FAIL")
        self.assertIn("1 job could not be checked: ledger-sync: pattern matches no line in runs.log; fix the pattern or remove it", r.message)
        self.assertNotIn("fired with no evidence", r.message)
        self.assertNotIn("left no expected evidence", report.render(results))
        self.assertTrue(r.message.endswith("`watchman doctor` names the line."))
        _code, out = run_cli("doctor", "--root", self.root)
        self.assertIn("ledger-sync: pattern '^(\\\\S+) other-job' matches no line in runs.log; fix the pattern or remove it", out)
        self.assertIn("1 to fix", out)

    def test_3_two_jobs_sharing_a_log_are_two_incidents(self):
        self.runs_log([f"{self.d(3)} 07:00:00 ledger-sync ok\n", f"{self.d(3)} 08:00:00 chaser ok\n"])
        # this machine's zone, not UTC: self.d() counts back from the local date, so a
        # hardcoded 0 makes the check's "today" a day behind the fixture's wherever
        # local and UTC dates differ, and the age assertions below are off by one
        self.write("watchman.toml", f'[watchman]\nutc_offset_hours = {local_utc_offset():g}\n\n'
                   '[[expected]]\nname = "ledger-sync"\nschedule = "daily 00:00"\nevidence = "runs.log"\n'
                   "pattern = '^(\\S+ \\S+) ledger-sync'\ngrace_minutes = 0\n\n"
                   '[[expected]]\nname = "chaser"\nschedule = "daily 00:00"\nevidence = "runs.log"\n'
                   "pattern = '^(\\S+ \\S+) chaser'\ngrace_minutes = 0\n")
        results = report.run_all(Config.load(self.root), write=False)
        live = sorted(i.text for i in results.incidents)
        self.assertEqual(len(live), 2)
        self.assertTrue(live[0].startswith("chaser left no expected evidence"))
        self.assertTrue(live[1].startswith("ledger-sync left no expected evidence"))
        actions = {i.text.split()[0]: i.action for i in results.incidents}
        self.assertTrue(actions["chaser"].startswith("Check the chaser job."))
        self.assertTrue(actions["ledger-sync"].startswith("Check the ledger-sync job."))
        # a stale file folds with the job whose evidence it is, or whose name it carries, and no other
        self.write("chaser.md", f"Generated {self.d(4)} 08:00\n")
        self.write("watchman.toml", self.read("watchman.toml") + "\n[stale_state]\nfile = \"chaser.md\"\n"
                   "marker = 'Generated (\\d{4}-\\d{2}-\\d{2})'\ngrace_days = 1\n")
        results = report.run_all(Config.load(self.root), write=False)
        self.assertEqual(len(results.incidents), 2)
        chaser = next(i for i in results.incidents if i.text.startswith("chaser"))
        self.assertIn("chaser.md is 4 days old", chaser.text)
        ledger = next(i for i in results.incidents if i.text.startswith("ledger-sync"))
        self.assertNotIn("chaser.md", ledger.text)

    def test_4_ran_but_still_says(self):
        # the sentence the product exists for: the job left a log line today, the summary did not move
        self.write("inbox-summary.md", f"# Inbox summary\n\nGenerated {self.d(3)} 06:00 from 14 emails\n")
        self.runs_log([f"{self.d(n)} 06:01:0{n} inbox-summary ok\n" for n in (6, 5, 4, 3, 2, 1, 0)])
        text, guesses = discover.discover(self.root)
        data = toml_min.loads(text)
        self.assertEqual(data["stale_state"]["file"], "inbox-summary.md")
        spec = next(e for e in data["expected"] if e["name"] == "inbox-summary")
        self.assertEqual(spec["evidence"], "runs.log")
        self.assertNotIn("guessed", spec)
        self.assertTrue(any("[[expected]] inbox-summary: daily 06:00, evidence runs.log" in g for g in guesses))
        self.write("watchman.toml", text)
        run_cli("confirm", "--all", "--root", self.root)
        results = report.run_all(Config.load(self.root))
        b = {r.check: r for r in results}
        self.assertEqual(b["expected-run"].status, "PASS")
        self.assertEqual(b["stale-state"].status, "FAIL")
        live = [i for i in results.incidents if i.state != "resolved"]
        self.assertEqual(len(live), 2)                  # this one, and the fixture's dead prompt path
        self.assertTrue(live[1].text.startswith("prompts/daily.md names invoices/"))
        self.assertEqual(live[0].line(), f"new:         inbox-summary ran at {self.d(0)} 06:01 but inbox-summary.md "
                                         f"still says {self.d(3)}. The job ran without updating its output; "
                                         "check what it wrote and where.")
        self.assertIn(f"- new: inbox-summary ran at {self.d(0)} 06:01 but inbox-summary.md still says {self.d(3)}. "
                      "The job ran without updating its output; check what it wrote and where.", self.read("WATCHMAN.md"))
        # once the summary catches up, the incident resolves
        self.write("inbox-summary.md", f"# Inbox summary\n\nGenerated {self.d(0)} 06:00 from 14 emails\n")
        results = report.run_all(Config.load(self.root))
        self.assertEqual([i.state for i in results.incidents if "inbox-summary" in i.text], ["resolved"])

    def test_5_a_period_folder_stops_when_its_period_ends(self):
        t = self.today
        first = t.replace(day=1)
        last_month_end = first - datetime.timedelta(days=1)
        ym = last_month_end.strftime("%Y-%m")
        # five dated files in a month folder, ending on that month's last day
        for n in (12, 9, 6, 3, 0):
            day = last_month_end - datetime.timedelta(days=n)
            self.write(f"log/{ym}/{day.isoformat()}.md", "# n\n")
        # a plain folder that also stopped on the last day of last month
        for n in (12, 9, 6, 3, 0):
            day = last_month_end - datetime.timedelta(days=n)
            self.write(f"closes/{day.isoformat()}.md", "# n\n")
        # and one that just went quiet, for contrast
        for n in (30, 27, 24, 21, 18):
            self.write(f"notes/{(t - datetime.timedelta(days=n)).isoformat()}.md", "# n\n")
        self.write("watchman.toml", f'[absence]\ndirs = ["log/{ym}", "closes", "notes"]\n')
        r = {r.check: r for r in report.run_all(Config.load(self.root), write=False)}["absence"]
        self.assertEqual(r.status, "WARN")
        self.assertIn("1 of 3 gone quiet", r.message)
        self.assertIn("notes/ (last dated", r.message)
        self.assertNotIn(f"log/{ym}/", r.message.split("cadence:")[1].split("·")[0])
        self.assertNotIn("closes/", r.message.split("cadence:")[1].split("·")[0])
        self.assertIn("2 ended with their period", r.message)
        # the same folders before the period ends are measured like any other
        from watchman.checks import absence
        self.assertFalse(absence._ended(f"log/{ym}/", [last_month_end], last_month_end))
        self.assertTrue(absence._ended(f"log/{ym}/", [last_month_end], first))
        self.assertTrue(absence._ended("log/2026-08-31/", [datetime.date(2026, 8, 20)], datetime.date(2026, 9, 1)))
        self.assertFalse(absence._ended("closes/", [datetime.date(2026, 8, 31)], datetime.date(2026, 8, 31)))
        self.assertFalse(absence._ended("brain/x.md", [datetime.date(2026, 8, 31)], datetime.date(2026, 9, 7)))

    def test_6_readme_is_one_screen_and_the_version_story_is_one_sentence(self):
        with open(os.path.join(TOP, "README.md"), encoding="utf-8") as fh:
            text = fh.read()
        self.assertNotIn("0.1.", text)
        self.assertIn("0.2.0, frozen from the first nightly run on 7 September 2026 for the 28-day self-test", text)
        self.assertNotIn("That is the whole difference", text)
        self.assertNotIn("needs no telemetry from the agent", text)
        self.assertIn("expected-run needs nothing from the agent; degraded-steps needs the job to write its own step-state", text)
        self.assertIn("## Advanced checks", text)
        self.assertIn("docs/checks.md", text)
        self.assertLess(len(text.splitlines()), 120)
        with open(os.path.join(TOP, "docs", "checks.md"), encoding="utf-8") as fh:
            checks = fh.read()
        self.assertIn("| Check | Kind | What it needs from the folder |", checks)
        for name in ("stale-state", "degraded-steps", "prompt-drift", "closed-sets", "append-only-log",
                     "read-budget", "stated-vs-measured", "no-vacuous-pass", "intervention-tally",
                     "absence", "citation-resolves", "cannot-list", "heartbeat", "expected-run"):
            self.assertIn(name, checks)

    def test_7_notice_names_the_other_watchman(self):
        with open(os.path.join(TOP, "NOTICE.md"), encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("Not affiliated with Facebook's Watchman (file watching service).", text)
        self.assertIn("This project may be renamed; the current name is a working title.", text)


if __name__ == "__main__":
    unittest.main()
