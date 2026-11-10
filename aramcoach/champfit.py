"""Ranks the champions the player can choose from in champion select.

ARAM gives each player two champion cards, and the ones not taken go to a bench the whole
team can swap from. The choice is made in seconds and a good bench champion is taken
quickly, so the ranking cannot wait for Claude. It is worked out locally from three things
prepared in advance:

- a fit table: for every champion, how easy it is for this player (1 to 5), the job it does
  on a team, and a few words of reason. Claude writes it once from the player's own
  description (`player.txt`); it is reused until that description or the champion list changes.
  Until it exists, the game's own difficulty score and class tags stand in for it;
- the player's record with each champion, from the client's match history and from the
  post-game records of matches the coach has seen;
- the jobs the rest of the team already covers.
"""
from __future__ import annotations

import hashlib
import json
import threading
from collections import Counter

from . import advisor, config, lcu, llm
from .log import log

JOBS = ("frontline", "damage", "support")
_PLURAL = {"frontline": "front-line champions", "damage": "damage dealers", "support": "supports"}
SWAP_MARGIN = 0.75           # a bench champion must beat the one in hand by this much to be worth a swap
_VERSION = 1                 # raise to discard tables written for an older request format
_lock = threading.Lock()
_building = False


def _table_path():
    return config.CACHE_DIR / "champion_fit.json"


def _history_path():
    return config.CACHE_DIR / "history.json"


def _key(sd) -> str:
    text = f"{_VERSION}|{config.player_profile()}|{','.join(sorted(sd.champions))}"
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def _read(path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


# ---- the fit table ---------------------------------------------------------

def load(sd):
    """The fit table written for the current player description, or None when there is none."""
    data = _read(_table_path())
    return data.get("champions") if data.get("key") == _key(sd) else None


def fallback(sd, cid) -> dict:
    """A rating from the game's own data, for use until Claude's table exists."""
    champ = sd.champions.get(cid) or {}
    tags, difficulty = champ.get("tags") or [], champ.get("difficulty")
    ease = max(1, min(5, 5 - (difficulty - 1) // 2)) if isinstance(difficulty, int) else 3
    job = "frontline" if "Tank" in tags or tags[:1] == ["Fighter"] else "support" if tags[:1] == ["Support"] else "damage"
    return {"ease": ease, "job": job, "why": ""}


def parse(sd, text: str) -> dict:
    """Read Claude's answer: one `id | ease | job | why` line per champion. Bad lines are skipped."""
    table = {}
    for line in text.splitlines():
        parts = [p.strip() for p in line.split("|", 3)]
        if len(parts) < 3:
            continue
        cid = parts[0] if parts[0] in sd.champions else sd.champ_id(parts[0])
        if cid is None or not parts[1].isdigit():
            continue
        job = parts[2].lower()
        table[cid] = {"ease": max(1, min(5, int(parts[1]))), "job": job if job in JOBS else fallback(sd, cid)["job"],
                      "why": parts[3][:90] if len(parts) > 3 else ""}
    return table


def build(sd) -> dict:
    """Ask Claude to rate every champion for this player, and save the table. One call, about a minute."""
    listing = "\n".join(f"{cid} | {c['name']} | {', '.join(c['tags']) or 'no class'} | difficulty {c.get('difficulty')}"
                        for cid, c in sorted(sd.champions.items()))
    text, meta = llm.run(advisor.system_prompt_file(sd, "std"), "REQUEST: champions\nCHAMPIONS:\n" + listing)
    table = parse(sd, text)
    if len(table) < 0.9 * len(sd.champions):
        raise llm.LLMError(f"Claude rated only {len(table)} of {len(sd.champions)} champions.")
    config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _table_path().write_text(json.dumps({"key": _key(sd), "champions": table}, indent=1, ensure_ascii=False),
                             encoding="utf-8")
    log("champion_fit", rated=len(table), latency=meta.get("latency"), cost=meta.get("cost"))
    return table


def ensure(sd):
    """Start writing the fit table in the background when it is missing or out of date."""
    global _building
    with _lock:
        if _building or load(sd) is not None:
            return
        _building = True

    def work():
        global _building
        try:
            build(sd)
        except Exception as exc:
            log("champion_fit_failed", error=str(exc)[:300])
        finally:
            _building = False

    threading.Thread(target=work, name="champion-fit", daemon=True).start()


# ---- the player's record ---------------------------------------------------

def refresh_history(sd):
    """Copy the player's recent matches from the client into the cache. Returns how many are known, or None."""
    games = lcu.match_history()
    if games is None:
        return None
    known, added = _read(_history_path()), 0
    for game in games:
        try:
            mine = (game.get("participants") or [{}])[0]
            stats = mine.get("stats") or {}
            cid = sd.champ_by_key.get(mine.get("championId"))
            if cid is None or (game.get("gameDuration") or 0) < 300 or game.get("gameType") == "CUSTOM_GAME":
                continue
            added += str(game["gameId"]) not in known
            known[str(game["gameId"])] = {"champ_id": cid, "win": bool(stats.get("win")),
                                          "deaths": stats.get("deaths") or 0, "mode": game.get("gameMode")}
        except (KeyError, TypeError, AttributeError):
            continue
    config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _history_path().write_text(json.dumps(known, indent=1), encoding="utf-8")
    log("history", read=len(games), known=len(known), added=added)
    return len(known)


def record(sd) -> dict:
    """The player's past results per champion: {champion id: {games, wins, deaths}}, deaths as an average."""
    games = dict(_read(_history_path()))
    for path in config.CAPTURE_DIR.glob("*/postgame.json"):
        summary = _read(path)
        me = next((p for p in summary.get("players") or [] if p.get("me")), None)
        opponents = sum(1 for p in summary.get("players") or [] if me and p.get("team") != me.get("team"))
        if me is None or not me.get("champ_id") or summary.get("minutes", 0) < 5 or opponents < 2:
            continue                      # not a real match: too short, or a custom game against nobody
        games[str(summary.get("game_id"))] = {"champ_id": me["champ_id"], "win": me["win"], "deaths": me["kda"][1]}
    out = {}
    for row in games.values():
        entry = out.setdefault(row["champ_id"], {"games": 0, "wins": 0, "deaths": 0})
        entry["games"] += 1
        entry["wins"] += bool(row["win"])
        entry["deaths"] += row["deaths"]
    for entry in out.values():
        entry["deaths"] = round(entry["deaths"] / entry["games"], 1)
    return out


# ---- ranking ---------------------------------------------------------------

def rank(sd, options: dict, table, played: dict):
    """Order the champions on offer for this player and this team.

    options: {mine, mates, bench, cards} as champion numbers (see lcu.champ_options).
    table: the fit table, or None to use the game's own difficulty scores.
    played: the player's record per champion (see record).
    Returns {rows, advice, best, swap, personal}, or None when there is nothing to choose from.
    Rows are best first: {champion, champ_id, source, ease, job, why, need, games, wins,
    deaths, score}. `source` is "yours", "card" or "bench".

    The score is the ease rating, plus up to 0.8 for champions the player has played, plus
    or minus a little for what the team needs. Ease weighs most on purpose: a champion the
    player can use beats a champion the team wants.
    """
    def fit(key):
        cid = sd.champ_by_key.get(key)
        return (table or {}).get(cid) or fallback(sd, cid)

    mates = [k for k in options["mates"] if k in sd.champ_by_key]
    team = Counter(fit(k)["job"] for k in mates)
    judge_team = len(mates) >= 2                      # before teammates have champions there is no team to read
    candidates = ([(options["mine"], "yours")] if options["mine"] else []) \
        + [(k, "card") for k in options["cards"]] + [(k, "bench") for k in options["bench"]]
    rows, seen = [], set()
    for key, source in candidates:
        cid = sd.champ_by_key.get(key)
        if cid is None or cid in seen:
            continue
        seen.add(cid)
        rating, past = fit(key), played.get(cid) or {}
        score, need = float(rating["ease"]) + 0.2 * min(past.get("games", 0), 4), ""
        if judge_team:
            if rating["job"] == "frontline" and team["frontline"] == 0:
                score, need = score + 1.0, "your team has no front line"
            elif rating["job"] == "damage" and team["damage"] < 2:
                score, need = score + 0.5, "your team is short of damage"
            elif team[rating["job"]] >= 3:
                score, need = score - 0.5, f"your team already has {team[rating['job']]} {_PLURAL[rating['job']]}"
        rows.append({"champion": sd.champions[cid]["name"], "champ_id": cid, "source": source,
                     "ease": rating["ease"], "job": rating["job"], "why": rating["why"], "need": need,
                     "games": past.get("games", 0), "wins": past.get("wins", 0), "deaths": past.get("deaths"),
                     "score": round(score, 2)})
    if not rows:
        return None
    rows.sort(key=lambda r: -r["score"])
    current = next((r for r in rows if r["source"] == "yours"), None)
    best = rows[0]
    if current and best is not current and best["score"] - current["score"] < SWAP_MARGIN:
        best = current                                 # not enough better to be worth giving up the one in hand
    if current is None:
        advice = f"Take {best['champion']}."
    elif best is current:
        advice = f"Keep {best['champion']}."
    else:
        advice = f"Swap to {best['champion']}, {'on the bench' if best['source'] == 'bench' else 'one of your cards'}."
    return {"rows": rows, "advice": advice, "best": best["champion"], "swap": best is not current and current is not None,
            "personal": table is not None}
