"""A check over zero items has tested that nothing is wrong with nothing; every check declares a floor and a pass below it is a fail."""
# Descends from the brain-ops audit of 2026-08-14, which found four assertions
# passing over empty input, and assertion 1's "THE FLOOR FOR 1, 2 AND 3 AT ONCE".
from ._util import Result

NAME = "no-vacuous-pass"


def enforce(results):
    """Flip any PASS whose population is under its floor. Called by the runner."""
    for r in results:
        if r.status == "PASS" and (r.population is None or r.population < r.floor):
            r.status = "FAIL"
            r.message = (f"passed over {r.population} item(s), floor is {r.floor}. "
                         f"That certifies nothing. Original: {r.message}")
    return results


def audit(results):
    """The board line: did every check declare its floor, and did any get flipped."""
    undeclared = [r.check for r in results if r.population is None or r.floor is None]
    flipped = [r.check for r in results if "That certifies nothing" in r.message]
    pop = len(results)
    if undeclared:
        return Result(NAME, "FAIL", f"{len(undeclared)} check(s) declared no floor: "
                      f"{undeclared}", pop, 1)
    if flipped:
        return Result(NAME, "FAIL", f"{len(flipped)} check(s) passed over fewer items "
                      f"than their floor and were flipped: {flipped}", pop, 1)
    return Result(NAME, "PASS", f"{pop} checks each declared a floor and met it", pop, 1)
