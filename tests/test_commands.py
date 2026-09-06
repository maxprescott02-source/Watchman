"""The commands the operator meets first: init --discover, doctor, install-cron, and the
date mode of stale-state. Run with: python3 -m unittest discover -s tests"""
import datetime
import io
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout

from watchman import cli, discover, doctor, install, report, toml_min
from watchman.config import Config


def stranger(root, today):
    """A small-business agent folder that is not shaped like brain-ops."""
    d = lambda n: (today - datetime.timedelta(days=n)).isoformat()      # noqa: E731
    files = {
        "inbox-summary.md": f"# Inbox summary\n\nGenerated {d(1)} 06:00 from 14 emails\n\n- Karen: invoice\n",
        "close/2026-08-31.md": ("# Close\n\n| Client | Invoiced | Status |\n|---|---|---|\n"
                                "| Doyle | 4200 | Paid |\n| Northside | 1850 | Outstanding |\n"),
        "clients.csv": "client,email,status\nDoyle,k@d.com,active\n",
        "tasks.md": "# Tasks\n\n- [ ] Chase Northside\n",
        "runs.log": "".join(f"{d(n)}T06:01:0{n} inbox-summary ok\n" for n in (6, 5, 4, 3, 2, 1))
                    + "2026-08-31T23:30:12 month-end-close ok\n",
        "prompts/daily.md": ("# Daily\n\nRewrite `inbox-summary.md`, tick `tasks.md`, append to "
                             "`runs.log`. Invoices are in `invoices/`.\n"),
        "notes/2026-08-14.md": "# Notes\n\n- called Karen\n",
        "notes/2026-08-18.md": "# Notes\n\n- quote\n",
        "notes/2026-08-21.md": "# Notes\n\n- quote\n",
        "notes/2026-08-25.md": "# Notes\n\n- quote\n",
    }
    for rel, text in files.items():
        p = os.path.join(root, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(text)
    return files


class Stranger(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="watchman-stranger-")
        self.today = datetime.date.today()
        stranger(self.root, self.today)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def run_cli(self, *args):
        out = io.StringIO()
        with redirect_stdout(out):
            code = cli.main(list(args))
        return code, out.getvalue()


class TestDiscover(Stranger):
    def test_proposes_every_shape_it_saw(self):
        text, guesses = discover.discover(self.root)
        data = toml_min.loads(text)
        self.assertEqual(data["stale_state"]["file"], "inbox-summary.md")
        self.assertIn("Generated", data["stale_state"]["marker"])
        names = {e["name"]: e for e in data["expected"]}
        self.assertEqual(names["inbox-summary"]["schedule"], "daily 06:00")
        self.assertEqual(names["month-end-close"]["schedule"], "monthly last 23:30")
        self.assertEqual(data["prompts"]["mirrors"], ["prompts/*.md"])
        self.assertEqual(data["absence"]["dirs"], ["notes"])
        self.assertEqual(data["ledgers"][0]["state_column"], "Status")
        self.assertEqual(data["ledgers"][0]["states"], ["Outstanding", "Paid"])
        self.assertIn("TODO confirm", text)
        self.assertIn("clients.csv has a status column", text)
        self.assertTrue(any("[[expected]] inbox-summary" in g for g in guesses))

    def test_init_discover_writes_and_names_next_step(self):
        code, out = self.run_cli("init", "--discover", self.root)
        self.assertEqual(code, 0)
        self.assertTrue(os.path.exists(os.path.join(self.root, "watchman.toml")))
        self.assertIn("doctor", out)
        # the folder's own files are untouched and nothing demo-shaped appeared
        self.assertFalse(os.path.exists(os.path.join(self.root, "now.md")))

    def test_init_on_a_full_folder_does_not_write_the_demo(self):
        code, out = self.run_cli("init", "--demo", self.root)
        self.assertEqual(code, 2)
        self.assertIn("--discover", out)
        self.assertFalse(os.path.exists(os.path.join(self.root, "now.md")))

    def test_init_without_flags_discovers_when_files_exist(self):
        code, out = self.run_cli("init", self.root)
        self.assertEqual(code, 0)
        self.assertIn("guessed", out)
        self.assertFalse(os.path.exists(os.path.join(self.root, "cannots.md")))

    def test_existing_toml_is_not_overwritten(self):
        self.run_cli("init", "--discover", self.root)
        with open(os.path.join(self.root, "watchman.toml"), "a") as fh:
            fh.write("\n# mine\n")
        code, out = self.run_cli("init", "--discover", self.root)
        self.assertIn("watchman.proposed.toml", out)
        with open(os.path.join(self.root, "watchman.toml")) as fh:
            self.assertIn("# mine", fh.read())

    def test_init_discover_takes_several_folders(self):
        other = tempfile.mkdtemp(prefix="watchman-other-")
        try:
            stranger(other, self.today)
            code, out = self.run_cli("init", "--discover", self.root, other)
            self.assertEqual(code, 0)
            self.assertTrue(os.path.exists(os.path.join(other, "watchman.toml")))
            self.assertEqual(out.count("looked at"), 2)
        finally:
            shutil.rmtree(other, ignore_errors=True)

    def test_empty_folder_says_so(self):
        empty = tempfile.mkdtemp(prefix="watchman-empty-")
        try:
            _text, guesses = discover.discover(empty)
            self.assertTrue(any("nothing recognisable" in g for g in guesses))
        finally:
            shutil.rmtree(empty)


class TestBoardOnStranger(Stranger):
    def board(self):
        self.run_cli("init", "--discover", self.root)
        return {r.check: r for r in report.run_all(Config.load(self.root), write=False)}

    def test_first_red_line_names_the_missed_run(self):
        # the summary was generated yesterday 06:00; today's 06:00 fire left nothing
        b = self.board()
        # the job is only overdue once today's 06:00 plus grace has passed
        if datetime.datetime.now().hour >= 8:
            self.assertEqual(b["expected-run"].status, "FAIL")
            self.assertIn("inbox-summary", b["expected-run"].message)
        self.assertEqual(b["prompt-drift"].status, "FAIL")
        self.assertIn("invoices/", b["prompt-drift"].message)
        self.assertEqual(b["closed-sets"].status, "PASS")
        # four dated notes is not a cadence yet
        self.assertEqual(b["absence"].status, "PASS")
        self.assertIn("not enough history to know the cadence yet (4 dated files", b["absence"].message)

    def test_stale_state_date_mode_against_today(self):
        b = self.board()
        self.assertEqual(b["stale-state"].status, "PASS")     # 1 day old, grace 1
        self.assertIn("date mode", "".join(doctor.run(Config.load(self.root))[0]))
        with open(os.path.join(self.root, "inbox-summary.md"), "w") as fh:
            fh.write(f"# Inbox summary\n\nGenerated {(self.today - datetime.timedelta(days=4)).isoformat()} 06:00\n")
        r = {r.check: r for r in report.run_all(Config.load(self.root), write=False)}["stale-state"]
        # the proposed section is guessed, so it can only warn until confirmed
        self.assertEqual(r.status, "WARN")
        self.assertTrue(r.message.startswith("unconfirmed:"))
        self.assertIn("4 days old", r.message)
        self.run_cli("confirm", "--all", "--root", self.root)
        r = {r.check: r for r in report.run_all(Config.load(self.root), write=False)}["stale-state"]
        self.assertEqual(r.status, "FAIL")
        self.assertIn("off or asleep", r.message)
        self.assertTrue(r.message.endswith("if it already ran, check why inbox-summary.md was not updated."))

    def test_stale_state_date_mode_against_sources(self):
        self.run_cli("init", "--discover", self.root)
        with open(os.path.join(self.root, "watchman.toml"), "a") as fh:
            fh.write("\n")
        p = os.path.join(self.root, "watchman.toml")
        with open(p) as fh:
            text = fh.read()
        text = text.replace("sources = []", 'sources = ["runs.log"]')
        with open(p, "w") as fh:
            fh.write(text)
        old = (datetime.datetime.now() - datetime.timedelta(days=9)).timestamp()
        os.utime(os.path.join(self.root, "runs.log"), (old, old))
        r = {r.check: r for r in report.run_all(Config.load(self.root), write=False)}["stale-state"]
        self.assertEqual(r.status, "PASS")
        self.assertIn("runs.log", r.message)
        # a source that moved on after the summary was generated
        with open(os.path.join(self.root, "runs.log"), "a") as fh:
            fh.write(f"{self.today.isoformat()}T06:01:00 inbox-summary ok\n")
        r = {r.check: r for r in report.run_all(Config.load(self.root), write=False)}["stale-state"]
        self.assertIn("runs.log", r.message)

    def test_marker_that_captures_neither_number_nor_date(self):
        self.run_cli("init", "--discover", self.root)
        self.run_cli("confirm", "--all", "--root", self.root)
        p = os.path.join(self.root, "watchman.toml")
        with open(p) as fh:
            text = fh.read()
        with open(p, "w") as fh:
            fh.write(text.replace("marker = 'Generated\\s*(\\d{4}-\\d{2}-\\d{2})'", "marker = '(Generated)'"))
        r = {r.check: r for r in report.run_all(Config.load(self.root), write=False)}["stale-state"]
        self.assertEqual(r.status, "FAIL")
        self.assertIn("neither an entry number nor a date", r.message)


class TestDoctor(Stranger):
    def test_every_section_gets_a_line_and_exit_is_zero(self):
        self.run_cli("init", "--discover", self.root)
        code, out = self.run_cli("doctor", "--root", self.root)
        self.assertEqual(code, 0)
        for section in ("[watchman]", "[stale_state]", "[[expected]]", "[prompts]", "[absence]", "[[ledgers]]"):
            self.assertIn(section, out)
        self.assertIn("0 to fix", out)
        self.assertIn("6 checks fit this folder. The others need conventions this folder does not use, and stay off.", out)
        self.assertNotIn("off (no section", out)
        self.assertNotIn("citation-resolves", out)
        _code, out = self.run_cli("doctor", "--root", self.root, "--verbose")
        self.assertIn("off (no section in watchman.toml): stated-vs-measured", out)
        self.assertIn("citation-resolves", out)

    def test_names_what_is_missing(self):
        with open(os.path.join(self.root, "watchman.toml"), "w") as fh:
            fh.write('[stale_state]\nfile = "gone.md"\nmarker = "x(\\\\d+)"\n\n'
                     '[[expected]]\nname = "j"\nschedule = "monthly"\nevidence = "never.txt"\n\n'
                     '[[expected]]\nname = "k"\nschedul = "daily 06:00"\nevidence = "runs.log"\n\n'
                     '[prompts]\nmirrors = ["nowhere/*.md"]\n')
        code, out = self.run_cli("doctor", "--root", self.root)
        self.assertEqual(code, 0)
        self.assertIn("gone.md does not exist", out)
        self.assertIn("accepted forms are", out)
        self.assertIn("needs both `schedule =` and `evidence =`", out)
        self.assertIn("matches nothing", out)
        self.assertIn("to fix", out)

    def test_global_options_may_follow_the_subcommand(self):
        self.run_cli("init", "--discover", self.root)
        code_a, out_a = self.run_cli("doctor", "--root", self.root)
        code_b, out_b = self.run_cli("--root", self.root, "doctor")
        self.assertEqual((code_a, out_a), (code_b, out_b))


class TestExpectedForms(Stranger):
    def test_monthly_last_and_day(self):
        at = datetime.datetime(2026, 9, 6, 23, 50)
        from watchman.checks.expected_run import _last_fire
        self.assertEqual(_last_fire("monthly last 23:30", at), datetime.datetime(2026, 8, 31, 23, 30))
        self.assertEqual(_last_fire("monthly 1 09:00", at), datetime.datetime(2026, 9, 1, 9, 0))
        self.assertEqual(_last_fire("30 23 31 * *", at), datetime.datetime(2026, 8, 31, 23, 30))
        with self.assertRaises(ValueError) as cm:
            _last_fire("monthly", at)
        self.assertIn("accepted forms", str(cm.exception))

    def test_config_mistakes_are_not_counted_as_silent_jobs(self):
        with open(os.path.join(self.root, "watchman.toml"), "w") as fh:
            fh.write('[[expected]]\nname = "bad"\nschedule = "fortnightly"\nevidence = "runs.log"\n')
        r = {r.check: r for r in report.run_all(Config.load(self.root), write=False)}["expected-run"]
        self.assertEqual(r.status, "FAIL")
        self.assertIn("could not be checked", r.message)
        self.assertNotIn("fired with no evidence", r.message)


class TestInstallCron(Stranger):
    def test_prints_a_crontab_line_and_writes_nothing(self):
        code, out = self.run_cli("install-cron", "--root", self.root, "--at", "02:15")
        self.assertEqual(code, 0)
        self.assertIn("15 2 * * *", out)
        self.assertIn("-m watchman --root", out)
        self.assertIn("crontab -e", out)

    def test_mac_plist_is_printed_then_written(self):
        home = tempfile.mkdtemp(prefix="watchman-home-")
        old = os.environ.get("HOME")
        os.environ["HOME"] = home
        try:
            lines, written = install.plan(self.root, "01:31", write=False, platform="darwin")
            self.assertIsNone(written)
            self.assertIn("<key>Label</key>", "\n".join(lines))
            lines, written = install.plan(self.root, "01:31", write=True, platform="darwin")
            self.assertTrue(written.startswith(os.path.join(home, "Library", "LaunchAgents")))
            self.assertTrue(os.path.exists(written))
            self.assertIn("launchctl load", "\n".join(lines))
        finally:
            if old is not None:
                os.environ["HOME"] = old
            shutil.rmtree(home, ignore_errors=True)

    def test_bad_time(self):
        with self.assertRaises(SystemExit):
            install.plan(self.root, "2am")

    def test_several_roots_make_one_line_with_reports_together(self):
        other = tempfile.mkdtemp(prefix="watchman-other-")
        try:
            lines, _ = install.plan([self.root, other], "01:31", findings="/reports/{name}-{date}.md")
            line = next(l for l in lines if l.strip().startswith("31 1"))
            self.assertIn(f"--root '{self.root}' --root '{other}'", line)
            self.assertIn("--findings '/reports/{name}-{date}.md'", line)
            self.assertIn("mkdir -p '/reports'", line)
            self.assertIn("'/reports/last-board.txt'", line)
        finally:
            shutil.rmtree(other, ignore_errors=True)


class TestManyRoots(Stranger):
    def test_two_roots_two_boards_two_findings(self):
        other = tempfile.mkdtemp(prefix="watchman-other-")
        reports = tempfile.mkdtemp(prefix="watchman-reports-")
        try:
            stranger(other, self.today)
            self.run_cli("init", "--discover", self.root)
            self.run_cli("init", "--discover", other)
            code, out = self.run_cli("--root", self.root, "--root", other, "--no-write",
                                     "--findings", os.path.join(reports, "{name}-{date}.md"))
            self.assertEqual(code, 1)
            self.assertIn(f"== {self.root}", out)
            self.assertIn(f"== {other}", out)
            written = sorted(os.listdir(reports))
            self.assertEqual(len(written), 2)
            self.assertTrue(all(f.endswith(f"-{self.today.isoformat()}.md") for f in written))
            with open(os.path.join(reports, written[0])) as fh:
                text = fh.read()
            self.assertIn("# Findings: " + written[0].split("-2")[0], text)
        finally:
            shutil.rmtree(other, ignore_errors=True)
            shutil.rmtree(reports, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
