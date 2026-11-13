"""Checks for what the post-game review is given. Run: python tests/test_postgame.py

A small made-up match: no Claude calls and no game client.
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aramcoach import advisor, postgame  # noqa: E402
from aramcoach.static_data import StaticData  # noqa: E402


def player(pid, team, champion, me=False, **more):
    return {"me": me, "pid": pid, "team": team, "champion": champion, "champ_id": champion, "level": 10,
            "kda": [2, 3, 4], "damage": 1000, "taken": 2000, "healing": 0, "gold": 5000, "win": team == 100,
            "augments": [], "items": [], **more}


PLAYERS = [player(1, 100, "Zilean", me=True), player(2, 100, "Garen"), player(3, 100, "Jinx"),
           player(4, 200, "Talon"), player(5, 200, "Lux"), player(6, 200, "Sona")]


def kill(seconds, killer, victim, assists=()):
    return {"type": "CHAMPION_KILL", "timestamp": int(seconds * 1000), "killerId": killer, "victimId": victim,
            "assistingParticipantIds": list(assists)}


def frame(seconds, events, gold):
    return {"timestamp": int(seconds * 1000), "events": events,
            "participantFrames": {str(pid): {"participantId": pid, "totalGold": g} for pid, g in gold.items()}}


TIMELINE = {"frames": [
    frame(0, [], {pid: 500 for pid in range(1, 7)}),
    frame(60, [kill(40, 2, 4, [1]), kill(48, 5, 2, [6])], {1: 900, 2: 1200, 3: 900, 4: 800, 5: 1100, 6: 800}),
    frame(120, [kill(100, 4, 3), kill(104, 4, 1, [5, 6]), kill(110, 3, 5),
                {"type": "BUILDING_KILL", "timestamp": 115000, "teamId": 100, "buildingType": "TOWER_BUILDING"}],
          {1: 1500, 2: 1900, 3: 1500, 4: 2400, 5: 1700, 6: 1500}),
    frame(180, [kill(150, 2, 6, [3]), kill(175, 2, 4)], {pid: 2500 for pid in range(1, 7)}),
]}


def test_fights():
    fights = postgame.fights(TIMELINE, PLAYERS)
    assert [(f["start"], f["end"]) for f in fights] == [(40.0, 48.0), (100.0, 110.0), (150.0, 150.0), (175.0, 175.0)]
    first, second, third, fourth = fights
    assert first["killed"] == ["Talon"] and first["lost"] == ["Garen"]
    assert first["me"]["credits"] == 1 and not first["me"]["died"] and first["me"]["since_death"] is None
    # The player died second in the second fight, to Talon with two helpers.
    assert second["lost"] == ["Jinx", "Zilean"] and second["killed"] == ["Lux"]
    assert second["me"] == {"credits": 0, "died": True, "order": 1, "killer": "Talon", "helpers": ["Lux", "Sona"],
                            "since_death": None}
    # A fight the player had no part in, 46 seconds after dying.
    assert third["me"]["credits"] == 0 and third["me"]["since_death"] == 46
    assert fourth["me"]["since_death"] == 71
    lines = [advisor._fight_line(f) for f in fights]
    assert lines[0] == "  0:40-0:48  1 for 1 | killed Talon | lost Garen | you: in on 1 of 1 kills", lines[0]
    assert "lost Jinx, YOU" in lines[1] and "died after 1 teammate, to Talon with Lux, Sona" in lines[1], lines[1]
    assert lines[2].endswith("you: no part, 46s after your last death"), lines[2]


def test_gold_and_structures():
    assert postgame.gold_lead(TIMELINE, PLAYERS) == [{"time": 60, "lead": 300}, {"time": 120, "lead": -700},
                                                     {"time": 180, "lead": 0}]
    # The turret belonged to team 100, the player's own team, so the enemy took it.
    assert postgame.structures(TIMELINE, PLAYERS) == [{"time": 115, "ours": False, "kind": "turret"}]
    assert postgame.fights({"frames": []}, PLAYERS) == [] and postgame.gold_lead({}, PLAYERS) == []


def test_purchases_and_request(sd):
    snapshot = lambda t, items: {"gameData": {"gameTime": t}, "allPlayers": [
        {"team": "ORDER", "championName": "Zilean", "items": [{"itemID": i} for i in items]},
        {"team": "CHAOS", "championName": "Talon", "items": [{"itemID": 3142}]}]}
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        (folder / "t00030.json").write_text(json.dumps(snapshot(30, [1052])), encoding="utf-8")       # a component
        (folder / "t00090.json").write_text(json.dumps(snapshot(90, [3158, 1052])), encoding="utf-8")
        (folder / "t00150.json").write_text(json.dumps(snapshot(150, [3158, 3110])), encoding="utf-8")
        (folder / "timeline.json").write_text("{}", encoding="utf-8")                                 # not a snapshot
        bought = postgame.purchases(sd, folder)
        assert bought[(100, "Zilean")] == [{"time": 90, "item": "Ionian Boots of Lucidity"},
                                           {"time": 150, "item": "Frozen Heart"}], bought
        assert bought[(200, "Talon")] == [{"time": 30, "item": "Youmuu's Ghostblade"}]
        record = {"plans": [{"time": 0, "trigger": "game start", "changed": "", "dropped": [],
                             "build": ["Ionian Boots of Lucidity", "Frozen Heart"]},
                            {"time": 104, "trigger": "the player just died", "changed": "", "dropped": [],
                             "build": ["Ionian Boots of Lucidity", "Frozen Heart"]},
                            {"time": 160, "trigger": "the player took an augment", "changed": "Rylai's now second.",
                             "dropped": ["Moonstone Renewer"], "build": ["Ionian Boots of Lucidity", "Rylai's Crystal Scepter"]}],
                  "offers": [{"time": 100, "names": ["Deft", "Recursion"], "pick": "Recursion", "why": "More bombs.",
                              "taken": "Recursion", "assumed": True}],
                  "death_rows": [{"time": 104, "verdict": "in even fights your team lost", "killer": "Talon", "by": 3,
                                  "health": 0.4, "ours": 2, "theirs": 1, "started_with": 3, "started_against": 3}],
                  "focus": "Stay behind your tank."}
        summary = {"game_id": 1, "mode": "KIWI", "minutes": 3.0, "players": PLAYERS}
        told = postgame.story(sd, summary, TIMELINE, folder, record)
    assert told["purchases"]["Zilean"][1]["item"] == "Frozen Heart" and told["purchases"]["Garen"] == []
    text = advisor.render_debrief(summary, "", None, told, sd)
    for part in (
            "YOU: Zilean level 10 | K/D/A 2/3/4 | in on 100% of team kills | damage to champions 1000 (33% of team)",
            "GOLD LEAD OF THE PLAYER'S TEAM, minute by minute: 1:00 +300, 2:00 -700, 3:00 +0",
            "STRUCTURES DESTROYED: 1:55 the enemy took a turret",
            "YOU: Zilean: Ionian Boots of Lucidity 1:30, Frozen Heart 2:30",
            "  1:44 in even fights your team lost: team lost 2 and killed 1; the fight began 3 against 3; health ten "
            "seconds earlier 40%; killed by Talon and 2 more",
            "  0:00 plan (game start): Ionian Boots of Lucidity > Frozen Heart",
            "  2:40 plan (the player took an augment): Ionian Boots of Lucidity > Rylai's Crystal Scepter | the coach's "
            "note: Rylai's now second. | removed by the item checks: Moonstone Renewer",
            "  3 plans in all",
            "  1:40 augment offer: Deft, Recursion | the coach picked Recursion because: More bombs. | taken: Recursion "
            "(assumed, the player did not say)",
            "THE FOCUS THE LAST REVIEW GAVE THE PLAYER FOR THIS MATCH: Stay behind your tank.",
            "ITEM CHECKS FOR THE PLAYER'S CHAMPION", "Zilean (you): Passive Time In A Bottle"):
        assert part in text, f"missing from the review request: {part}\n{text[:3000]}"
    assert text.count(" plan (") == 2, "a plan that repeats the build above it is not listed again"
    # On a champion that does not build defense the review is told the player's instruction, so that it does not call a
    # build without armor a mistake. Zilean is such a champion. What the player typed to the coach is in the record too.
    assert "THE PLAYER'S INSTRUCTION FOR THIS KIND OF CHAMPION: Zilean" in text
    typed = dict(told, told=[{"time": 95, "text": "no defensive items please"}])
    assert '  1:35 the player typed to the coach: "no defensive items please"' in advisor.render_debrief(summary, "", None, typed, sd)
    # The coach assumes its pick was taken. When the game's record says the player never held it, the review is told
    # so: one real review blamed a build on an augment the player had rerolled away.
    ended_with = lambda *names: dict(summary, players=[dict(p, augments=list(names)) if p["me"] else p for p in PLAYERS])
    wrong = advisor.render_debrief(ended_with("Deft"), "", None, told, sd)
    assert "taken: NOT Recursion. The game's record shows the player never held it." in wrong and "(assumed, the player" not in wrong
    assert "taken: Recursion (assumed, the player did not say)" in advisor.render_debrief(ended_with("Recursion"), "", None, told, sd)
    # Enemy healing is set against what is usual in the player's other recorded matches.
    told["healing"] = {"per_minute": 2070, "usual": 1917, "matches": 12}
    assert ("ENEMY HEALING: their team healed 2070 a minute. In the player's other 12 recorded matches the middle value "
            "was 1917 a minute, so this was about the usual amount.") in advisor.render_debrief(summary, "", None, told, sd)
    told["healing"] = {"per_minute": 3240, "usual": 1917, "matches": 12}
    assert "well above the usual amount" in advisor.render_debrief(summary, "", None, told, sd)
    with_heals = {"minutes": 10.0, "players": [dict(PLAYERS[0], healing=100), dict(PLAYERS[3], healing=4000),
                                               dict(PLAYERS[4], healing=6000)]}
    measured = postgame.enemy_healing(with_heals)
    assert measured["per_minute"] == 1000 and (measured["usual"] is None or measured["matches"] >= 5)
    assert postgame.enemy_healing({"minutes": 10.0, "players": [dict(PLAYERS[3])]}) is None
    # A record saved before the review took all of this in still renders.
    old = {"game_id": 1, "mode": "ARAM", "minutes": 12.0, "players": [
        {k: v for k, v in p.items() if k != "pid"} for p in PLAYERS]}
    assert "YOU: Zilean" in advisor.render_debrief(old, "", None)


def test_the_player_is_found_without_the_account_id():
    table = lambda: {"players": [dict(p, me=False) for p in PLAYERS]}
    summary = table()
    assert postgame.mark_me(summary, {"champ_id": "Zilean", "team": "ORDER"})
    assert [p["champion"] for p in summary["players"] if p["me"]] == ["Zilean"]
    # The same champion on the other team is somebody else.
    assert not postgame.mark_me(table(), {"champ_id": "Zilean", "team": "CHAOS"})
    assert not postgame.mark_me(table(), None)
    # A player the account id already found is left alone.
    summary = {"players": [dict(p) for p in PLAYERS]}
    assert postgame.mark_me(summary, {"champ_id": "Talon", "team": "CHAOS"})
    assert [p["champion"] for p in summary["players"] if p["me"]] == ["Zilean"]
    # The client fails to answer twice, then answers.
    answers = iter([None, None, "abc"])
    real_puuid, real_sleep = postgame.lcu.my_puuid, postgame.time.sleep
    postgame.lcu.my_puuid, postgame.time.sleep = (lambda: next(answers)), (lambda seconds: None)
    try:
        assert postgame._my_puuid() == "abc"
        postgame.lcu.my_puuid = lambda: None
        assert postgame._my_puuid(tries=3) is None
    finally:
        postgame.lcu.my_puuid, postgame.time.sleep = real_puuid, real_sleep


if __name__ == "__main__":
    test_fights()
    test_the_player_is_found_without_the_account_id()
    test_gold_and_structures()
    test_purchases_and_request(StaticData())
    print("post-game checks ok")
