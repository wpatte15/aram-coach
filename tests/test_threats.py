"""Checks for the estimate of what kind of damage is killing the player. Run: python tests/test_threats.py

Uses the game data cached on disk and makes no Claude calls.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aramcoach import advisor, config, threats  # noqa: E402
from aramcoach.static_data import StaticData  # noqa: E402

config.player_profile = lambda: "I am new to the game."        # no favourites, item buttons allowed


def item(sd, name, slot=0):
    found = sd.find_item(name) or next(it for it in sd.items.values() if it["name"] == name)
    return {"id": found["id"], "name": found["name"], "slot": slot, "gold": found["total"], "count": 1}


def player(sd, champion, items=()):
    cid = sd.champ_id(champion)
    held = [item(sd, n, slot) for slot, n in enumerate(items)]
    return {"champion": sd.champions[cid]["name"], "champ_id": cid, "items": held, "item_gold": sum(i["gold"] for i in held),
            "tags": sd.champions[cid]["tags"]}


def ornn_game(sd, mine=("Heartsteel", "Mercury's Treads")):
    """A real match: a front-line champion against a team led by a crit Kalista."""
    me = player(sd, "Ornn", mine)
    me.update(gold=600, stats={"armor": 90, "magicResist": 86, "maxHealth": 5187})
    enemies = [player(sd, "Kalista", ("The Collector", "Infinity Edge")), player(sd, "Veigar", ("Luden's Echo", "Rabadon's Deathcap")),
               player(sd, "Shen", ("Heartsteel",)), player(sd, "Jarvan IV", ("Sundered Sky",)), player(sd, "Nautilus", ("Heartsteel",))]
    killed = {"Kalista": {"kills": 4, "assists": 1}, "Veigar": {"kills": 1, "assists": 4},
              "Jarvan IV": {"kills": 0, "assists": 5}, "Shen": {"kills": 0, "assists": 4}, "Nautilus": {"kills": 1, "assists": 4}}
    return {"me": me, "allies": [player(sd, "Caitlyn"), player(sd, "Milio")], "enemies": enemies, "killed_me": killed,
            "deaths": {"count": 6, "trade": 1}, "item_ids": []}


def test_kinds(sd):
    assert threats.physical_share(sd, player(sd, "Kalista", ("The Collector", "Infinity Edge"))) == 0.88
    assert threats.physical_share(sd, player(sd, "Veigar", ("Luden's Echo", "Rabadon's Deathcap"))) == 0.08
    assert threats.physical_share(sd, player(sd, "Kalista")) == 0.8            # no items yet: her usual kind
    assert threats.physical_share(sd, player(sd, "Veigar")) == 0.2
    assert threats.physical_share(sd, player(sd, "Nautilus", ("Heartsteel",))) in (0.35, 0.5)   # a tank deals both
    # Items outweigh the usual kind: Akali built for ability power.
    assert threats.damage_kind(sd, player(sd, "Akali", ("Riftmaker", "Rabadon's Deathcap"))) == "magic"
    assert threats.damage_kind(sd, player(sd, "Jhin", ("The Collector", "Infinity Edge"))) == "physical"


def test_mix(sd):
    state = ornn_game(sd)
    back, front = threats.mix(sd, state), threats.mix(sd, state, frontline=True)
    assert abs(front["aimed"] - back["aimed"] - threats.FRONTLINE_BIAS) < 1e-9
    assert 0.5 < back["share"] < 0.7 and front["side"] == "physical", (back, front)
    assert [r["champion"] for r in front["rows"]][0] == "Kalista" and front["rows"][0]["kind"] == "physical"
    # Before anyone has died twice the kills are too few to count.
    early = dict(state, killed_me={"Veigar": {"kills": 1, "assists": 0}})
    assert threats.mix(sd, early)["basis"] == "the enemies' items"
    # No items anywhere: a head count of the champions.
    bare = dict(state, enemies=[player(sd, c) for c in ("Kalista", "Veigar")], killed_me={})
    assert threats.mix(sd, bare)["basis"] == "the enemy champions" and threats.mix(sd, bare)["aimed"] == 0.5
    assert threats.mix(sd, dict(state, enemies=[])) is None
    # A close call stays a mix. Who lands the killing blows does not decide it: over the recorded matches that
    # rule made every wrong call there was.
    close = dict(state, enemies=[player(sd, "Kalista", ("The Collector",)), player(sd, "Veigar", ("Luden's Echo", "Rabadon's Deathcap"))],
                 killed_me={"Kalista": {"kills": 4, "assists": 0}, "Veigar": {"kills": 0, "assists": 4}})
    found = threats.mix(sd, close)
    assert found["side"] == "mixed" and "killing blows" not in found["basis"], found


def test_own_resistances(sd):
    """The player's own armor and magic resist decide what gets through.

    From a real match: a Malphite with 463 armor and 70 magic resist against two attackers, two mages and a
    Volibear. The coach said 60% physical. The post-game record measured 32%.
    """
    enemies = [player(sd, "Caitlyn", ("Infinity Edge", "The Collector")), player(sd, "Rengar", ("Infinity Edge", "The Collector")),
               player(sd, "Taliyah", ("Seraph's Embrace", "Stormsurge")), player(sd, "Zilean", ("Imperial Mandate", "Shadowflame")),
               player(sd, "Volibear", ("Heartsteel", "Unending Despair"))]
    me = player(sd, "Malphite", ("Sunfire Aegis", "Thornmail", "Randuin's Omen"))
    me.update(level=15, gold=500)
    state = {"me": me, "allies": [], "enemies": enemies, "killed_me": {}, "item_ids": []}
    bare = threats.mix(sd, state, True)
    assert bare["share"] == bare["aimed"] and bare["side"] != "magic", "without the player's stats the estimate is what is aimed at them"
    me["stats"] = {"armor": 463, "magicResist": 70, "maxHealth": 3392}
    found = threats.mix(sd, state, True)
    assert found["aimed"] == bare["aimed"] and found["share"] < found["aimed"] - 0.15, found
    assert found["side"] == "magic" and found["share"] < 0.4, found
    # The other way round: stacked magic resist lets the physical damage through.
    me["stats"] = {"armor": 80, "magicResist": 300, "maxHealth": 3392}
    assert threats.mix(sd, state, True)["share"] > bare["aimed"] + 0.15
    # A player with only their champion's own resistances takes the split that was aimed at them.
    alone = threats.own_resistances(sd, dict(me, stats={"armor": 1, "magicResist": 1}))
    assert abs(threats.gets_through(0.6, (alone[2], alone[3], alone[2], alone[3])) - 0.6) < 1e-9
    assert threats.own_resistances(sd, dict(me, stats={})) is None and threats.own_resistances(sd, None) is None
    # The request says so in words, and the figures per item turn with it: magic resist is worth more than armor now.
    me["stats"] = {"armor": 463, "magicResist": 70, "maxHealth": 3392}
    catalog = sd.catalog("std")
    seen = threats.read(sd, state, catalog, True)
    text = "\n".join(threats.lines(sd, state, seen))
    for part in ("The damage that gets through to you is mostly magic", "463 armor, which stops 82% of physical damage",
                 "70 magic resist, which stops 41% of magic damage", "your armor is already stopping most of it",
                 "magic resist is now worth more to you per gold"):
        assert part in text, f"missing: {part}\n{text}"
    gain = lambda name: threats.toughness_gain(sd.find_item(name), me["stats"], seen["mix"]["share"])
    assert gain("Force of Nature") > 1.5 * gain("Frozen Heart"), (gain("Force of Nature"), gain("Frozen Heart"))
    assert 6 <= len(seen["gains"]) <= 8, "six items, and up to two health-only ones beside them"
    # A fighter who has built health instead of attack items deals a good deal of magic damage.
    assert threats.physical_share(sd, player(sd, "Volibear")) == 0.8
    assert threats.physical_share(sd, player(sd, "Volibear", ("Heartsteel",))) == 0.6


def test_answers(sd):
    get = lambda name: sd.find_item(name)
    assert threats.answers(get("Thornmail"), "physical", True) and threats.answers(get("Randuin's Omen"), "physical", True)
    assert not threats.answers(get("Warmog's Armor"), "physical", True), "health alone is not defense on a front-line champion"
    assert not threats.answers(get("Warmog's Armor"), "mixed", True)
    assert threats.answers(get("Rylai's Crystal Scepter"), "physical", False), "health counts for a champion at the back"
    assert not threats.answers(get("Banshee's Veil"), "physical", False), "magic resist does not answer a physical attacker"
    assert threats.answers(get("Banshee's Veil"), "magic", False) and threats.answers(get("Force of Nature"), "magic", True)
    assert not threats.answers(get("Plated Steelcaps"), "physical", True), "boots never count"
    assert not threats.answers(get("Rabadon's Deathcap"), "mixed", False)


def test_read_and_lines(sd):
    catalog = sd.catalog("std")
    seen = threats.read(sd, ornn_game(sd), catalog, True)
    assert seen["held"] == [] and "Thornmail" in seen["fits"] and "Warmog's Armor" not in seen["fits"], seen["fits"]
    # A part of an item is not a finished answer; a finished armor item is, and it leaves the list of candidates.
    assert threats.read(sd, ornn_game(sd, ("Heartsteel", "Chain Vest")), catalog, True)["held"] == []
    done = threats.read(sd, ornn_game(sd, ("Heartsteel", "Thornmail")), catalog, True)
    assert done["held"] == ["Thornmail"] and "Thornmail" not in done["fits"]
    # Items the item checks rule out are not offered as defense.
    banned = {sd.find_item("Thornmail")["id"]: "x"}
    assert "Thornmail" not in threats.read(sd, ornn_game(sd), catalog, True, banned)["fits"]
    assert threats.read(sd, dict(ornn_game(sd), enemies=[]), catalog, True) is None
    # What each item adds to the damage the player can take: health, armor and magic resist multiply.
    stats = {"maxHealth": 2000, "armor": 100, "magicResist": 100}
    stat_item = lambda **s: {"stats": s}
    assert abs(threats.toughness_gain(stat_item(Health=1000), stats, 0.5) - 0.5) < 1e-9
    assert abs(threats.toughness_gain(stat_item(Armor=100), stats, 1.0) - 0.5) < 1e-9, "100 armor on 100: half again against physical"
    assert abs(threats.toughness_gain(stat_item(Armor=100), stats, 0.0)) < 1e-9, "and nothing against magic"
    assert threats.toughness_gain(stat_item(**{"Magic Resist": 100}), stats, 0.5) == threats.toughness_gain(stat_item(Armor=100), stats, 0.5)
    assert threats.toughness_gain(stat_item(Armor=50), {}, 0.5) is None
    names = [g["name"] for g in seen["gains"]]
    gain = {g["name"]: g for g in seen["gains"]}
    assert "Thornmail" in names and "Randuin's Omen" in names, names
    # Against a mostly physical team an armor item is worth more per gold than more health on a big health pool.
    warmog = threats.toughness_gain(sd.find_item("Warmog's Armor"), ornn_game(sd)["me"]["stats"], seen["mix"]["share"])
    assert gain["Thornmail"]["gain"] / 2450 > warmog / 3100 and gain["Thornmail"]["gain"] > 0.15
    text = "\n".join(threats.lines(sd, ornn_game(sd), seen))
    for part in ("Kalista: deals physical damage | 4 kills on you, 1 assists", "The damage that gets through to you is mostly physical, about",
                 "You have 5187 health, 90 armor, which stops 47% of physical damage, and 86 magic resist, which stops 46% of magic damage.",
                 "Finished items you hold against it: none.",
                 "How much longer you would last in a fight with each item", "Thornmail +", "HEALING CUTS ON YOUR TEAM: nobody holds"):
        assert part in text, f"missing: {part}\n{text}"
    # The estimate informs the plan. It never tells it to buy defense, and the plan is never reordered.
    assert "DEFENSE NEXT" not in text and "must" not in text
    assert threats.lines(sd, ornn_game(sd), None) == []


def test_fragile_champions_are_not_shown_armor(sd):
    """A champion that does not build defense is told the player's instruction, not a list of tank items.

    From real matches: Randuin's Omen went into the build of a Vel'Koz, a Zilean and a Tryndamere "because physical
    damage keeps killing you". The player's friends called it: the champion is fragile anyway, buy damage.
    """
    from aramcoach import live
    theirs = {"Vi": ("Eclipse", "Infinity Edge"), "Ashe": ("Infinity Edge",), "Sivir": ("Infinity Edge",),
              "Brand": ("Liandry's Torment",), "Ambessa": ("Eclipse",)}

    def give(p, names):
        p["items"] = [item(sd, n, slot) for slot, n in enumerate(names)]
        p["item_gold"] = sum(i["gold"] for i in p["items"])

    def game(champion, items):
        state = live.pregame_state(sd, sd.champ_id(champion), [], [sd.champ_id(c) for c in theirs], "ARAM: Mayhem")
        give(state["me"], items)
        state["me"].update(level=13, gold=900, stats={"armor": 84, "magicResist": 47, "maxHealth": 2576})
        for p in state["enemies"]:
            give(p, theirs[p["champion"]])
        state["killed_me"] = {"Vi": {"kills": 4, "assists": 2}, "Ashe": {"kills": 2, "assists": 3}}
        return state

    plain = ("Randuin's Omen", "Warmog's Armor", "Jak'Sho, The Protean", "Heartsteel", "Thornmail", "Kaenic Rookern", "Frozen Heart")
    mage = game("Vel'Koz", ("Luden's Echo", "Liandry's Torment"))
    assert not advisor._sturdy(sd, mage["me"])
    seen = advisor._threats(sd, mage)
    assert seen["sturdy"] is False and 1 <= len(seen["gains"]) <= 4
    assert all(sd.find_item(g["name"])["stats"].get("Ability Power") for g in seen["gains"]), seen["gains"]
    text = "\n".join(threats.lines(sd, mage, seen))
    assert "The damage that gets through to you is mostly physical" in text, "the kind of damage is still said"
    assert "do not buy an item only for its armor, magic resist or health" in text
    assert not any(name in text for name in plain), text
    assert "Finished items you hold against it" not in text and "only health helps" not in text
    request = advisor.render_request(sd, mage, "", "REQUEST: plan")
    assert "HOW TO USE THAT ESTIMATE" not in request, "the notes on balancing resistances are for champions that buy them"
    # A marksman gets the same, with attack items.
    fighter = advisor._threats(sd, game("Jinx", ("Infinity Edge",)))
    attack = lambda name: any(sd.find_item(name)["stats"].get(k) for k in threats.PHYSICAL_STATS)
    assert fighter["sturdy"] is False and fighter["gains"] and all(attack(g["name"]) for g in fighter["gains"]), fighter["gains"]
    # A front-line champion and a hook support still get the full list and the notes.
    for champion in ("Malphite", "Thresh", "Blitzcrank"):
        tank = game(champion, ("Sunfire Aegis",))
        assert advisor._sturdy(sd, tank["me"]), champion
        seen = advisor._threats(sd, tank)
        text = "\n".join(threats.lines(sd, tank, seen))
        assert seen["sturdy"] and any(name in text for name in plain) and "do not buy an item only for" not in text, champion
        assert "HOW TO USE THAT ESTIMATE" in advisor.render_request(sd, tank, "", "REQUEST: plan")
    # What the player typed during the match reaches every later request as an instruction.
    told = dict(mage, told=[{"time": 769, "text": "teammates say dont build anything defensive on my ap mage"}])
    request = advisor.render_request(sd, told, "", "REQUEST: plan")
    assert '12:49 "teammates say dont build anything defensive on my ap mage"' in request and "Do not argue with it" in request
    assert "WHAT THE PLAYER TYPED" not in advisor.render_request(sd, mage, "", "REQUEST: plan")


def test_the_plan_is_not_reordered(sd):
    catalog = sd.catalog("std")
    entry = lambda name: {"item_id": sd.find_item(name)["id"], "name": name, "why": ""}
    order = ["Trinity Force", "Plated Steelcaps", "Infinity Edge", "Sterak's Gage", "Randuin's Omen", "Death's Dance"]
    advice = advisor._validate({"headline": "h", "build_order": [entry(n) for n in order], "changed": ""}, catalog)
    assert [b["name"] for b in advice["build_order"]] == order, "the combination piece stays where the plan put it"
    assert "moved_up" not in advice


def test_the_request_carries_it(sd):
    from aramcoach import live
    state = live.pregame_state(sd, sd.champ_id("Ornn"), [sd.champ_id("Caitlyn")], [sd.champ_id("Kalista"), sd.champ_id("Veigar")], "ARAM")
    text = advisor.render_request(sd, state, "", "REQUEST: plan")
    assert "WHAT IS KILLING YOU" in text and "Kalista: deals physical damage | no part in your deaths so far" in text
    assert "from the enemy champions" in text and "DEFENSE NEXT" not in text
    # How to use the estimate is told to plans only. An augment offer is asked exactly as it was before.
    assert "HOW TO USE THAT ESTIMATE IN THIS PLAN" in text
    assert "HOW TO USE THAT ESTIMATE" not in advisor.render_request(sd, state, "", "REQUEST: augments")
    assert "usually within ten points" in advisor.SYSTEM_PROMPT, "the system prompt is the one the augment picks were replayed with"
    blind = live.pregame_state(sd, sd.champ_id("Ornn"), [], [], "ARAM")
    assert "WHAT IS KILLING YOU" not in advisor.render_request(sd, blind, "", "REQUEST: pregame")


def test_true_damage(sd):
    """An enemy whose ability text says true damage is named, since no resistance answers it."""
    assert threats.true_damage(sd, "Chogath") == ["R Feast"]
    assert threats.true_damage(sd, "Lux") == [] and threats.true_damage(sd, None) == []


if __name__ == "__main__":
    data = StaticData()
    test_kinds(data)
    test_mix(data)
    test_own_resistances(data)
    test_fragile_champions_are_not_shown_armor(data)
    test_answers(data)
    test_read_and_lines(data)
    test_the_plan_is_not_reordered(data)
    test_the_request_carries_it(data)
    test_true_damage(data)
    print("threat checks ok")
