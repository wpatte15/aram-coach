"""Checks for the research prepared ahead of a match. Run: python tests/test_research.py

The research here is made up, in the shape Claude answers. Uses the game data cached on disk.
No network and no Claude calls.
"""
import inspect
import json
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aramcoach import advisor, config, live, llm, research  # noqa: E402
from aramcoach.static_data import StaticData  # noqa: E402

config.player_profile = lambda: "I am new to the game. I never press item buttons."
research.log = lambda *args, **kwargs: None       # keep made-up events out of the real log

MAP_ANSWER = {"augments": [
    {"name": "Soul Eater", "kind": "Engine", "does": "Immobilising a champion grants 30 health for good.",
     "wants": "an ability that immobilises on a short cooldown.",
     "items": [{"name": "Heartsteel", "why": "more health for what scales with health"},
               {"name": "Zhonya's Hourglass", "why": "only a button"}, {"name": "No Such Item", "why": "x"}],
     "augments": [{"name": "Quest: Steel Your Heart", "why": "both grow health"}, {"name": "Soul Eater", "why": "itself"},
                  {"name": "Nonexistent Augment", "why": "x"}],
     "dead": "kits with no immobilising ability"},
    {"name": "It's Critical", "kind": "amplifier", "does": "Grants 50% critical strike chance.",
     "wants": "abilities or attacks that can critically strike",
     "items": [{"name": "Infinity Edge", "why": "bigger crits at 100% chance"}], "augments": ["Jeweled Gauntlet"], "dead": ""},
    {"name": "Jeweled Gauntlet", "kind": "amplifier", "does": "Abilities can critically strike.",
     "wants": "abilities that deal damage", "items": [], "augments": [], "dead": ""},
    {"name": "Goliath", "kind": "stats", "does": "Grants 35% bonus health.", "wants": "a front-line champion"},
    {"name": "Made Up Augment", "kind": "engine", "does": "x"},
    {"name": "Zealot", "kind": "stats", "does": ""},
]}

BOOK_ANSWER = {
    "hooks": ["E Judgment spins seven times and each spin can critically strike."],
    "lacks": ["Nothing in the kit heals or shields an ally."],
    "combos": [
        {"name": "Crit spin", "augments": ["Zealot", "It's Critical", "Jeweled Gauntlet", "Fake Augment"],
         "items": ["Infinity Edge", "Trinity Force", "Redemption", "Nonexistent Blade", "Iceborn Gauntlet"], "kit": "E Judgment",
         "chain": "Zealot gives 25% crit chance and attack speed, so E spins more often and each spin can crit.",
         "reaches": "100% crit chance", "breaks": "enemies stacking armor"},
        {"name": "Nothing real", "augments": ["Fake Augment"], "items": ["Infinity Edge"], "kit": "", "chain": "x"},
        {"name": "No chain", "augments": ["Zealot"], "items": []},
    ],
    "augments": [{"name": "Zealot", "fit": "strong", "why": "E spins faster with attack speed."},
                 {"name": "Soul Eater", "fit": "weak", "why": "Garen has no immobilising ability"},
                 {"name": "Goliath", "fit": "fine", "why": "x"}, {"name": "Fake", "fit": "core", "why": "x"}],
}


def test_answers_are_checked(sd):
    rows = research.clean_map(sd, MAP_ANSWER)
    assert set(rows) == {"souleater", "itscritical", "jeweledgauntlet", "goliath"}, set(rows)   # no such augment; no mechanism
    eater = rows["souleater"]
    assert eater["kind"] == "engine" and [i["name"] for i in eater["items"]] == ["Heartsteel"], eater    # button-only, unknown
    assert [research._key(a["name"]) for a in eater["augments"]] == ["steelyourheart"], eater           # itself, unknown
    assert rows["itscritical"]["augments"] == [{"name": "Jeweled Gauntlet", "why": ""}]
    book = research.clean_playbook(sd, "Garen", BOOK_ANSWER)
    assert [c["name"] for c in book["combos"]] == ["Crit spin"], book["combos"]
    combo = book["combos"][0]
    assert combo["augments"] == ["Zealot", "It's Critical", "Jeweled Gauntlet"], combo
    # Redemption needs its button, the blade does not exist, and Iceborn Gauntlet is a second Spellblade item.
    assert combo["items"] == ["Infinity Edge", "Trinity Force"], combo
    groups = sd.exclusive_groups()
    # A plan loses a second item of such a group, and says why.
    plan = advisor._validate({"build_order": [{"name": "Trinity Force"}, {"name": "Lich Bane"}, {"name": "Infinity Edge"},
                                              {"name": "Sunfire Aegis"}, {"name": "Hollow Radiance"}]}, sd.catalog("std"))
    assert [b["name"] for b in plan["build_order"]] == ["Trinity Force", "Infinity Edge", "Sunfire Aegis"], plan["build_order"]
    assert [d["name"] for d in plan["dropped"]] == ["Lich Bane", "Hollow Radiance"] and "Spellblade" in plan["dropped"][0]["why"]
    # Once the player owns finished boots, the build keeps that pair.
    ionian = sd.find_item("Ionian Boots of Lucidity")["id"]
    raw = {"build_order": [{"name": "Infinity Edge"}, {"name": "Mercury's Treads"}, {"name": "Trinity Force"}]}
    plan = advisor._validate(raw, sd.catalog("std"), owned={ionian})
    assert [b["name"] for b in plan["build_order"]] == ["Infinity Edge", "Ionian Boots of Lucidity", "Trinity Force"], plan
    assert plan["dropped"][0]["name"] == "Mercury's Treads" and "already own" in plan["dropped"][0]["why"]
    plan = advisor._validate(raw, sd.catalog("std"), owned={sd.find_item("Infinity Edge")["id"]})
    assert [b["name"] for b in plan["build_order"]][1] == "Mercury's Treads" and not plan["dropped"], "no boots owned: no change"
    assert {"Trinity Force", "Iceborn Gauntlet", "Lich Bane"} <= set(groups["Spellblade"]) and "Grievous Wounds" not in groups
    assert "ITEMS THAT DO NOT COMBINE" in advisor.system_prompt_file(sd, "std").read_text(encoding="utf-8")
    fits = {key: row["fit"] for key, row in book["augments"].items()}
    assert fits == {"zealot": "core", "souleater": "weak", "itscritical": "core", "jeweledgauntlet": "core"}, fits
    return rows, book


def test_requests(sd):
    long_text = "x" * 500
    text = research.map_request([{"name": "Soul Eater", "tier": "Gold", "description": long_text}])
    assert text.startswith("REQUEST: research") and f"Soul Eater | Gold | {long_text}" in text
    assert "What players usually pick is not evidence" in text
    saved, config.RESEARCH = config.RESEARCH, "0"
    try:
        text = research.champion_request(sd, "Garen")
    finally:
        config.RESEARCH = saved
    for part in ("TASK: champion. Work out what can be built on Garen's kit", "CHAMPION: Garen (", "(melee)",
                 "Judgment", "ITEM CHECKS", "There is no augment map yet"):
        assert part in text, f"missing: {part}"
    prompt = advisor.SYSTEM_PROMPT
    assert "PREPARED RESEARCH" in prompt and "## REQUEST: research" in prompt
    for gone in ("pick rate", "LEADS FROM OTHER PLAYERS", "arammayhem", "rarely taken"):
        assert gone not in prompt, f"usage statistics must not come back: {gone}"
    assert "max_tokens" in inspect.signature(llm.run).parameters


def test_saved_research_feeds_the_requests(sd, rows, book):
    real_folder, real_cache, real_run = research._folder, config.CACHE_DIR, llm.run
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp) / "now" / "research"
        research._folder, config.RESEARCH = (lambda _sd: folder), "saved"
        config.CACHE_DIR = Path(tmp)                  # research saved on this machine must not be found
        try:
            state = live.pregame_state(sd, "Garen", ["Jinx"], ["Lux"], "ARAM: Mayhem")
            state["my_augments"] = ["Zealot"]
            state["me"]["items"] = [{"id": sd.find_item("Infinity Edge")["id"], "name": "Infinity Edge"}]
            assert research.plan_lines(sd, state) == [] and research.card_lines(sd, state, ["Zealot"]) == []
            research._save(sd, "augments.json", {"version": research.VERSION, "patch": sd.version, "augments": rows})
            research._save(sd, "champion_Garen.json", {"version": research.VERSION, "patch": sd.version, "champion": "Garen",
                                                       "made": "", **book})
            text = "\n".join(research.plan_lines(sd, state))
            for part in ("PREPARED RESEARCH ON GAREN (your own earlier working", "it has not seen this match",
                         "+ E Judgment spins seven times", "- Nothing in the kit heals",
                         "1. Crit spin: augments Zealot [HELD], It's Critical, Jeweled Gauntlet; items Infinity Edge [OWNED], "
                         "Trinity Force; through E Judgment.", "Reaches: 100% crit chance Breaks: enemies stacking armor",
                         "Zealot: core on this kit: E spins faster with attack speed."):
                assert part in text, f"missing: {part}\n{text}"
            assert "written on patch" not in text
            # A combination the player has not opened shows no items and no chain during a match.
            bare = dict(state, my_augments=[])
            text = "\n".join(research.plan_lines(sd, bare))
            assert "Combinations not opened" in text and "- Crit spin: opens with Zealot, It's Critical, Jeweled Gauntlet; " \
                "through E Judgment. Reaches: 100% crit chance" in text, text
            assert "Trinity Force" not in text and "so E spins more often" not in text, text
            # In champion select every combination is given in full, for the item set.
            text = "\n".join(research.plan_lines(sd, bare, ahead=True))
            assert "1. Crit spin: augments Zealot, It's Critical, Jeweled Gauntlet; items Infinity Edge [OWNED], Trinity Force" in text
            assert "belong in `augment_builds`" in text
            assert "Combinations not opened" in advisor.render_request(sd, bare, "", "REQUEST: plan")
            assert "belong in `augment_builds`" in advisor.render_request(sd, bare, "", "REQUEST: pregame")
            cards = "\n".join(research.card_lines(sd, state, ["It's Critical", "Soul Eater", "Goliath", "Jeweled Gauntlet"]))
            for part in ("WHAT THE PREPARED RESEARCH SAYS ABOUT THE CARDS ON OFFER:",
                         "It's Critical: core on Garen: a piece of Crit spin. A piece of \"Crit spin\", with Zealot [HELD], "
                         "Jeweled Gauntlet. On any champion: Wants: abilities or attacks that can critically strike. "
                         "Augments it compounds with: Jeweled Gauntlet.",
                         "Soul Eater: weak on Garen: Garen has no immobilising ability. On any champion: Wants: an ability "
                         "that immobilises on a short cooldown. Augments it compounds with: ",
                         "Does little when: kits with no immobilising ability.",
                         "Goliath: no entry for Garen: its worth here is ordinary, so judge it from its text.",
                         # A link written on the other augment's row counts from this side too.
                         "Augments it compounds with: It's Critical."):
                assert part in cards, f"missing: {part}\n{cards}"
            assert not any(line.lstrip().startswith("HEAVY") for line in research.card_lines(sd, state, ["HEAVY", "Goliath"]))
            # Only an augment the playbook calls core or strong is a reason to remake the build.
            assert research.matters(sd, "Garen", "Zealot") and not research.matters(sd, "Garen", "Goliath")
            assert not research.matters(sd, "Garen", "Soul Eater"), "weak on this kit"
            assert not research.matters(sd, "Garen", "Health Shard") and not research.matters(sd, "Lux", "Magic Resist Shard")
            # Without a playbook the augment map decides: an engine or an amplifier matters, plain stats do not.
            assert research.matters(sd, "Lux", "It's Critical") and not research.matters(sd, "Lux", "Goliath")
            assert research.matters(sd, "Lux", "Some Augment Nobody Researched")
            # The plan request and the offer request carry it.
            assert "PREPARED RESEARCH ON GAREN" in advisor.render_request(sd, state, "", "REQUEST: plan")
            sent = []
            llm.run = lambda system, prompt, **kw: (sent.append(prompt) or '{"pick": "It\'s Critical", "why": "w"}', {})
            offer = [sd.augment("It's Critical"), sd.augment("Goliath"), sd.augment("Soul Eater")]
            result, _ = advisor.choose_augment(sd, state, "", offer)
            assert result["pick"] == "It's Critical" and "WHAT THE PREPARED RESEARCH SAYS ABOUT THE CARDS ON OFFER" in sent[0]
            assert "measured:" not in sent[0] and "rank " not in sent[0].split("AUGMENTS ON OFFER")[1]
            llm.run = real_run
            # A champion with no playbook still gets what the augment map says about the augments held and offered.
            other = live.pregame_state(sd, "Lux", ["Jinx"], [], "ARAM: Mayhem")
            other["my_augments"] = ["It's Critical"]
            text = "\n".join(research.plan_lines(sd, other))
            assert "there is none on Lux's kit yet" in text and "It's Critical: On any champion: Wants: abilities" in text, text
            assert "only what holds on any champion" in research.card_lines(sd, other, ["Soul Eater"])[0]
            # The map's item links are given only where there is no playbook to say what fits the kit.
            assert "Items that multiply it: Heartsteel" in research.card_lines(sd, other, ["Soul Eater"])[1]
            assert "Items that multiply it" not in cards
            # Research written for an earlier patch is still used, and the request says so.
            old = Path(tmp) / "15.1.1" / "research"
            old.mkdir(parents=True)
            for path in folder.iterdir():
                data = json.loads(path.read_text(encoding="utf-8"))
                (old / path.name).write_text(json.dumps({**data, "patch": "15.1.1"}), encoding="utf-8")
                path.unlink()
            assert ", written on patch 15.1.1;" in research.plan_lines(sd, state)[0]
            # A file written for an older request format is set aside.
            (old / "champion_Garen.json").write_text(json.dumps({"version": 0, "combos": []}), encoding="utf-8")
            assert research.playbook(sd, "Garen") is None
            # Turned off: nothing is used.
            config.RESEARCH = "0"
            assert research.plan_lines(sd, state) == [] and research.card_lines(sd, state, ["Soul Eater"]) == []
        finally:
            research._folder, config.CACHE_DIR, config.RESEARCH, llm.run = real_folder, real_cache, "1", real_run


def test_writing(sd):
    """The augment map is asked for in batches, an answer that leaves augments out is asked again, and failures wait."""
    real = (research._folder, research._ask, research.MAP_BATCH, sd.augments_described, research.build_champion,
            research.build_map, config.RESEARCH, config.CACHE_DIR)
    names = ["Soul Eater", "It's Critical", "Jeweled Gauntlet", "Zealot", "Goliath"]
    asked, skipped = [], {"Zealot"}

    def fake_ask(_sd, prompt, on_start=None):
        listed = [line.split(" | ")[0] for line in prompt.split("full effect text):\n")[1].splitlines()]
        asked.append(listed)
        if on_start:
            on_start()
        answer = [{"name": n, "kind": "stats", "does": f"{n} does something."} for n in listed if n not in skipped]
        skipped.difference_update(listed)                 # left out once, answered when asked again
        return {"augments": answer}, {"cost": 0.5}

    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp) / "research"
        research._folder, research._ask, research.MAP_BATCH = (lambda _sd: folder), fake_ask, 2
        config.CACHE_DIR = Path(tmp)                  # research saved on this machine must not be found
        sd.augments_described = lambda: [sd.augment(n) for n in names]
        try:
            result = research.build_map(sd)
            assert sorted(map(len, asked)) == [1, 1, 2, 2] and asked[-1] == ["Zealot"], asked
            assert result["augments"] == 5 and result["missing"] == [] and result["cost"] == 2.0, result
            assert set(research.augment_map(sd)["augments"]) == {research._key(n) for n in names}
            # Doing one augment again keeps the rest. With nothing missing, nothing is asked.
            research.build_map(sd, only=["Goliath"])
            assert asked[-1] == ["Goliath"] and len(research.augment_map(sd)["augments"]) == 5
            count = len(asked)
            assert research.build_map(sd)["written"] == 0 and len(asked) == count
            # A run cut short keeps what was answered, and the next run asks for the rest only.
            asked.clear()
            research._ask = lambda _sd, prompt, on_start=None: (_ for _ in ()).throw(llm.LLMError("cut off")) \
                if "Zealot" in prompt.split("full effect text):\n")[1] else fake_ask(_sd, prompt, on_start)
            result = research.build_map(sd, fresh=True)
            assert result["written"] == 4 and result["missing"] == ["Zealot"], result
            assert len(research.augment_map(sd)["augments"]) == 4 and research.map_missing(sd) == [sd.augment("Zealot")]
            research._ask = fake_ask
            asked.clear()
            assert research.build_map(sd)["written"] == 1 and asked == [["Zealot"]], asked
            # ensure: nothing is written with "saved", nor when it is there already; a missing playbook is written once.
            built = []
            research.build_champion = lambda _sd, cid, on_start=None: built.append(cid)
            research.build_map = lambda _sd: built.append("map")
            wait = lambda: [time.sleep(0.02) for _ in range(100) if research._building]
            config.RESEARCH = "saved"
            research.ensure(sd, "Garen")
            wait()
            assert built == []
            config.RESEARCH = "1"
            research.ensure(sd)
            wait()
            assert built == [], "the augment map is saved"
            research.ensure(sd, "Garen")
            wait()
            assert built == ["Garen"], built

            def failing(_sd, cid, on_start=None):
                built.append(f"failed {cid}")
                raise llm.LLMError("no")

            research.build_champion = failing
            research.ensure(sd, "Lux")
            wait()
            research.ensure(sd, "Lux")
            wait()
            assert built == ["Garen", "failed Lux"], "a failed request is not repeated at once"
            # With no augment map at all, that is written first.
            (folder / "augments.json").unlink()
            research._cache.clear()
            research.build_champion = lambda _sd, cid, on_start=None: built.append(cid)
            research.ensure(sd, "Jinx")
            wait()
            assert built[-2:] == ["map", "Jinx"], built
        finally:
            (research._folder, research._ask, research.MAP_BATCH, sd.augments_described, research.build_champion,
             research.build_map, config.RESEARCH, config.CACHE_DIR) = real
            research._failed_at.clear()


if __name__ == "__main__":
    data = StaticData()
    made_rows, made_book = test_answers_are_checked(data)
    test_requests(data)
    test_saved_research_feeds_the_requests(data, made_rows, made_book)
    test_writing(data)
    print("research checks ok")
