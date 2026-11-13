"""Checks for reading missing augment text from arammayhem.com. Run: python tests/test_augtext.py

The pages here are made up, in the shape the site serves. No network and no Claude calls.
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aramcoach import augtext, config  # noqa: E402
from aramcoach.static_data import NO_EFFECT_TEXT, clean_wiki  # noqa: E402

# The list page also carries each augment's rank and pick rate. None of it may be kept.
LIST = "<html><body><h1>Tier List</h1><span>Rank</span><span>Augment</span><span>Tier</span><span>Pick Rate</span>" + "".join(
    f'<a href="/augments/{slug}/"><span>{rank}</span><span>{name}</span><span>{rarity}</span><span>{pick}%</span>'
    f'<span>{rating}</span></a>'
    for rank, name, rarity, pick, rating, slug in (
        (1, "Goliath", "Prismatic", "35.32", "S+", "goliath"), (2, "Quest: Steel Your Heart", "Gold", "25.67", "S-", "quest-steel-your-heart"),
        (3, "Zealot", "Silver", "20.00", "A+", "zealot"), (4, "Take’em Down Down Down", "Gold", "39.92", "S", "take-em-down"),
        (5, "Glass Cannon", "Prismatic", "4.97", "D", "glass-cannon"))) + "</body></html>"

PAGE = ("<html><body><a>← Back to Augments</a><h1>Quest: Steel Your Heart</h1><span>Gold</span><b>Quest:</b>"
        "<span>Obtain Heartsteel and accumulate over</span><b>300</b><span>bonus</span><span>health</span><span>.</span>"
        "<b>Reward:</b><span>Upon completing your</span><b>Quest</b><span>, more health.</span>"
        "<span>Last updated · Nov 9, 2026</span><span>Tier</span><span>S-</span><span>Pick Rate</span><span>25.67%</span></body></html>")
TEXT = "Quest: Obtain Heartsteel and accumulate over 300 bonus health. Reward: Upon completing your Quest, more health."


class Data:
    """Stands in for the game data: three augments, two of them without a description."""

    def __init__(self, folder):
        self.dir = Path(folder)

    def augments_all(self):
        return [{"name": "Steel Your Heart", "description": ""}, {"name": "Goliath", "description": "Grants health."},
                {"name": "HEAVY", "description": ""}, {"name": "???", "description": ""}]


def test_parsers():
    slugs = augtext.parse_slugs(LIST)
    assert slugs == {"goliath": "goliath", "steelyourheart": "quest-steel-your-heart", "zealot": "zealot",
                     "takeemdowndowndown": "take-em-down", "glasscannon": "glass-cannon"}, slugs     # addresses only
    assert augtext.parse_augment_text(PAGE) == TEXT
    assert augtext.parse_augment_text("<html><body>nothing</body></html>") == ""
    assert augtext.key_for("Quest: Steel Your Heart") == augtext.key_for("Steel Your Heart") == "steelyourheart"
    assert augtext.key_for("Questionable") == "questionable"
    for gone in ("augment_note", "champion_lines", "parse_champion", "champion", "augments"):
        assert not hasattr(augtext, gone), f"usage statistics must not come back: {gone}"


def test_wiki_templates():
    """A template whose name carries the meaning keeps it. Each of these read wrongly in a real augment's text."""
    cases = [
        ("{{tip|Immobilize|Immobilizing}} or {{tip|ground|grounding}} an enemy champion grants you {{adaptive|10}}, stacking",
         "Immobilizing or grounding an enemy champion grants you 10 adaptive force, stacking"),            # was "grants you 10"
        ("Gain {{rd|75|50}} '''bonus''' attack range.", "Gain 75 (melee) / 50 (ranged) bonus attack range."),
        ("empowering {{nie|Taxes}} to generate {{g|25}}. Additionally, gain {{g|250}}.",
         "empowering Taxes to generate 25 gold. Additionally, gain 250 gold."),
        ("for a total of {{as|{{pp|11*4 to 80*4}}|magic damage}} {{as|(+ 35*4% '''bonus''' AD)}}",
         "for a total of 44 to 320 (+ 140% bonus AD)"),
        ("that deals{{ft|{{as|{{pp|6/3 to 60/3}}}} {{as|(+ {{ap|6/3}}% AP)}} per second|{{as|6 to 60}} in all}}(1 second cooldown)",
         "that deals 2 to 20 (+ 2% AP) per second (1 second cooldown)"),
        ("you are {{tip|heal|healed}} for {{as|{{ap|30/12}}% of your '''maximum''' health}} every {{fd|0.25}} seconds",
         "you are healed for 2.5% of your maximum health every 0.25 seconds"),
        ("{{sbc|Poltergeist:}} {{#invoke:SpellData|geteffect|Poltergeist}}", f"Poltergeist: {NO_EFFECT_TEXT}"),
        ("while located at least {{tip|er}} 600 units away, after 3 seconds, per 1 stack", "while located at least 600 units away, after 3 seconds, per 1 stack"),
        ("Your {{tt|spinning abilities|Any ability with spinning properties}} deal 30% more damage with [[Sheen|the sheen]].",
         "Your spinning abilities deal 30% more damage with the sheen."),
    ]
    for raw, expected in cases:
        assert clean_wiki(raw) == expected, f"{raw}\n  gave: {clean_wiki(raw)}\n  want: {expected}"


def test_only_missing_text_is_read():
    real_get, asked = augtext._get, []
    pages = {f"{augtext.SITE}/augments/": LIST, f"{augtext.SITE}/augments/quest-steel-your-heart/": PAGE}

    def fake_get(url):
        asked.append(url)
        return pages[url]

    with tempfile.TemporaryDirectory() as tmp:
        sd = Data(tmp)
        augtext._get, augtext.MIN_AUGMENTS, config.AUGMENT_TEXT = fake_get, 3, True
        try:
            assert augtext.texts(sd) == {} and asked == [], "nothing is read unless asked to fetch"
            assert augtext.texts(sd, fetch=True) == {"Steel Your Heart": TEXT}
            assert asked == list(pages), "the list, then only the page of the augment that lacks text"
            saved = (Path(tmp) / "augment_text.json").read_text(encoding="utf-8")
            assert "25.67" not in saved and "Pick Rate" not in saved and '"rank"' not in saved, saved
            assert set(json.loads(saved)["tried"]) == {"Steel Your Heart", "HEAVY"}, "the site has no page for HEAVY"
            assert augtext.texts(sd, fetch=True) == {"Steel Your Heart": TEXT} and len(asked) == 2, "not asked for again"
            # A list the site no longer serves in this shape changes nothing.
            (Path(tmp) / "augment_text.json").unlink()
            pages[f"{augtext.SITE}/augments/"] = "<html><body>redesigned</body></html>"
            assert augtext.texts(sd, fetch=True) == {} and len(asked) == 3
            # Turned off: nothing is asked for.
            config.AUGMENT_TEXT = False
            assert augtext.texts(sd, fetch=True) == {} and len(asked) == 3
            augtext.prepare(sd)
            assert len(asked) == 3
        finally:
            augtext._get, augtext.MIN_AUGMENTS, config.AUGMENT_TEXT = real_get, 100, True


if __name__ == "__main__":
    test_parsers()
    test_wiki_templates()
    test_only_missing_text_is_read()
    print("augment text checks ok")
