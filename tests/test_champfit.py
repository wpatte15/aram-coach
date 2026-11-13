"""Checks the champion-select ranking with a small hand-made champion list.

Run with: .venv\\Scripts\\python.exe tests\\test_champfit.py
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aramcoach import champfit, config  # noqa: E402


class FakeData:
    """The parts of StaticData the ranking uses."""
    champions = {
        "Garen": {"name": "Garen", "tags": ["Fighter", "Tank"], "difficulty": 5},
        "Malphite": {"name": "Malphite", "tags": ["Tank", "Mage"], "difficulty": 2},
        "Leblanc": {"name": "LeBlanc", "tags": ["Assassin", "Mage"], "difficulty": 9},
        "Jinx": {"name": "Jinx", "tags": ["Marksman"], "difficulty": 6},
        "Sona": {"name": "Sona", "tags": ["Support", "Mage"], "difficulty": 4},
        "Lux": {"name": "Lux", "tags": ["Mage", "Support"], "difficulty": 5},
        "Ashe": {"name": "Ashe", "tags": ["Marksman", "Support"], "difficulty": 4},
    }
    champ_by_key = {86: "Garen", 54: "Malphite", 7: "Leblanc", 222: "Jinx", 37: "Sona", 99: "Lux", 22: "Ashe"}

    def champ_id(self, name, raw=""):
        return next((cid for cid, c in self.champions.items() if c["name"].lower() == name.lower()), None)


SD = FakeData()
TABLE = {
    "Garen": {"ease": 5, "job": "frontline", "why": "tanky, simple spin"},
    "Malphite": {"ease": 5, "job": "frontline", "why": "press R on their team"},
    "Leblanc": {"ease": 1, "job": "damage", "why": "fragile, needs a combination"},
    "Jinx": {"ease": 3, "job": "damage", "why": "strong but dies to anything"},
    "Sona": {"ease": 4, "job": "support", "why": "heals by pressing buttons"},
    "Lux": {"ease": 3, "job": "damage", "why": "long range, needs aim"},
    "Ashe": {"ease": 4, "job": "damage", "why": "slows from range"},
}


config.player_profile = lambda: "I am new to the game."      # no favourites unless a test names some


def options(mine=0, bench=(), cards=(), mates=()):
    return {"mine": mine, "bench": list(bench), "cards": list(cards), "mates": list(mates)}


def test_fallback_uses_the_games_own_data():
    assert champfit.fallback(SD, "Malphite") == {"ease": 5, "job": "frontline", "why": ""}
    assert champfit.fallback(SD, "Leblanc")["ease"] == 1 and champfit.fallback(SD, "Leblanc")["job"] == "damage"
    assert champfit.fallback(SD, "Sona")["job"] == "support" and champfit.fallback(SD, "Garen")["job"] == "frontline"
    assert champfit.fallback(SD, "Nobody") == {"ease": 3, "job": "damage", "why": ""}


def test_parse_skips_bad_lines_and_accepts_names():
    text = ("Here are the ratings:\n"
            "Garen | 5 | frontline | tanky, simple spin\n"
            "LeBlanc | 1 | damage | fragile, needs a combination\n"      # display name instead of the id
            "Jinx | nine | damage | bad number\n"
            "Sona | 9 | healer | number out of range, unknown job\n"
            "Nobody | 3 | damage | not a champion\n")
    table = champfit.parse(SD, text)
    assert set(table) == {"Garen", "Leblanc", "Sona"}
    assert table["Leblanc"] == {"ease": 1, "job": "damage", "why": "fragile, needs a combination"}
    assert table["Sona"]["ease"] == 5 and table["Sona"]["job"] == "support", "clamped, and the job falls back to the tags"


def test_an_easier_bench_champion_is_worth_a_swap():
    ranked = champfit.rank(SD, options(mine=7, bench=[222, 86]), TABLE, {})
    assert [r["champion"] for r in ranked["rows"]] == ["Garen", "Jinx", "LeBlanc"]
    assert ranked["advice"] == "Swap to Garen, on the bench." and ranked["swap"] is True and ranked["personal"] is True


def test_a_small_difference_keeps_the_champion_in_hand():
    ranked = champfit.rank(SD, options(mine=222, bench=[99]), TABLE, {"Lux": {"games": 2, "wins": 1, "deaths": 8.0}})
    assert ranked["rows"][0]["champion"] == "Lux" and ranked["rows"][0]["score"] == 3.4, "two games add 0.4"
    assert ranked["advice"] == "Keep Jinx." and ranked["swap"] is False
    assert ranked["rows"][0]["games"] == 2 and ranked["rows"][0]["deaths"] == 8.0


def test_team_need_counts_once_teammates_have_champions():
    early = champfit.rank(SD, options(mine=22, bench=[86], mates=[99]), TABLE, {})
    assert all(r["need"] == "" for r in early["rows"]), "one teammate is not a team to read"
    late = champfit.rank(SD, options(mine=22, bench=[86], mates=[99, 222, 37]), TABLE, {})
    garen = next(r for r in late["rows"] if r["champion"] == "Garen")
    assert garen["need"] == "your team has no front line" and garen["score"] == 6.0
    assert late["advice"] == "Swap to Garen, on the bench."
    crowded = champfit.rank(SD, options(mine=22, bench=[37], mates=[99, 222, 7]), TABLE, {})
    ashe = next(r for r in crowded["rows"] if r["champion"] == "Ashe")
    assert ashe["need"] == "your team already has 3 damage dealers" and ashe["score"] == 3.5


def test_favourites_are_read_from_the_profile():
    real = config.player_profile
    config.player_profile = lambda: ("I am new.\n\nLove to play: garen, Sona\nLike to play: Jinx, sona, Nobody and Lux.\n"
                                     "I do not like to play: LeBlanc\nChampions I understand reasonably well: Ashe.")
    try:
        assert champfit.favourites(SD) == {"Garen": "love", "Sona": "love", "Jinx": "like", "Lux": "like", "Ashe": "like"}
    finally:
        config.player_profile = real
    assert champfit.favourites(SD) == {}


def test_a_favourite_comes_before_an_easier_champion_the_team_needs():
    liked = {"Jinx": "like", "Leblanc": "love"}
    # Garen is easier and the team has no front line, but the player asked for Jinx.
    ranked = champfit.rank(SD, options(mine=99, bench=[86, 222], mates=[99, 22, 37]), TABLE, {}, liked)
    assert [r["champion"] for r in ranked["rows"]] == ["Jinx", "Garen", "Lux"]
    assert ranked["advice"] == "Swap to Jinx, on the bench." and ranked["rows"][0]["liked"] == "like"
    # A loved champion beats a liked one, even one rated hard.
    ranked = champfit.rank(SD, options(mine=222, bench=[7, 86]), TABLE, {}, liked)
    assert [r["champion"] for r in ranked["rows"]] == ["LeBlanc", "Jinx", "Garen"]
    assert ranked["advice"] == "Swap to LeBlanc, on the bench."
    # Holding a favourite, a small gain among equals is still not worth a swap.
    both = {"Jinx": "like", "Lux": "like"}
    ranked = champfit.rank(SD, options(mine=222, bench=[99]), TABLE, {"Lux": {"games": 2, "wins": 1, "deaths": 8.0}}, both)
    assert ranked["advice"] == "Keep Jinx."
    # With no favourite on offer the ranking is what it was.
    ranked = champfit.rank(SD, options(mine=7, bench=[222, 86]), TABLE, {}, {"Sona": "love"})
    assert [r["champion"] for r in ranked["rows"]] == ["Garen", "Jinx", "LeBlanc"] and ranked["rows"][0]["liked"] == ""


def test_cards_before_a_champion_is_held():
    ranked = champfit.rank(SD, options(cards=[7, 54]), None, {})
    assert ranked["advice"] == "Take Malphite." and ranked["personal"] is False
    assert [r["source"] for r in ranked["rows"]] == ["card", "card"]
    assert champfit.rank(SD, options(), TABLE, {}) is None


def test_record_reads_post_game_files_and_skips_games_against_nobody():
    work = Path(tempfile.mkdtemp(prefix="aramcoach-fit-"))
    config.CAPTURE_DIR, config.CACHE_DIR = work / "captures", work / "cache"
    player = lambda champ, team, me=False, win=True, deaths=3: {
        "me": me, "team": team, "champ_id": champ, "win": win, "kda": [1, deaths, 5]}
    games = {
        "a": {"game_id": 1, "minutes": 18, "players": [player("Garen", 100, me=True, deaths=11, win=False),
                                                       player("Jinx", 200), player("Lux", 200)]},
        "b": {"game_id": 2, "minutes": 15, "players": [player("Garen", 100, me=True, deaths=5),
                                                       player("Jinx", 200), player("Lux", 200)]},
        "solo": {"game_id": 3, "minutes": 6, "players": [player("Sona", 100, me=True)]},
        "short": {"game_id": 4, "minutes": 2, "players": [player("Lux", 100, me=True), player("Jinx", 200),
                                                          player("Ashe", 200)]},
    }
    for name, summary in games.items():
        (config.CAPTURE_DIR / name).mkdir(parents=True)
        (config.CAPTURE_DIR / name / "postgame.json").write_text(json.dumps(summary), encoding="utf-8")
    config.CACHE_DIR.mkdir()
    (config.CACHE_DIR / "history.json").write_text(json.dumps({
        "2": {"champ_id": "Garen", "win": True, "deaths": 5},          # the same match as "b": counted once
        "9": {"champ_id": "Malphite", "win": True, "deaths": 4}}), encoding="utf-8")
    assert champfit.record(SD) == {"Garen": {"games": 2, "wins": 1, "deaths": 8.0},
                                   "Malphite": {"games": 1, "wins": 1, "deaths": 4.0}}


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_")]
    for test_name, fn in tests:
        fn()
        print("ok  ", test_name)
    print(f"{len(tests)} passed")
