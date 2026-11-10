"""Works out how the player died, from who was alive and from the game's kill events.

The game API reports every kill with its time, and whether each player is dead right now.
That is enough to say, for each of the player's deaths:

- outnumbered: their side had fewer players alive than the other side when they died;
- first: nobody on their team had died in that fight before them;
- alone: nobody on either team died within the fight window before or after;
- soon: they had been alive for only a short time since respawning.

A death can be several of these. Eight recorded matches (80 deaths) had 29 outnumbered
deaths and 38 that were alone or first, which is why the coach reports them: "you died 12
times" does not say what to change, and "5 of them were 3 against 5" does.
"""
from __future__ import annotations

FIGHT_WINDOW = 12.0          # seconds: kills this close together are treated as one fight
SOON_AFTER_RESPAWN = 35.0    # dying this soon after respawning means walking straight back in

KINDS = ("outnumbered", "alone", "soon", "first")       # in the order used to label one death

_RULES = {
    "outnumbered": "When your team has fewer players alive than theirs, walk back toward your turret until "
                   "they respawn. Hold Tab to see who is dead.",
    "alone": "Stay within reach of a teammate. Do not chase or push by yourself.",
    "soon": "After respawning, wait for your team before walking back into the fight.",
    "first": "Let a teammate walk in first, then follow.",
    "first_tank": "Going in first is your job. Go in only when teammates are close enough to follow you.",
}


def record(state: dict, alive_since: float | None, after: float = -1.0) -> dict:
    """Measure the player's death from the snapshot in which they are first seen dead.

    alive_since: game time at which the player last came back to life, or None when the coach
      did not see it (it was started in the middle of a match).
    after: time of the previous recorded death, so an older kill event is not used twice.
    Returns {time, killer, with, against, alive_for}. `with` counts the player's side
    including the player; `against` counts the enemies alive. Both are as they stood just
    before the player died.
    """
    mine = [k for k in state["kills"] if k["me"] and k["time"] > after]
    when = mine[-1]["time"] if mine else state["time"]
    last_death = {(k["victim_team"], k["victim"]): k["time"] for k in state["kills"]}
    # Dead in this snapshot, and their death came before the player's.
    down = lambda players: sum(1 for p in players
                               if p["dead"] and last_death.get((p["team"], p["champion"]), 0.0) < when)
    return {
        "time": when,
        "killer": mine[-1]["killer"] if mine else "",
        "with": 1 + len(state["allies"]) - down(state["allies"]),
        "against": len(state["enemies"]) - down(state["enemies"]),
        "alive_for": None if alive_since is None else max(0.0, when - alive_since),
    }


def classify(death: dict, kills: list, my_team, now: float) -> dict:
    """Add what the kill events say about one recorded death. Returns the death with a flag per kind and a label."""
    t = death["time"]
    near = [k for k in kills if abs(k["time"] - t) <= FIGHT_WINDOW and not (k["me"] and abs(k["time"] - t) < 5)]
    allies_before = any(k["victim_team"] == my_team and k["time"] < t for k in near)
    settled = now - t >= FIGHT_WINDOW            # until then, later kills in the same fight are still to come
    flags = {
        "outnumbered": death["with"] < death["against"],
        "alone": settled and not near,
        "soon": death["alive_for"] is not None and death["alive_for"] < SOON_AFTER_RESPAWN,
    }
    flags["first"] = not allies_before and not flags["alone"]
    return {**death, **flags, "kind": next((k for k in KINDS if flags[k]), "fight")}


def describe(death: dict) -> str:
    """One sentence about one classified death, for the panel."""
    if death["kind"] == "outnumbered":
        return f"You died fighting {death['with']} against {death['against']}."
    if death["kind"] == "alone":
        return "You died alone: nobody else died within 12 seconds before or after."
    if death["kind"] == "soon":
        return f"You died {int(death['alive_for'])} seconds after respawning."
    if death["kind"] == "first":
        return "You were the first on your team to die in that fight."
    return f"You died in a team fight, {death['with']} against {death['against']}."


def summarize(deaths: list, tank: bool = False):
    """Totals for a list of classified deaths, or None when there are none.

    Returns {count, outnumbered, alone, soon, first, line, last, rule}. `line` is the breakdown
    in words, `last` describes the most recent death, and `rule` is one instruction for the
    kind that has happened at least twice (empty before that: one death is not a pattern).
    tank: the player's champion is a tank, for whom dying first is often the job.
    """
    if not deaths:
        return None
    counts = {kind: sum(1 for d in deaths if d[kind]) for kind in KINDS}
    words = {"outnumbered": "while outnumbered", "alone": "alone", "soon": "within 35 seconds of respawning",
             "first": "as the first on your team to die in the fight"}
    parts = [f"{counts[kind]} {words[kind]}" for kind in KINDS if counts[kind]]
    n = len(deaths)
    top = max(KINDS, key=lambda kind: counts[kind])             # ties go to the earlier, more specific kind
    rule = ""
    if counts[top] >= 2:
        rule = _RULES["first_tank" if top == "first" and tank else top]
    return {"count": n, **counts,
            "line": f"{n} death{'s' if n != 1 else ''}" + (": " + ", ".join(parts) if parts else ""),
            "last": describe(deaths[-1]), "rule": rule}
