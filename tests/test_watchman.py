"""Run with: python3 -m unittest discover -s tests"""
import datetime
import io
import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout

from watchman import cli, report, toml_min
from watchman.checks import heartbeat
from watchman.config import Config
from watchman.init import TOML, write_fixture

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.join(os.path.dirname(HERE), "watchman")


def board(root, write=True):
    return {r.check: r for r in report.run_all(Config.load(root), write=write)}


class Fixture(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="watchman-")
        self.today = datetime.date.today()
        write_fixture(self.root, self.today)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def edit(self, rel, old, new):
        p = os.path.join(self.root, rel)
        with open(p, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn(old, text)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(text.replace(old, new))


class TestDemoBoard(Fixture):
    def test_mixed_board_as_designed(self):
        b = board(self.root)
        want = {"heartbeat": "WARN", "stale-state": "FAIL", "stated-vs-measured": "PASS",
                "degraded-steps": "WARN", "prompt-drift": "PASS", "closed-sets": "FAIL",
                "intervention-tally": "WARN", "absence": "WARN", "append-only-log": "PASS",
                "citation-resolves": "FAIL", "cannot-list": "WARN", "read-budget": "PASS",
                "no-vacuous-pass": "PASS"}
        self.assertEqual({k: v.status for k, v in b.items()}, want)
        self.assertEqual(report.exit_code(list(b.values())), 1)

    def test_count_is_computed_not_stated(self):
        text = report.render(list(board(self.root).values()))
        self.assertIn("5 passed · 5 warnings · 3 failed · 13 checks ran", text)

    def test_json_output(self):
        data = json.loads(report.render_json(list(board(self.root).values())))
        self.assertEqual(data["counts"]["FAIL"], 3)
        self.assertTrue(all("floor" in r for r in data["results"]))


class TestHeartbeat(Fixture):
    def test_second_run_passes_then_stale_fails(self):
        board(self.root)
        self.assertEqual(board(self.root)["heartbeat"].status, "PASS")
        cfg = Config.load(self.root)
        hb = heartbeat.read(cfg)
        hb["ran_at"] = (datetime.datetime.now(datetime.timezone.utc)
                        - datetime.timedelta(hours=50)).isoformat()
        with open(cfg.heartbeat, "w") as fh:
            json.dump(hb, fh)
        self.assertEqual(heartbeat.run(cfg, first_run_ok=False).status, "FAIL")

    def test_second_runner_fails_on_missing(self):
        with redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(["--root", self.root, "heartbeat"]), 1)
        board(self.root)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(["--root", self.root, "heartbeat"]), 0)


class TestLog(Fixture):
    def test_append_allocates_next_number(self):
        with redirect_stdout(io.StringIO()):
            cli.main(["--root", self.root, "log", "Six"])
            cli.main(["--root", self.root, "log", "Seven", "--body", "body"])
        b = board(self.root, write=False)
        self.assertIn("7 entries", b["append-only-log"].message)

    def test_duplicate_number_fails(self):
        self.edit(f"log/{self.today.strftime('%Y-%m')}.md", "Entry 5 ", "Entry 4 ")
        r = board(self.root, write=False)["append-only-log"]
        self.assertEqual(r.status, "FAIL")
        self.assertIn("duplicate", r.message)

    def test_stale_state_passes_when_folded(self):
        self.edit("now.md", "folded through Entry 3", "folded through Entry 4")
        self.assertEqual(board(self.root, write=False)["stale-state"].status, "PASS")

    def test_missing_marker_fails(self):
        self.edit("now.md", "(folded through Entry 3)", "")
        self.assertIn("no marker", board(self.root, write=False)["stale-state"].message)


class TestFloors(Fixture):
    def test_empty_population_is_flipped(self):
        os.remove(os.path.join(self.root, "brain", "notes.md"))
        b = board(self.root, write=False)
        self.assertEqual(b["citation-resolves"].status, "FAIL")
        self.assertIn("certifies nothing", b["citation-resolves"].message)
        self.assertEqual(b["no-vacuous-pass"].status, "FAIL")

    def test_missing_tally_fails_not_zero(self):
        os.remove(os.path.join(self.root, "interventions.md"))
        self.assertEqual(board(self.root, write=False)["intervention-tally"].status, "FAIL")


class TestChecks(Fixture):
    def test_stated_number_drift_fails(self):
        self.edit("docs/guide.md", "tokens", "tokens; the log holds 99 entries")
        r = board(self.root, write=False)["stated-vs-measured"]
        self.assertEqual(r.status, "FAIL")
        self.assertIn("99 entries", r.message)

    def test_board_count_in_prose_fails(self):
        self.edit("docs/guide.md", "tokens.", "tokens. 12 checks passed last night.")
        self.assertIn("count of checks", board(self.root, write=False)["stated-vs-measured"].message)

    def test_dead_path_in_prompt(self):
        self.edit("tasks/nightly.md", "`now.md`", "`me/old-name.md`")
        r = board(self.root, write=False)["prompt-drift"]
        self.assertEqual(r.status, "FAIL")
        self.assertIn("me/old-name.md", r.message)

    def test_degraded_eight_nights_fails(self):
        for back in range(2, 9):
            day = (self.today - datetime.timedelta(days=back)).isoformat()
            with open(os.path.join(self.root, "state", f"nightly-{day}.json"), "w") as fh:
                json.dump({"job": "nightly", "day": day, "ended": True, "artefact": "now.md",
                           "done": {"2-sweep": {"result": "skipped", "degraded": True}}}, fh)
        self.assertEqual(board(self.root, write=False)["degraded-steps"].status, "FAIL")

    def test_ended_without_artefact_fails(self):
        self.edit(f"state/nightly-{self.today.isoformat()}.json", '"now.md"', '"missing.md"')
        self.assertIn("without missing.md", board(self.root, write=False)["degraded-steps"].message)

    def test_noted_is_not_an_outcome(self):
        self.edit("interventions.md", "| Rule |", "| Noted |")
        r = board(self.root, write=False)["intervention-tally"]
        self.assertEqual(r.status, "FAIL")
        self.assertIn("Noted", r.message)

    def test_intervene_cli_appends(self):
        with redirect_stdout(io.StringIO()):
            cli.main(["--root", self.root, "intervene", "fixed a heading", "--cost", "a turn"])
        self.assertIn("6 row(s)", board(self.root, write=False)["intervention-tally"].message)

    def test_cannot_without_date_fails(self):
        self.edit("cannots.md", "| rename files on the mount |", "| rename files on the mount | |")
        self.edit("cannots.md", "| Re-test by |", "| Re-test by | Note |")
        r = board(self.root, write=False)["cannot-list"]
        self.assertEqual(r.status, "FAIL")
        self.assertIn("no re-test date", r.message)

    def test_read_budget_growth_fails(self):
        board(self.root)
        with open(os.path.join(self.root, "now.md"), "a") as fh:
            fh.write("x" * 20_000)
        self.assertIn("grew", board(self.root, write=False)["read-budget"].message)


class TestPackage(unittest.TestCase):
    def test_toml_min_parses_the_starter(self):
        data = toml_min.loads(TOML.format(utc=10, month="2026-09"))
        self.assertEqual(data["watchman"]["utc_offset_hours"], 10)
        self.assertEqual(data["stated"]["measure"][0]["name"], "now.md")
        self.assertEqual(data["ledgers"][0]["states"][0], "Open")
        self.assertEqual(data["log"]["heading"][:3], "^##")
        try:
            import tomllib
            self.assertEqual(tomllib.loads(TOML.format(utc=10, month="2026-09")), data)
        except ImportError:
            pass

    def test_no_dashes_anywhere(self):
        top = os.path.dirname(PKG)
        for base, dirs, files in os.walk(top):
            dirs[:] = [d for d in dirs if d not in ("demo", "__pycache__", ".watchman")]
            for f in files:
                if f.endswith((".py", ".md", ".toml")):
                    with open(os.path.join(base, f), encoding="utf-8") as fh:
                        text = fh.read()
                        for dash in ("\u2014", "\u2013"):
                            self.assertNotIn(dash, text, f)

    def test_help_reads_nothing(self):
        with redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as cm:
                cli.main(["--root", "/nonexistent", "--help"])
        self.assertEqual(cm.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
