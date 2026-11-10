"""A built-in sample game, for trying the panel without League running.

The payload has the same shape as the game's allgamedata response. It moves through three
phases: alive, dead with gold to spend, then alive again after an enemy finishes a new item.
"""
from __future__ import annotations

import time

# champion id, level, K/D/A, items, summoner spells, main rune
_ORDER = [
    ("Lux", 9, (2, 3, 8), ["Luden's Echo", "Sorcerer's Shoes", "Amplifying Tome"], ("Flash", "Mark"), "Arcane Comet"),
    ("Garen", 9, (3, 4, 5), ["Stridebreaker", "Plated Steelcaps"], ("Flash", "Ghost"), "Conqueror"),
    ("Ashe", 8, (4, 5, 9), ["Kraken Slayer", "Berserker's Greaves"], ("Flash", "Heal"), "Lethal Tempo"),
    ("Leona", 8, (1, 5, 12), ["Locket of the Iron Solari", "Mercury's Treads"], ("Flash", "Mark"), "Aftershock"),
    ("Yasuo", 9, (5, 6, 4), ["Blade of The Ruined King", "Berserker's Greaves"], ("Flash", "Ignite"), "Lethal Tempo"),
]
_CHAOS = [
    ("Zed", 10, (9, 2, 3), ["Eclipse", "Serrated Dirk", "Ionian Boots of Lucidity"], ("Flash", "Ignite"), "Electrocute"),
    ("Soraka", 9, (0, 3, 17), ["Moonstone Renewer", "Ionian Boots of Lucidity"], ("Flash", "Mark"), "Summon Aery"),
    ("Malphite", 9, (3, 3, 10), ["Sunfire Aegis", "Plated Steelcaps"], ("Flash", "Mark"), "Grasp of the Undying"),
    ("Jinx", 9, (6, 4, 6), ["Infinity Edge", "Berserker's Greaves"], ("Flash", "Heal"), "Lethal Tempo"),
    ("Veigar", 9, (5, 3, 7), ["Rabadon's Deathcap", "Sorcerer's Shoes"], ("Flash", "Mark"), "Electrocute"),
]


class DemoSource:
    capture = False

    def __init__(self, sd):
        self.sd = sd
        self.started = time.time()

    def _items(self, names):
        out = []
        for slot, name in enumerate(names):
            item = self.sd.find_item(name)
            if item:                         # skip names that do not exist in the current patch
                out.append({"itemID": item["id"], "displayName": item["name"], "count": 1,
                            "slot": slot, "price": item["total"], "canUse": False, "consumable": False})
        return out

    def _player(self, row, team, index, elapsed):
        cid, level, kda, items, spells, keystone = row
        name = "You" if (team, index) == ("ORDER", 0) else f"{cid} player"
        dead = (team, index) == ("ORDER", 0) and 35 <= elapsed < 75
        if cid == "Malphite" and elapsed >= 75:
            items = items + ["Force of Nature"]
        return {
            "championName": self.sd.champions[cid]["name"],
            "rawChampionName": f"game_character_displayname_{cid}",
            "isBot": False, "isDead": dead, "respawnTimer": max(0.0, 75 - elapsed) if dead else 0.0,
            "items": self._items(items), "level": level, "position": "", "skinID": 0, "team": team,
            "scores": {"kills": kda[0], "deaths": kda[1] + (1 if dead or (name == "You" and elapsed >= 75) else 0),
                       "assists": kda[2], "creepScore": 30, "wardScore": 0.0},
            "summonerName": name, "riotIdGameName": name, "riotIdTagLine": "DEMO", "riotId": f"{name}#DEMO",
            "summonerSpells": {"summonerSpellOne": {"displayName": spells[0]},
                               "summonerSpellTwo": {"displayName": spells[1]}},
            "runes": {"keystone": {"displayName": keystone},
                      "primaryRuneTree": {"displayName": "Sorcery"}, "secondaryRuneTree": {"displayName": "Inspiration"}},
        }

    def fetch(self):
        elapsed = time.time() - self.started
        game_time = 450.0 + elapsed
        players = ([self._player(r, "ORDER", i, elapsed) for i, r in enumerate(_ORDER)]
                   + [self._player(r, "CHAOS", i, elapsed) for i, r in enumerate(_CHAOS)])
        events = [{"EventID": 0, "EventName": "GameStart", "EventTime": 0.0},
                  {"EventID": 1, "EventName": "ChampionKill", "EventTime": game_time - 40,
                   "KillerName": "Zed player", "VictimName": "Ashe player", "Assisters": ["Soraka player"]}]
        if elapsed >= 35:
            events.append({"EventID": 2, "EventName": "ChampionKill", "EventTime": 485.0,
                           "KillerName": "Zed player", "VictimName": "You", "Assisters": ["Malphite player"]})
        return {
            "activePlayer": {
                "summonerName": "You", "riotIdGameName": "You", "riotId": "You#DEMO", "level": 9,
                "currentGold": 950.0 + 6 * min(elapsed, 35) + (990.0 if elapsed >= 35 else 0.0),
                "abilities": {"Q": {"abilityLevel": 2}, "W": {"abilityLevel": 1},
                              "E": {"abilityLevel": 5}, "R": {"abilityLevel": 1}},
                "championStats": {"maxHealth": 1420.0, "attackDamage": 78.0, "abilityPower": 186.0, "armor": 46.0,
                                  "magicResist": 38.0, "abilityHaste": 20.0, "attackSpeed": 0.74, "moveSpeed": 375.0,
                                  "resourceType": "MANA"},
                "fullRunes": {"generalRunes": [{"displayName": n} for n in
                                               ("Arcane Comet", "Manaflow Band", "Transcendence", "Scorch")]},
            },
            "allPlayers": players,
            "events": {"Events": events},
            "gameData": {"gameMode": "ARAM", "gameTime": game_time, "mapName": "Map12", "mapNumber": 12,
                         "mapTerrain": "Default"},
        }, "live"
