"""Read-only access to the League client (LCU) API.

The client writes a `lockfile` with its port and password while it is running. This module
only reads: the client's phase, champion select, the two teams, the queue, and the match
history. It never sends a command to the client. Every function returns None when the
client is not reachable.
"""
from __future__ import annotations

import re
from pathlib import Path

import requests
import urllib3

# The client uses a self-signed certificate on loopback, so verification is off and the warning is silenced.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_SETTINGS = Path(r"C:\ProgramData\Riot Games\Metadata\league_of_legends.live"
                 r"\league_of_legends.live.product_settings.yaml")
_DEFAULT_LOCKFILE = Path(r"C:\Riot Games\League of Legends\lockfile")


def _lockfile():
    candidates = []
    try:
        match = re.search(r'product_install_full_path:\s*"?([^"\r\n]+)"?',
                          _SETTINGS.read_text(encoding="utf-8", errors="replace"))
        if match:
            candidates.append(Path(match.group(1).strip()) / "lockfile")
    except OSError:
        pass
    candidates.append(_DEFAULT_LOCKFILE)
    return next((c for c in candidates if c.exists()), None)


def get(path: str, timeout: float = 3.0):
    """GET an LCU endpoint and return the parsed JSON, or None."""
    lockfile = _lockfile()
    if lockfile is None:
        return None
    try:
        _name, _pid, port, password, _proto = lockfile.read_text(encoding="utf-8").strip().split(":")[:5]
        # The client uses a self-signed certificate on loopback, so verification is off.
        resp = requests.get(f"https://127.0.0.1:{port}{path}", auth=("riot", password),
                            verify=False, timeout=timeout)
        return resp.json() if resp.status_code == 200 else None
    except (OSError, ValueError, requests.RequestException):
        return None


def install_dir():
    """Folder League is installed in, or None when the client is not running."""
    lockfile = _lockfile()
    return lockfile.parent if lockfile else None


def phase():
    """Client state: "None", "Lobby", "ChampSelect", "GameStart", "InProgress", "EndOfGame" and others."""
    return get("/lol-gameflow/v1/gameflow-phase", timeout=2)


def champ_select():
    """In champion select: (my champion number, [teammates' champion numbers]). None when no champion is set."""
    session = get("/lol-champ-select/v1/session", timeout=2)
    if not session:
        return None
    cell = session.get("localPlayerCellId")
    mine, mates = 0, []
    for p in session.get("myTeam") or []:
        key = p.get("championId") or 0
        if p.get("cellId") == cell:
            mine = key
        elif key:
            mates.append(key)
    return (mine, mates) if mine else None


_PRIVATE = ("puuid", "summonerid", "gamename", "tagline", "internalname", "chatdetails", "jwt")


def _scrub(node):
    """Copy of a client payload without other players' identities or chat credentials."""
    if isinstance(node, dict):
        return {k: _scrub(v) for k, v in node.items() if not any(word in k.lower() for word in _PRIVATE)}
    if isinstance(node, list):
        return [_scrub(v) for v in node]
    return node


def champ_options():
    """What the player can choose from in champion select, or None outside it.

    ARAM gives each player two champion cards (sometimes three); the ones not taken go to a
    bench the whole team can swap from. Returns {mine, mates, bench, cards, phase, raw}:
    champion numbers, the timer phase, and the session itself with identities removed.

    `benchChampions` is a field of the session. The cards are taken from the client's
    "subset champion list", which its own type definitions tie to the session flag
    `allowSubsetChampionPicks`. That reading comes from the definitions, not from a watched
    champion select, so `raw` is kept to check it against a real one. Cards are reported
    only while the choice between them is still open: once one of them is on the bench or
    with a teammate, or the player holds a champion that was not a card, the bench is the
    whole list.
    """
    session = get("/lol-champ-select/v1/session", timeout=2)
    if not isinstance(session, dict):
        return None
    cell = session.get("localPlayerCellId")
    mine, mates = 0, []
    for p in session.get("myTeam") or []:
        key = p.get("championId") or 0
        if p.get("cellId") == cell:
            mine = key
        elif key:
            mates.append(key)
    bench = [b.get("championId") for b in session.get("benchChampions") or []
             if isinstance(b, dict) and b.get("championId")]
    subset = get("/lol-lobby-team-builder/champ-select/v1/subset-champion-list", timeout=2) \
        if session.get("allowSubsetChampionPicks") else None
    subset = [c for c in subset if isinstance(c, int) and c > 0] if isinstance(subset, list) else []
    chosen = any(c in bench or c in mates for c in subset) or bool(mine and mine not in subset)
    raw = _scrub(session)
    raw["subsetChampionList"] = subset
    return {"mine": mine, "mates": mates, "bench": bench,
            "cards": [] if chosen or len(subset) > 6 else [c for c in subset if c != mine],
            "phase": (session.get("timer") or {}).get("phase"), "raw": raw}


def match_history(count: int = 40):
    """The player's most recent matches from the client, newest first, or None.

    Each entry holds the match's id, mode and length, and the player's own champion and stats.
    """
    data = get(f"/lol-match-history/v1/products/lol/current-summoner/matches?begIndex=0&endIndex={count - 1}",
               timeout=10)
    games = ((data or {}).get("games") or {}).get("games") if isinstance(data, dict) else None
    return games if isinstance(games, list) else None


def match_teams():
    """Once a match is starting: (my champion number, [allies], [enemies]). None when unavailable.

    The client knows both teams from the loading screen onward, before the game API is up.
    """
    game = (get("/lol-gameflow/v1/session", timeout=2) or {}).get("gameData") or {}
    me = get("/lol-summoner/v1/current-summoner", timeout=2) or {}
    teams = [game.get("teamOne") or [], game.get("teamTwo") or []]
    for i, team in enumerate(teams):
        for p in team:
            same = (me.get("puuid") and p.get("puuid") == me["puuid"]) or \
                   (me.get("summonerId") and p.get("summonerId") == me["summonerId"])
            if same and p.get("championId"):
                allies = [q["championId"] for q in team if q is not p and q.get("championId")]
                enemies = [q["championId"] for q in teams[1 - i] if q.get("championId")]
                return p["championId"], allies, enemies
    return None


def current_game_id():
    """The client's numeric id for the match in progress, or None."""
    game = (get("/lol-gameflow/v1/session", timeout=2) or {}).get("gameData") or {}
    return game.get("gameId") or None


def finished_game(game_id: int):
    """Full post-game record of a finished match from the client's match history, or None.

    It lists every player with champion, score, damage, healing, items and augments. The
    record appears some seconds after the match ends.
    """
    game = get(f"/lol-match-history/v1/games/{game_id}", timeout=10)
    return game if isinstance(game, dict) and game.get("participants") else None


def timeline(game_id: int):
    """Minute-by-minute record of a finished match, or None: every kill with its time and map position.

    The client keeps only the player's last 40 matches, so the coach saves this after each one.
    """
    data = get(f"/lol-match-history/v1/game-timelines/{game_id}", timeout=10)
    return data if isinstance(data, dict) and data.get("frames") else None


def my_puuid():
    return (get("/lol-summoner/v1/current-summoner", timeout=3) or {}).get("puuid")


def queue_info():
    """Queue of the current game: {id, description, mode, mapId}, or None."""
    session = get("/lol-gameflow/v1/session") or {}
    queue = (session.get("gameData") or {}).get("queue") or {}
    if not queue:
        return None
    return {"id": queue.get("id"), "description": queue.get("description"), "mode": queue.get("gameMode"),
            "mapId": queue.get("mapId")}
