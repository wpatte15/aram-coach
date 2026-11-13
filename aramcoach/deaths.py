"""Works out why the player died, as far as the game's local data can tell.

"You died 12 times" does not say what to change. A death in a fight the team won is not a
mistake, and for a front-line champion it is often the job; a death alone against four
enemies is. For each death the game API gives who was credited with the kill, every other
kill around it, which players were dead at that moment, and the player's own health in the
seconds before. From those, each death gets one verdict:

- trade:  the team killed at least as many as it lost in that fight, counting the player.
- alone:  three or more enemies were credited and no teammate took part in the fight.
- picked: one or two enemies were credited and no teammate took part.
- short:  the fight began with the player's side already down players.
- low:    the player was below half health ten seconds before dying.
- lost:   a fight from even numbers that the team lost.

The first verdict that applies is used, in that order. In 34 recorded matches (343 deaths)
about a third were trades and under half were lost even fights.

What this cannot tell: which enemy ability did the damage, and whether the player's own
abilities landed. The local game API reports neither, so a lost even fight is as far as the
verdict goes.
"""
from __future__ import annotations

FIGHT_WINDOW = 10.0          # seconds: kills this close to a death are treated as the same fight
LOW_HEALTH = 0.5             # share of health below which starting a fight counts as starting it low

KINDS = ("trade", "alone", "picked", "short", "low", "lost")
AVOIDABLE = ("alone", "picked", "short", "low")       # the verdicts with something for the player to change

_WORDS = {
    "trade": "in fights your team won or traded evenly",
    "alone": "alone against three or more enemies",
    "picked": "caught by one or two enemies with no fight around",
    "short": "in fights that started short-handed",
    "low": "after starting a fight below half health",
    "lost": "in even fights your team lost",
    "pending": "still being decided",
}


def words(kind: str) -> str:
    """A verdict in words, such as "in even fights your team lost"."""
    return _WORDS.get(kind, kind)


def record(state: dict, health_before: float | None = None, after: float = -1.0) -> dict:
    """Measure the player's death from the snapshot in which they are first seen dead.

    health_before: the player's share of health about ten seconds earlier, or None when unknown.
    after: time of the previous recorded death, so an older kill event is not used twice.

    Returns the death as a dict. `with` and `against` count the players alive on each side
    just before the player died, the player included. `started_with` and `started_against`
    count them as the fight began: a teammate who died earlier in the same fight still counts
    there. `by` is how many enemies were credited with the kill.
    """
    mine = [k for k in state["kills"] if k["me"] and k["time"] > after]
    when = mine[-1]["time"] if mine else state["time"]
    last_death = {(k["victim_team"], k["victim"]): k["time"] for k in state["kills"]}
    # Dead in this snapshot, and their death came before the given time.
    down = lambda players, before: sum(1 for p in players
                                       if p["dead"] and last_death.get((p["team"], p["champion"]), 0.0) < before)
    allies, enemies = state["allies"], state["enemies"]
    return {
        "time": when,
        "killer": mine[-1]["killer"] if mine else "",
        "by": len(mine[-1]["credit"]) if mine else 0,
        "with": 1 + len(allies) - down(allies, when),
        "against": len(enemies) - down(enemies, when),
        "started_with": 1 + len(allies) - down(allies, when - FIGHT_WINDOW),
        "started_against": len(enemies) - down(enemies, when - FIGHT_WINDOW),
        "health": health_before,
    }


def classify(death: dict, kills: list, me: tuple, now: float) -> dict:
    """Give one recorded death its verdict from the kills around it.

    me: the player as (team, champion). now: the current game time. Until the fight window
    has passed, later kills in the same fight are still to come and the verdict is "pending".
    Returns the death with `kind`, and with `ours` and `theirs`: how many each side lost in
    the fight, the player included.
    """
    team, t = me[0], death["time"]
    near = [k for k in kills if abs(k["time"] - t) <= FIGHT_WINDOW and not (k["me"] and abs(k["time"] - t) < 5)]
    lost_mates = [k for k in near if k["victim_team"] == team]
    killed = [k for k in near if k["victim_team"] not in (team, None)]
    # A teammate took part if one died in the fight or was credited with one of its kills.
    mates_in = bool(lost_mates) or any(c[0] == team and c != me for k in killed for c in k["credit"])
    ours, theirs = 1 + len(lost_mates), len(killed)
    if now - t < FIGHT_WINDOW:
        kind = "pending"
    elif theirs >= ours:
        kind = "trade"
    elif not mates_in:
        kind = "alone" if death["by"] >= 3 else "picked"
    elif death["started_with"] < death["started_against"]:
        kind = "short"
    elif death["health"] is not None and death["health"] < LOW_HEALTH:
        kind = "low"
    else:
        kind = "lost"
    return {**death, "kind": kind, "ours": ours, "theirs": theirs}


def describe(death: dict) -> str:
    """One or two sentences about one classified death, for the panel."""
    kind, start = death["kind"], f"{death['started_with']} against {death['started_against']}"
    short = death["started_with"] < death["started_against"]
    if kind == "pending":
        return "The fight is still being decided." + (f" It started {start}." if short else "")
    if kind == "trade":
        return (f"A fair trade: your team killed {death['theirs']} and lost {death['ours']}, you included."
                + (f" It did that starting {start}." if short else ""))
    if kind == "alone":
        return f"You were in there without your team: {death['by']} enemies killed you and no teammate was in the fight."
    if kind == "picked":
        return f"{death['killer'] or 'They'} caught you with no fight going on and no teammate involved."
    if kind == "short":
        return f"That fight started {start}, and your team lost {death['ours']} for {death['theirs']}."
    if kind == "low":
        return f"You were at {round(100 * death['health'])}% health ten seconds before you died, and your team lost the fight."
    return f"Your team lost that fight {death['ours']} for {death['theirs']} from even numbers."


def rule_for(kind: str, tank: bool = False, lead: str = "") -> str:
    """One instruction that answers a verdict. lead: a front-line teammate's champion, when there is one."""
    if kind == "alone":
        if lead and not tank:
            return f"Wait for {lead} to go in first, then follow."
        return "Go in only when teammates are right beside you."
    if kind == "picked":
        return "Stay within reach of a teammate. Do not walk up or chase by yourself."
    if kind == "short":
        return "When teammates are dead, walk back toward your turret until they respawn. Hold Tab to see who is dead."
    if kind == "low":
        return "Below half health, stay behind your team and let them start the fight."
    return ""


def summarize(deaths: list, tank: bool = False, lead: str = ""):
    """Totals for a list of classified deaths, or None when there are none.

    Returns {count, one count per verdict, pending, line, last, rule, note}. `line` is the
    breakdown in words. `last` describes the most recent death. `rule` is one instruction for
    the avoidable verdict that has happened at least twice (one death is not a pattern).
    `note` counts the trades once there are two, so those deaths are not read as mistakes.
    """
    if not deaths:
        return None
    counts = {kind: sum(1 for d in deaths if d["kind"] == kind) for kind in KINDS + ("pending",)}
    n = len(deaths)
    parts = [f"{counts[kind]} {_WORDS[kind]}" for kind in KINDS + ("pending",) if counts[kind]]
    top = max(AVOIDABLE, key=lambda kind: counts[kind])           # ties go to the earlier verdict
    rule = rule_for(top, tank, lead) if counts[top] >= 2 else ""
    note = ""
    if counts["trade"] >= 2:
        note = (f"{counts['trade']} of your {n} deaths came in fights your team won or traded evenly. "
                "Those are not the ones to fix.")
    return {"count": n, **counts, "line": f"{n} death{'s' if n != 1 else ''}: " + ", ".join(parts),
            "last": describe(deaths[-1]), "rule": rule, "note": note}
