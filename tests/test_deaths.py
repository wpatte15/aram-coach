"""Checks the death verdicts against small hand-made fights.

Run with: .venv\\Scripts\\python.exe tests\\test_deaths.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aramcoach import deaths  # noqa: E402

ALLIES = ["Lux", "Jinx", "Leona", "Ahri"]
ENEMIES = ["Garen", "Zed", "Sona", "Vayne", "Malphite"]
ME = ("ORDER", "Thresh")


def kill(time, victim, credit=(), me=False):
    """A kill event. credit: the champions credited with it, killer first."""
    team = "ORDER" if victim in ALLIES or me else "CHAOS"
    other = "CHAOS" if team == "ORDER" else "ORDER"
    return {"time": time, "victim": victim, "victim_team": team, "killer": credit[0] if credit else "",
            "credit": [(other, c) for c in credit], "me": me}


def died(time, credit=("Garen",)):
    return kill(time, "Thresh", credit, me=True)


def snapshot(time, kills, dead=()):
    """A game state in which the named champions are dead."""
    player = lambda name, team: {"champion": name, "team": team, "dead": name in dead}
    return {"time": time, "kills": kills, "me": {"champion": "Thresh", "team": "ORDER", "dead": True},
            "allies": [player(n, "ORDER") for n in ALLIES], "enemies": [player(n, "CHAOS") for n in ENEMIES]}


def verdict(kills, at, now, dead=(), health=None, seen=None):
    """Record the player's death at `at` and classify it at `now`. seen: the kills known when the player died."""
    death = deaths.record(snapshot(at + 0.5, kills if seen is None else seen, dead), health)
    return deaths.classify(death, kills, ME, now)


def test_a_fight_the_team_won_is_a_trade():
    kills = [died(200, ("Garen", "Zed")), kill(203, "Zed", ("Jinx", "Lux")), kill(205, "Garen", ("Jinx",)),
             kill(206, "Lux", ("Vayne",))]
    row = verdict(kills, 200, now=230, seen=kills[:1])
    assert row["kind"] == "trade" and (row["ours"], row["theirs"]) == (2, 2), row
    assert deaths.describe(row) == "A fair trade: your team killed 2 and lost 2, you included."


def test_alone_against_several():
    kills = [died(300, ("Garen", "Zed", "Sona", "Vayne"))]
    row = verdict(kills, 300, now=320)
    assert row["kind"] == "alone" and row["by"] == 4
    assert deaths.describe(row) == ("You were in there without your team: 4 enemies killed you and no teammate "
                                    "was in the fight.")


def test_picked_off_by_one_enemy():
    kills = [kill(350, "Lux", ("Zed",)), died(400, ("Vayne",))]          # the earlier death is outside the fight
    row = verdict(kills, 400, now=420)
    assert row["kind"] == "picked" and deaths.describe(row).startswith("Vayne caught you with no fight going on")


def test_the_verdict_waits_for_the_fight_to_end():
    kills = [died(300, ("Garen", "Zed", "Sona"))]
    early = verdict(kills, 300, now=305)
    assert early["kind"] == "pending" and deaths.describe(early) == "The fight is still being decided."
    late = kills + [kill(306, "Garen", ("Jinx",)), kill(307, "Zed", ("Jinx", "Lux"))]
    assert verdict(late, 300, now=312, seen=kills)["kind"] == "trade", "kills after the death still count for the fight"


def test_a_fight_that_started_short_handed():
    # Lux and Jinx died half a minute earlier and are still dead. Leona dies in this fight, before the player.
    kills = [kill(70, "Lux", ("Zed",)), kill(72, "Jinx", ("Zed",)), kill(96, "Leona", ("Garen",)), died(100)]
    row = verdict(kills, 100, now=120, dead={"Lux", "Jinx", "Leona"})
    assert (row["started_with"], row["started_against"]) == (3, 5), "Leona was alive when the fight began"
    assert (row["with"], row["against"]) == (2, 5)
    assert row["kind"] == "short" and deaths.describe(row) == "That fight started 3 against 5, and your team lost 2 for 0."


def test_a_teammate_who_dies_in_the_fight_does_not_make_it_short_handed():
    kills = [kill(96, "Leona", ("Garen",)), died(100)]
    row = verdict(kills, 100, now=120, dead={"Leona"})
    assert (row["started_with"], row["started_against"]) == (5, 5) and row["kind"] == "lost"
    assert deaths.describe(row) == "Your team lost that fight 2 for 0 from even numbers."


def test_starting_a_fight_at_low_health():
    kills = [kill(96, "Leona", ("Garen",)), died(100)]
    row = verdict(kills, 100, now=120, dead={"Leona"}, health=0.34)
    assert row["kind"] == "low"
    assert deaths.describe(row) == "You were at 34% health ten seconds before you died, and your team lost the fight."
    healthy = verdict(kills, 100, now=120, dead={"Leona"}, health=0.8)
    assert healthy["kind"] == "lost"


def test_a_teammate_credited_with_a_kill_counts_as_being_in_the_fight():
    kills = [died(100, ("Garen", "Zed", "Sona")), kill(104, "Sona", ("Ahri",)), kill(105, "Lux", ("Zed",)),
             kill(106, "Jinx", ("Zed",))]
    row = verdict(kills, 100, now=120, seen=kills[:1])
    assert row["kind"] == "lost" and (row["ours"], row["theirs"]) == (3, 1), "Ahri was there, so it was not alone"


def test_a_second_death_does_not_reuse_the_first_kill_event():
    kills = [died(100)]
    second = deaths.record(snapshot(160, kills), None, after=100)
    assert second["time"] == 160 and second["killer"] == "" and second["by"] == 0, "its own event has not arrived yet"


def test_summary_counts_rule_and_note():
    assert deaths.summarize([]) is None
    row = lambda kind: {"kind": kind, "killer": "Zed", "by": 3, "ours": 2, "theirs": 0, "health": 0.3,
                        "started_with": 3, "started_against": 5}
    s = deaths.summarize([row("trade"), row("alone"), row("alone"), row("lost")], lead="Leona")
    assert s["count"] == 4 and s["alone"] == 2 and s["trade"] == 1 and s["lost"] == 1 and s["short"] == 0
    assert s["line"] == ("4 deaths: 1 in fights your team won or traded evenly, 2 alone against three or more enemies, "
                         "1 in even fights your team lost")
    assert s["rule"] == "Wait for Leona to go in first, then follow." and s["note"] == ""
    assert deaths.summarize([row("alone"), row("alone")], tank=True, lead="Leona")["rule"] == \
        "Go in only when teammates are right beside you.", "a front-line player is the one who goes in first"
    assert deaths.summarize([row("alone")])["rule"] == "", "one death is not a pattern"
    assert deaths.summarize([row("lost"), row("lost"), row("lost")])["rule"] == "", "a lost even fight has no local rule"
    good = deaths.summarize([row("trade"), row("trade"), row("short")])
    assert good["rule"] == "" and good["note"].startswith("2 of your 3 deaths came in fights your team won")
    short = deaths.summarize([row("short"), row("short"), row("low"), row("low")])
    assert short["rule"].startswith("When teammates are dead"), "a tie goes to the earlier verdict"


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_")]
    for test_name, fn in tests:
        fn()
        print("ok  ", test_name)
    print(f"{len(tests)} passed")
