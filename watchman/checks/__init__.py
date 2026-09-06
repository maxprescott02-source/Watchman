"""The register. A check is on when its config section exists; the order here is the board order."""
from . import (absence, append_only_log, cannot_list, citation_resolves, closed_sets,
               degraded_steps, intervention_tally, prompt_drift, read_budget,
               stale_state, stated_vs_measured)

# (config section, module). read_budget and heartbeat are wired by the runner
# because they exchange state with the previous run.
REGISTER = [
    ("stale_state", stale_state),
    ("stated", stated_vs_measured),
    ("degraded", degraded_steps),
    ("prompts", prompt_drift),
    ("ledgers", closed_sets),
    ("interventions", intervention_tally),
    ("absence", absence),
    ("log", append_only_log),
    ("citations", citation_resolves),
    ("cannots", cannot_list),
    ("read_budget", read_budget),
]
