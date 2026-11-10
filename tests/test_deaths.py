"""Checks the death breakdown against small hand-made fights.

Run with: .venv\\Scripts\\python.exe tests\\test_deaths.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aramcoach import deaths  # noqa: E402

ALLIES = ["Lux", "Jinx", "Leona", "Ahri"]
ENEMIES = ["Garen", "Zed", "Sona", "Vayne", "Malphite"]


def kill(time, victim, team, me=False, killer="Garen"):
    return {"time": time, "victim": victim, "victim_team": team, "killer": killer, "me": me}


def snapshot(time, kills, dead=()):
    """A game state with the named champions dead. Kills must include the player's own death."""
    player = lambda name, team: {"champion": name, "team": team, "dead": name in dead}
    return {"time": time, "kills": kills, "me": {"champion": "Thresh", "team": "ORDER", "dead": True},
            "allies": [player(n, "ORDER") for n in ALLIES], "enemies": [player(n, "CHAOS") for n in ENEMIES]}


def test_outnumbered_counts_only_players_who_died_first():
    kills = [kill(100, "Lux", "ORDER"), kill(104, "Jinx", "ORDER"), kill(110, "Thresh", "ORDER", me=True),
             kill(110.5, "Leona", "ORDER")]
    state = snapshot(111, kills, dead={"Lux", "Jinx", "Leona"})         # Leona died after the player
    death = deaths.record(state, alive_since=40.0)
    assert (death["with"], death["against"]) == (3, 5), death
    assert death["time"] == 110 and death["killer"] == "Garen" and death["alive_for"] == 70.0
    row = deaths.classify(death, kills, "ORDER", now=111)
    assert row["outnumbered"] and not row["first"] and row["kind"] == "outnumbered"
    assert deaths.describe(row) == "You died fighting 3 against 5."


def test_first_to_die_in_a_fight():
    kills = [kill(200, "Thresh", "ORDER", me=True), kill(203, "Lux", "ORDER"), kill(205, "Zed", "CHAOS")]
    death = deaths.record(snapshot(200.6, kills[:1]), alive_since=100.0)
    assert (death["with"], death["against"]) == (5, 5)
    row = deaths.classify(death, kills, "ORDER", now=230)
    assert row["first"] and not row["alone"] and not row["outnumbered"] and row["kind"] == "first"


def test_alone_needs_the_fight_window_to_pass():
    kills = [kill(300, "Thresh", "ORDER", me=True)]
    death = deaths.record(snapshot(300.5, kills), alive_since=200.0)
    early = deaths.classify(death, kills, "ORDER", now=305)
    assert not early["alone"] and early["kind"] == "first", "a fight may still follow within the window"
    late = deaths.classify(death, kills, "ORDER", now=320)
    assert late["alone"] and not late["first"] and late["kind"] == "alone"


def test_soon_after_respawning_and_unknown_respawn():
    kills = [kill(400, "Thresh", "ORDER", me=True), kill(403, "Zed", "CHAOS")]      # a fight was going on
    death = deaths.record(snapshot(400.5, kills[:1]), alive_since=380.0)
    row = deaths.classify(death, kills, "ORDER", now=420)
    assert row["soon"] and row["kind"] == "soon" and deaths.describe(row) == "You died 20 seconds after respawning."
    unknown = deaths.classify(deaths.record(snapshot(400.5, kills[:1]), alive_since=None), kills, "ORDER", now=420)
    assert not unknown["soon"], "without a seen respawn the life length is unknown"


def test_a_second_death_does_not_reuse_the_first_kill_event():
    kills = [kill(100, "Thresh", "ORDER", me=True)]
    second = deaths.record(snapshot(160, kills), alive_since=130.0, after=100)
    assert second["time"] == 160 and second["killer"] == "", "the new death's event has not arrived yet"


def test_summary_counts_and_rule():
    assert deaths.summarize([]) is None
    base = {"time": 0, "killer": "", "with": 3, "against": 5, "alive_for": 60.0}
    rows = [{**base, "outnumbered": True, "alone": False, "soon": False, "first": False, "kind": "outnumbered"},
            {**base, "outnumbered": True, "alone": False, "soon": True, "first": True, "kind": "outnumbered"},
            {**base, "with": 5, "outnumbered": False, "alone": False, "soon": False, "first": True, "kind": "first"}]
    s = deaths.summarize(rows)
    assert s["count"] == 3 and s["outnumbered"] == 2 and s["first"] == 2 and s["soon"] == 1
    assert s["line"] == ("3 deaths: 2 while outnumbered, 1 within 35 seconds of respawning, "
                         "2 as the first on your team to die in the fight")
    assert s["rule"].startswith("When your team has fewer players alive"), "a tie goes to the more specific kind"
    assert s["last"] == "You were the first on your team to die in that fight."
    assert deaths.summarize(rows[:1])["rule"] == "", "one death is not a pattern"
    firsts = [rows[2], rows[2]]
    assert deaths.summarize(firsts)["rule"].startswith("Let a teammate walk in first")
    assert deaths.summarize(firsts, tank=True)["rule"].startswith("Going in first is your job")


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_")]
    for test_name, fn in tests:
        fn()
        print("ok  ", test_name)
    print(f"{len(tests)} passed")
