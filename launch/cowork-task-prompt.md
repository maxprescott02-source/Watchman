# Run watchman from inside Claude Cowork, no cron at all

*For the operator who schedules with Cowork's own task UI and will not touch a terminal twice. Paste this as a new scheduled task, daily, at the time you wake up. Replace FOLDER with the folder your agents work over. It needs watchman on the machine once: `pip install .` from the repo, or the repo cloned anywhere.*

---

**Task name:** Watchman morning check

**Schedule:** daily, 05:30 (or thirty minutes after your last nightly agent finishes)

**Prompt:**

Run this shell command and capture its output:

    python3 -m watchman --root "FOLDER"

Then read FOLDER/WATCHMAN.md.

If its first section lists one or more incidents, send me an email with the subject "Watchman: N incidents in FOLDER" and the body being WATCHMAN.md exactly as written, nothing added. If it says "Healthy: nothing needs you", send nothing and finish.

Never edit any file in FOLDER. Never re-run the jobs it names. Your only job is to run the check and hand me the file when it has something in it.

---

Why this exists: the people who filed anthropics/claude-code #55378 and #47899 found out their scheduled tasks had stopped weeks after the fact, and every safety net they had was on the same scheduler. This task is still on that scheduler, so it is not independent; it is the version for someone who will not set up cron. The independent version is `python3 -m watchman install FOLDER`, which schedules through launchd or cron. Run both if you can: if the Cowork task goes quiet, the cron one still writes WATCHMAN.md, and watchman's own `expected-run` will name the Cowork task as the thing that stopped.
