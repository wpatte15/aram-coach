"""Reads the game's Live Client Data API and reduces the payload to the state the coach uses."""
from __future__ import annotations

import json
import time
from pathlib import Path

import requests
import urllib3

from . import config

# The game API uses a self-signed certificate on loopback. Verification is off for it,
# so the per-request warning is silenced.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

MODE_LABELS = {"ARAM": "ARAM", "KIWI": "ARAM: Mayhem", "CHERRY": "Arena", "CLASSIC": "Summoner's Rift"}
_STAT_KEYS = ("maxHealth", "attackDamage", "abilityPower", "armor", "magicResist", "abilityHaste",
              "attackSpeed", "moveSpeed", "critChance", "lifeSteal", "omnivamp")


class LiveSource:
    """The running game. fetch() returns (payload, status), where payload is None without a game."""
    capture = True

    def fetch(self):
        try:
            resp = requests.get(config.LIVE_URL, verify=False, timeout=1.5)
        except requests.RequestException:
            return None, "waiting"
        try:
            data = resp.json() if resp.status_code == 200 else None
        except ValueError:
            data = None
        if not isinstance(data, dict) or "allPlayers" not in data:
            return None, "loading"       # the API answers with an error object on the loading screen
        return data, "live"


class ReplaySource:
    """Replays captured payloads: one JSON file, or a folder of them stepped through in name order."""
    capture = False

    def __init__(self, path: str, step_seconds: float = 3.0):
        p = Path(path)
        self.files = sorted(p.glob("*.json")) if p.is_dir() else [p]
        if not self.files or not self.files[0].exists():
            raise FileNotFoundError(f"No payload found at {path}")
        self.step = step_seconds
        self.started = time.time()

    def fetch(self):
        index = min(int((time.time() - self.started) / self.step), len(self.files) - 1)
        return json.loads(self.files[index].read_text(encoding="utf-8")), "live"


def find_augment_fields(node, path: str = "", out: dict | None = None, depth: int = 0) -> dict:
    """Collect every field whose name mentions augments, wherever it sits in the payload.

    The API's augment support in ARAM: Mayhem is undocumented, so this looks for it by name.
    """
    if out is None:
        out = {}
    if isinstance(node, dict):
        for key, value in node.items():
            here = f"{path}.{key}" if path else key
            if "augment" in key.lower():
                out[here] = value
            elif depth < 6:
                find_augment_fields(value, here, out, depth + 1)
    elif isinstance(node, list):
        for i, value in enumerate(node[:12]):
            find_augment_fields(value, f"{path}[{i}]", out, depth + 1)
    return out


def _names(obj: dict) -> set:
    return {obj[k] for k in ("riotId", "riotIdGameName", "summonerName") if obj.get(k)}


def _find_me(active: dict, raw_players: list):
    """Index of the active player in allPlayers. The full Riot ID is tried first because game names can repeat."""
    for key in ("riotId", "summonerName", "riotIdGameName"):
        mine = active.get(key)
        if mine:
            for i, p in enumerate(raw_players):
                if p.get(key) == mine:
                    return i
    return None


_BASE_STATS = (("health", "hp", "hpperlevel"), ("attack damage", "attackdamage", "attackdamageperlevel"),
               ("armor", "armor", "armorperlevel"), ("magic resist", "spellblock", "spellblockperlevel"))
_ITEM_FLAT = {"Health": "health", "Attack Damage": "attack damage", "Ability Power": "ability power",
              "Armor": "armor", "Magic Resist": "magic resist"}
_ITEM_PERCENT = {"Life Steal%": "life steal %", "Omnivamp%": "omnivamp %",
                 "Heal and Shield Power%": "heal and shield power %"}


def estimate_stats(base: dict, level: int, items: list, sd):
    """Estimate a player's stats from champion base stats, level, and item stat lines.

    The API reports real stats for the active player only. This covers everyone else. It leaves
    out runes, augments, and item passives (for example Rabadon's ability power multiplier), so
    treat the result as a floor, not an exact value. Returns None for an unknown champion.
    """
    if not base:
        return None
    n = max(0, level - 1)
    growth = n * (0.7025 + 0.0175 * n)           # the game's per-level stat growth curve
    est = {name: base.get(flat, 0) + base.get(per_level, 0) * growth for name, flat, per_level in _BASE_STATS}
    est["ability power"] = 0.0
    for it in items:
        stats = (sd.items.get(it["id"]) or {}).get("stats") or {}
        for key, name in _ITEM_FLAT.items():
            est[name] += stats.get(key, 0)
        for key, name in _ITEM_PERCENT.items():
            if stats.get(key):
                est[name] = est.get(name, 0) + stats[key]
    out = {name: round(value) for name, value in est.items()}
    if not base.get("attackdamageperlevel"):
        # Data Dragon 16.22 reports zero attack damage growth for every champion, so the
        # level part is missing. A real game showed about 2 per level for Thresh.
        out["attack damage (level growth not included)"] = out.pop("attack damage")
    return out


_STANDARD_SPELLS = {"flash", "mark", "dash", "ghost", "heal", "ignite", "barrier", "exhaust", "cleanse",
                    "clarity", "teleport", "smite"}


def augments_from_spells(spell_names: list, sd) -> list:
    """Augments revealed by a summoner spell slot.

    The game API does not report augments. An augment that replaces a summoner spell still
    shows in that slot under the new spell's name, which matches either an augment's name or
    a spell named in an augment's description (seen in a real game: "A Dance with Death"
    comes from the augment Totentanz).
    """
    found = []
    for spell in spell_names:
        if spell.lower() in _STANDARD_SPELLS:
            continue
        entry = sd.augment(spell) or next(
            (a for a in sd.augments_described() if spell.lower() in a["description"].lower()), None)
        if entry and entry not in found:
            found.append(entry)
    return found


def _player(p: dict, sd) -> dict:
    scores = p.get("scores") or {}
    runes = p.get("runes") or {}
    spells = p.get("summonerSpells") or {}
    items = []
    for it in p.get("items") or []:
        iid = it.get("itemID")
        known = sd.items.get(iid) or {}
        items.append({
            "id": iid,
            "name": known.get("name") or it.get("displayName") or str(iid),
            "count": it.get("count") or 1,
            "slot": it.get("slot", 0),
            "gold": known.get("total", it.get("price") or 0),
        })
    cid = sd.champ_id(p.get("championName") or "", p.get("rawChampionName") or "")
    spell_names = [s.get("displayName") for s in (spells.get("summonerSpellOne"), spells.get("summonerSpellTwo"))
                   if s and s.get("displayName")]
    return {
        "name": p.get("riotIdGameName") or p.get("summonerName") or "",
        "champion": p.get("championName") or "",
        "champ_id": cid,
        "tags": (sd.champions.get(cid) or {}).get("tags", []),
        "team": p.get("team"),
        "level": p.get("level") or 1,
        "dead": bool(p.get("isDead")),
        "respawn": int(p.get("respawnTimer") or 0),
        "kda": [scores.get("kills", 0), scores.get("deaths", 0), scores.get("assists", 0)],
        "items": items,
        "est": estimate_stats((sd.champions.get(cid) or {}).get("base"), p.get("level") or 1, items, sd),
        "item_gold": sum(i["gold"] * (1 if i["gold"] >= 500 else i["count"]) for i in items),
        "spells": spell_names,
        "augments": augments_from_spells(spell_names, sd),
        "keystone": (runes.get("keystone") or {}).get("displayName"),
        "rune_trees": [t.get("displayName") for t in (runes.get("primaryRuneTree"), runes.get("secondaryRuneTree"))
                       if t and t.get("displayName")],
    }


def _blank_player(sd, cid: str) -> dict:
    champ = sd.champions.get(cid) or {}
    return {
        "name": "", "champion": champ.get("name", cid), "champ_id": cid, "tags": champ.get("tags", []),
        "team": None, "level": 1, "dead": False, "respawn": 0, "kda": [0, 0, 0], "items": [], "item_gold": 0,
        "est": estimate_stats(champ.get("base"), 1, [], sd), "spells": [], "augments": [],
        "keystone": None, "rune_trees": [],
    }


def pregame_state(sd, mine: str, allies: list, enemies: list, mode_label: str) -> dict:
    """A snapshot for the time before the match loads, built from champion picks alone.

    It has the same shape as `summarize` returns, so the same prompt code can render it.
    Pass an empty enemy list while the enemy team is still unknown.
    """
    me = _blank_player(sd, mine)
    me.update(gold=1400, stats={}, ability_ranks={}, runes=[], resource=None)
    return {
        "ended": False, "mode": "", "mode_label": mode_label, "map": 12, "time": 0.0, "me": me,
        "allies": [_blank_player(sd, c) for c in allies],
        "enemies": [_blank_player(sd, c) for c in enemies],
        "events": [], "kills": [], "killed_me": {}, "item_ids": [], "augment_fields": {}, "queue": None,
        "scoreboard": [],
    }


def _events(raw: dict, champ_by_name: dict, now: float) -> list:
    out = []
    who = lambda name: champ_by_name.get(name, name)
    for e in ((raw.get("events") or {}).get("Events") or []):
        t = e.get("EventTime") or 0
        if now - t > 150:
            continue
        kind = e.get("EventName")
        if kind == "ChampionKill":
            assists = ", ".join(who(a) for a in e.get("Assisters") or [])
            text = f"{who(e.get('KillerName'))} killed {who(e.get('VictimName'))}" + (f" (assists: {assists})" if assists else "")
        elif kind == "Multikill":
            text = f"{who(e.get('KillerName'))} got a {e.get('KillStreak')}-kill streak"
        elif kind == "Ace":
            text = f"{who(e.get('Acer'))} finished off the last enemy alive (ace)"
        elif kind in ("TurretKilled", "InhibKilled"):
            text = f"{who(e.get('KillerName'))} destroyed a {'turret' if kind == 'TurretKilled' else 'inhibitor'}"
        else:
            continue
        out.append({"time": int(t), "text": text})
    return out[-10:]


def _deaths_by_enemy(raw: dict, active: dict, champ_by_name: dict, enemy_champs: set) -> dict:
    """Whole-game count of which enemies killed, or helped kill, the player: {champion: {kills, assists}}.

    The API reports no damage numbers, so this is the most direct evidence of who is hurting the player.
    """
    mine = _names(active)
    tally = {}
    for e in ((raw.get("events") or {}).get("Events") or []):
        if e.get("EventName") != "ChampionKill" or e.get("VictimName") not in mine:
            continue
        credits = [(e.get("KillerName"), "kills")] + [(a, "assists") for a in e.get("Assisters") or []]
        for name, kind in credits:
            champ = champ_by_name.get(name)
            if champ in enemy_champs:
                tally.setdefault(champ, {"kills": 0, "assists": 0})[kind] += 1
    return tally


def _kills(raw: dict, raw_players: list, players: list, active: dict) -> list:
    """Every champion kill so far, oldest first: {time, victim, victim_team, killer, me}.

    `me` marks the player's own deaths. A victim is identified by team and champion, which is
    unique: both teams can hold the same champion, but one team cannot hold it twice.
    """
    by_name = {}
    for rp, p in zip(raw_players, players):
        for name in _names(rp):
            by_name[name] = p
    mine = _names(active)
    out = []
    for e in ((raw.get("events") or {}).get("Events") or []):
        if e.get("EventName") != "ChampionKill":
            continue
        victim, killer = by_name.get(e.get("VictimName")), by_name.get(e.get("KillerName"))
        out.append({"time": e.get("EventTime") or 0.0,
                    "victim": victim["champion"] if victim else "", "victim_team": victim["team"] if victim else None,
                    "killer": killer["champion"] if killer else "",      # empty for a turret or minion
                    "me": e.get("VictimName") in mine})
    return sorted(out, key=lambda k: k["time"])


def summarize(raw: dict, sd) -> dict:
    """Reduce an allgamedata payload to the fields the coach reasons about."""
    active = raw.get("activePlayer") or {}
    game = raw.get("gameData") or {}
    raw_players = raw.get("allPlayers") or []
    players = [_player(p, sd) for p in raw_players]

    me_index = _find_me(active, raw_players)
    me = None
    if me_index is not None:
        me = players[me_index]
        stats = active.get("championStats") or {}
        me["gold"] = int(active.get("currentGold") or 0)
        me["level"] = active.get("level") or me["level"]
        me["stats"] = {k: round(stats[k], 2 if k in ("attackSpeed", "critChance", "lifeSteal", "omnivamp") else 0)
                       for k in _STAT_KEYS if isinstance(stats.get(k), (int, float))}
        me["resource"] = stats.get("resourceType")
        me["ability_ranks"] = {k: (v or {}).get("abilityLevel", 0)
                               for k, v in (active.get("abilities") or {}).items() if k in "QWER"}
        me["runes"] = [r.get("displayName") for r in ((active.get("fullRunes") or {}).get("generalRunes") or [])
                       if r.get("displayName")]

    # Without an identified player (for example when spectating), fall back to the blue side as "allies".
    my_team = me["team"] if me else "ORDER"
    allies = [p for i, p in enumerate(players) if p["team"] == my_team and i != me_index]
    enemies = [p for p in players if p["team"] != my_team]

    champ_by_name = {}
    for rp, p in zip(raw_players, players):
        for name in _names(rp):
            champ_by_name[name] = p["champion"]

    mode = game.get("gameMode") or ""
    now = game.get("gameTime") or 0.0
    return {
        # The API keeps answering for a while after the match is decided.
        "ended": any(e.get("EventName") == "GameEnd" for e in ((raw.get("events") or {}).get("Events") or [])),
        "mode": mode,
        "mode_label": MODE_LABELS.get(mode, mode or "unknown mode"),
        "map": game.get("mapNumber"),
        "time": now,
        "me": me,
        "allies": allies,
        "enemies": enemies,
        "events": _events(raw, champ_by_name, now),
        "kills": _kills(raw, raw_players, players, active) if me else [],
        # Every player in the API's order, which is the scoreboard's row order within each team.
        "scoreboard": [{"team": p["team"], "champion": p["champion"], "kda": p["kda"]} for p in players],
        "killed_me": _deaths_by_enemy(raw, active, champ_by_name, {p["champion"] for p in enemies}) if me else {},
        "item_ids": [i["id"] for p in players for i in p["items"] if isinstance(i["id"], int)],
        "augment_fields": find_augment_fields(raw),
    }
