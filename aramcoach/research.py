"""Research done ahead of a match: how augments, items and champion kits multiply each other.

During a match Claude answers in seconds at low effort. That is recall, not reasoning: asked
for a plan, it wrote an answer without a reasoning step in 18 of 19 recorded requests. The
working-out that finds a combination, such as which ability a per-hit augment fires on, what
an item converts and what the chain reaches, takes minutes. So it is done here, in advance,
at high effort, and kept on disk. The requests made during a match are handed the lines that
apply to them.

Two things are prepared:

- the augment map: for every augment, what it does as a mechanism, what a kit must have for
  it to pay, the items and other augments that multiply it, and when it does nothing;
- a playbook per champion: the properties of the kit a combination can run through, the
  combinations the kit supports with what each piece feeds into, and the augments this kit
  uses unusually well or cannot use.

All of it is worked out from the game's own text: ability notes, augment effects and the
item catalog. No statistics about what other players pick go in, on purpose: a tool that
shows the popular picks already exists, and the coach is for reasoning about one match.

Research is kept per patch under cache/<patch>/research/. On a new patch the files written
for the last one are still used, and the request says which patch they were written on.
Run `python -m aramcoach.research` to write them again.
"""
from __future__ import annotations

import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from . import config, itemcheck, llm
from .log import log
from .static_data import norm

VERSION = 1                   # raise to set aside research written for an older request format
MAP_BATCH = 35                # augments worked through in one request
MAX_TOKENS = 64000            # reasoning and answer together; a batch of the map is a long answer
RETRY_AFTER_FAILURE = 900     # seconds before a failed research request is tried again
KINDS = ("engine", "amplifier", "stats", "utility")
FITS = ("core", "strong", "weak")
_lock = threading.Lock()
_building = set()             # what is being written now: "map", or a champion id
_failed_at = {}
_cache = {}                   # file path -> (modification time, contents)

PREFACE = """REQUEST: research
This is preparation, done outside a match. Nobody is waiting, so reason at length before you write. The coach keeps your answer and hands the lines that apply to the requests made during a match, which have seconds to decide and no time to work anything out. What you establish here is what those requests will know.
"""

MAP_TASK = """
TASK: augments. For each augment listed below, work out how it can become a piece of a combination as described under Combinations: pieces that multiply each other. Use its effect text below, the item catalog and the augment list. Work only from those texts. What players usually pick is not evidence and must play no part. Describe mechanisms, and do not call an augment good or bad in general.

Answer with one JSON object and nothing else:
{"augments": [{"name": string, "kind": string, "does": string, "wants": string, "items": [{"name": string, "why": string}], "augments": [{"name": string, "why": string}], "dead": string}]}
Give one entry per augment listed, in the order listed, with the name exactly as listed.
- kind: one of "engine", "amplifier", "stats", "utility". An engine grows without limit or pays again each time something happens in a fight: a stack, an effect per hit or per cast, one stat converted into another. An amplifier multiplies something the champion must already have: critical strikes, on-hit effects, healing, a stat by a percentage. Stats is a fixed amount of strength that multiplies nothing. Utility is the rest: movement, gold, summoner spells, effects that happen once.
- does: one or two sentences of plain mechanism: what triggers it, what it gives, what the gain scales with, and any cap, cooldown or loss on death the text states. Keep every number.
- wants: what a champion's kit must have for this to pay several times in a fight, as properties that can be checked against ability text, such as "an ability that immobilises on a short cooldown", "many separate hits each second", "a large health pool", "abilities that deal damage over time" or "basic attacks from range". For a stats augment, say which kind of champion uses those stats.
- items: up to three items from the catalog that multiply it or that it multiplies, strongest link first, by exact catalog name, each with `why` in at most 18 words and the number or threshold reached where there is one. A link exists only where one piece's output is the other's input: more of the stat it converts, more triggers of its effect, a threshold reached, a cap lifted. An item that is merely also good on the same champions is not a link. Never list a BUTTON-ONLY item. Leave the list empty when nothing in the catalog multiplies it.
- augments: up to four other augments from the augment list with the same kind of link, by exact name, each with `why` in at most 18 words. Leave the list empty when there is none.
- dead: when it does little or nothing: the kits that never meet its condition, what is lost on death, a cap reached early. Empty when it works on any champion.
Where the text does not settle a question that matters, such as whether damage over time counts as a hit, whether an ability applies on-hit effects or whether two effects stack, write "the text does not say" in that place. Do not assume the favourable reading.

AUGMENTS TO WORK THROUGH (name | tier | full effect text):
"""

CHAMPION_TASK = """
TASK: champion. Work out what can be built on <<NAME>>'s kit in ARAM: Mayhem.

Below are the champion's abilities with their numbers, how each is cast, the coach's item checks for this champion, and the AUGMENT MAP: for every augment the mechanism, what it wants from a kit, and the items and augments that multiply it, prepared earlier in the same way as this.

Work in this order:
1. Read the kit for what a combination can run through: an ability that hits many times, applies on-hit effects, can critically strike, scales unusually steeply with one stat, stacks without limit, immobilises, has a short cooldown, heals or shields. Note what the ability text does not support as well, because many augments and items need a property this kit may lack.
2. Go through the augment map one augment at a time and hold what it wants against the kit. Do this for every augment, including the ones this champion's usual build would never suggest: the valuable finds are there.
3. Assemble combinations: an augment, the part of the kit it runs through, and the items and further augments that multiply it. Follow each chain as far as it goes, and work out with the numbers what it reaches.
What players usually build or pick on this champion is not evidence and must play no part. Where a text does not settle whether something triggers, say so in the entry and do not assume the favourable reading. A word in an effect text means what the game means by it: a silence or a slow is not an immobilising effect, and damage over time is not a hit unless the text says so.

Answer with one JSON object and nothing else:
{"hooks": [string], "lacks": [string], "combos": [{"name": string, "augments": [string], "items": [string], "kit": string, "chain": string, "reaches": string, "breaks": string}], "augments": [{"name": string, "fit": string, "why": string}]}
- hooks: up to six properties of this kit that a combination can be built on, each one sentence that names the ability and gives the number from the notes. Include the ones the usual build ignores.
- lacks: up to four properties this kit does not have that augments and items commonly need, each a short sentence, such as "no ability applies on-hit effects" or "nothing in the kit heals or shields an ally".
- combos: up to six combinations this kit supports, the one that grows furthest first. A combination has at least one augment, or two items, that multiply each other through a named part of the kit. List fewer when fewer are real: an invented link costs the player a pick.
  - name: at most four words.
  - augments: the augments that are pieces, by exact name, the one that opens it first. Empty for a combination of items alone.
  - items: the catalog items that are pieces, by exact name, in the order to buy them. Only what multiplies, not the rest of a build.
  - kit: the ability or passive it runs through.
  - chain: two or three sentences on what each piece feeds into, with the numbers.
  - reaches: the threshold or end state it reaches, in one sentence.
  - breaks: what stops it paying: an enemy answer, a condition this player may not meet, something lost on death.
  Include the strongest combination of items alone when the kit has one: it is the build before any augment arrives.
- augments: one entry for each augment whose worth on this champion is clearly different from its worth on most champions. `fit` is "core" for a piece of a combination above, "strong" when this kit meets its condition unusually often or turns its stat into unusually much, and "weak" when this kit cannot meet its condition or the augment works against how this champion fights. `why` is at most 22 words and names the ability or the missing property. Leave out every augment that is none of these: no entry means its worth here is ordinary.
"""


def _key(name) -> str:
    """How a name is compared. The game lists some quests twice, as "Steel Your Heart" and "Quest: Steel Your Heart"."""
    return norm(re.sub(r"^\s*quest\s*:", "", str(name), flags=re.I))


# ---- reading what is saved --------------------------------------------------

def _folder(sd):
    return sd.dir / "research"


def _newest(sd, name: str):
    """The saved file for this patch, or failing that the one written most recently for an earlier patch."""
    path = _folder(sd) / name
    if path.exists():
        return path
    older = sorted(config.CACHE_DIR.glob(f"*/research/{name}"), key=lambda p: p.stat().st_mtime)
    return older[-1] if older else None


def _load(sd, name: str):
    path = _newest(sd, name)
    if path is None:
        return None
    try:
        info = path.stat()
        # Time and size: a file written twice within one tick of the clock keeps its time, and was read as unchanged.
        stamp = (info.st_mtime_ns, info.st_size)
        if _cache.get(str(path), (None, None))[0] != stamp:
            data = json.loads(path.read_text(encoding="utf-8"))
            _cache[str(path)] = (stamp, data if isinstance(data, dict) and data.get("version") == VERSION else None)
        return _cache[str(path)][1]
    except (OSError, ValueError):
        return None


def augment_map(sd):
    """The saved augment map: {patch, augments: {normalised name: row}}, or None. Turned off, always None."""
    return _load(sd, "augments.json") if config.RESEARCH != "0" else None


def playbook(sd, champ_id: str):
    """The saved playbook for one champion, or None."""
    return _load(sd, f"champion_{champ_id}.json") if config.RESEARCH != "0" and champ_id else None


def _save(sd, name: str, data: dict):
    path = _folder(sd) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")


# ---- checking Claude's answers ----------------------------------------------

def _text(value, limit: int = 400) -> str:
    return re.sub(r"\s+", " ", value).strip()[:limit] if isinstance(value, str) else ""


def _augment_name(sd, name):
    """The augment's own name as the coach knows it, or None when there is no such augment."""
    if not isinstance(name, str):
        return None
    entry = sd.augment(name) or sd.augment(re.sub(r"^\s*quest\s*:\s*", "", name, flags=re.I))
    return entry["name"] if entry and entry["name"] else None


def _item_names(sd) -> dict:
    return {_key(it["name"]): it for it in sd.catalog("std")}


def _links(found, resolve, limit: int) -> list:
    """Read [{name, why}], keeping only names that exist. A bare name is accepted too."""
    out, seen = [], set()
    for entry in found if isinstance(found, list) else []:
        name = resolve(entry.get("name") if isinstance(entry, dict) else entry)
        if name and name not in seen:
            seen.add(name)
            out.append({"name": name, "why": _text(entry.get("why"), 200) if isinstance(entry, dict) else ""})
    return out[:limit]


def clean_map(sd, raw: dict) -> dict:
    """Read one answer to the augment task: {normalised name: row}. Names the game does not have are dropped."""
    items = _item_names(sd)

    def usable(name):                             # an item in the catalog that works without its button
        it = items.get(_key(name)) if isinstance(name, str) else None
        return it["name"] if it and not it["button_only"] else None

    rows = {}
    for entry in raw.get("augments") if isinstance(raw.get("augments"), list) else []:
        name = _augment_name(sd, entry.get("name")) if isinstance(entry, dict) else None
        if not name or not _text(entry.get("does")):
            continue
        kind = _text(entry.get("kind")).lower()
        rows[_key(name)] = {
            "name": name, "kind": kind if kind in KINDS else "utility",
            "does": _text(entry.get("does"), 500), "wants": _text(entry.get("wants"), 300),
            "items": _links(entry.get("items"), usable, 3),
            "augments": [link for link in _links(entry.get("augments"), lambda n: _augment_name(sd, n), 4)
                         if _key(link["name"]) != _key(name)],
            "dead": _text(entry.get("dead"), 300),
        }
    return rows


def clean_playbook(sd, champ_id: str, raw: dict) -> dict:
    """Read one answer to the champion task. Unknown names are dropped, and so is an item the item checks rule out."""
    items = _item_names(sd)
    rejected = itemcheck.rejected(sd, champ_id, sd.catalog("std"))
    strings = lambda key, limit: [_text(s, 320) for s in (raw.get(key) if isinstance(raw.get(key), list) else [])
                                  if _text(s)][:limit]

    def names(found, resolve):
        out = []
        for name in found if isinstance(found, list) else []:
            real = resolve(name)
            if real and real not in out:
                out.append(real)
        return out

    def item(name):
        it = items.get(_key(name)) if isinstance(name, str) else None
        return it["name"] if it and it["id"] not in rejected else None

    group = {name: passive for passive, members in sd.exclusive_groups("std").items() for name in members}

    def one_per_group(found: list) -> list:      # two Spellblade items give one Spellblade effect: keep the first
        out, taken = [], set()
        for name in found:
            if group.get(name) not in taken:
                out.append(name)
                taken.add(group.get(name, name))
        return out

    combos = []
    for entry in raw.get("combos") if isinstance(raw.get("combos"), list) else []:
        if not isinstance(entry, dict) or not _text(entry.get("name")) or not _text(entry.get("chain")):
            continue
        combo = {"name": _text(entry.get("name"), 40), "augments": names(entry.get("augments"), lambda n: _augment_name(sd, n)),
                 "items": one_per_group(names(entry.get("items"), item)), "kit": _text(entry.get("kit"), 160),
                 "chain": _text(entry.get("chain"), 700), "reaches": _text(entry.get("reaches"), 300),
                 "breaks": _text(entry.get("breaks"), 300)}
        if combo["augments"] or len(combo["items"]) >= 2:      # a combination has pieces that exist
            combos.append(combo)
    combos = combos[:6]
    rows = {}
    for entry in raw.get("augments") if isinstance(raw.get("augments"), list) else []:
        name = _augment_name(sd, entry.get("name")) if isinstance(entry, dict) else None
        fit = _text(entry.get("fit")).lower() if isinstance(entry, dict) else ""
        if name and fit in FITS and _text(entry.get("why")):
            rows[_key(name)] = {"name": name, "fit": fit, "why": _text(entry.get("why"), 240)}
    for combo in combos:                         # a piece of a listed combination is core, whatever its own row said
        for name in combo["augments"]:
            row = rows.setdefault(_key(name), {"name": name, "fit": "core", "why": f"a piece of {combo['name']}"})
            if row["fit"] != "core":
                row["fit"] = "core"
    return {"hooks": strings("hooks", 6), "lacks": strings("lacks", 4), "combos": combos, "augments": rows}


# ---- asking -----------------------------------------------------------------

def _parse(text: str) -> dict:
    start, end = text.find("{"), text.rfind("}")
    try:
        obj = json.loads(text[start: end + 1]) if start >= 0 and end > start else None
    except ValueError:
        obj = None
    if not isinstance(obj, dict):
        raise llm.LLMError("Claude's research answer was not the expected JSON.")
    return obj


def _ask(sd, prompt: str, on_start=None):
    from . import advisor                         # imported here: advisor itself imports this module
    text, meta = llm.run(advisor.system_prompt_file(sd, "std"), prompt, effort=config.RESEARCH_EFFORT,
                         on_start=on_start, max_tokens=MAX_TOKENS)
    return _parse(text), meta


def _run_many(jobs: list, workers: int = 3, each=None) -> list:
    """Run paid requests side by side and return each one's result, or the exception it raised.

    The first is given a head start: on a prompt the API does not hold in its cache, requests
    sent together each pay to write it. The rest wait until the first has begun to be answered.
    each: optional callback given every result as it is collected, in the order the jobs were
    listed, so that finished work can be saved before the rest is done.
    """
    begun = threading.Event()

    def one(index):
        if index:
            begun.wait(timeout=120)
        try:
            return jobs[index](begun.set if index == 0 else None)
        finally:
            begun.set()                           # never leave the others waiting on a request that failed

    out = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for future in [pool.submit(one, i) for i in range(len(jobs))]:
            try:
                result = future.result()
            except Exception as exc:
                result = exc
            if each is not None:
                each(result)
            out.append(result)
    return out


def map_request(augments: list) -> str:
    return PREFACE + MAP_TASK + "\n".join(f"{a['name']} | {a['tier']} | {a['description']}" for a in augments)


def map_missing(sd) -> list:
    """The described augments the map saved for this patch does not have, one per augment."""
    rows = ((_load(sd, "augments.json") or {}).get("augments") or {}) if (_folder(sd) / "augments.json").exists() else {}
    out, seen = [], set()
    for a in sorted(sd.augments_described(), key=lambda a: a["name"]):
        if _key(a["name"]) not in rows and _key(a["name"]) not in seen:
            seen.add(_key(a["name"]))
            out.append(a)
    return out


def build_map(sd, only=None, fresh: bool = False, workers: int = 3) -> dict:
    """Work through the augments and save the map. Returns {augments, written, missing, cost, latency}.

    Without arguments it does the augments the map saved for this patch does not have yet: all
    of them the first time, and the rest after a run that was cut short. only: augment names to
    do again. fresh: do every augment again. The map is saved after every answer, so a failure
    part of the way loses nothing that was paid for. The whole map is about seven requests at
    high effort.
    """
    here = (_folder(sd) / "augments.json").exists()
    rows = {} if fresh or not here else dict((_load(sd, "augments.json") or {}).get("augments") or {})
    if only:
        keep = {_key(_augment_name(sd, n) or "") for n in only}
        wanted = [a for a in sorted(sd.augments_described(), key=lambda a: a["name"]) if _key(a["name"]) in keep]
    elif fresh:
        wanted = sorted({_key(a["name"]): a for a in sd.augments_described()}.values(), key=lambda a: a["name"])
    else:
        wanted = map_missing(sd)
    started, cost, done = time.time(), 0.0, set()

    def each(result):
        nonlocal cost
        if isinstance(result, Exception):
            log("research_failed", what="augment map", error=str(result)[:300])
            return
        raw, meta = result
        cost += meta.get("cost") or 0.0
        found = clean_map(sd, raw)
        rows.update(found)
        done.update(found)
        _save(sd, "augments.json", {"version": VERSION, "patch": sd.version, "made": time.strftime("%Y-%m-%d %H:%M"),
                                    "augments": rows})

    def run(augments):
        batches = [augments[i: i + MAP_BATCH] for i in range(0, len(augments), MAP_BATCH)]
        _run_many([lambda on_start, b=b: _ask(sd, map_request(b), on_start) for b in batches], workers, each)

    run(wanted)
    missing = [a for a in wanted if _key(a["name"]) not in done]
    if missing and done:                          # an answer left some out, or one request failed: ask once more
        run(missing)
        missing = [a for a in wanted if _key(a["name"]) not in done]
    if wanted and not done:
        raise llm.LLMError("No part of the augment map could be written.")
    result = {"augments": len(rows), "written": len(done), "missing": [a["name"] for a in missing],
              "cost": round(cost, 3), "latency": round(time.time() - started, 1)}
    log("research", what="augment map", **result)
    return result


def _map_line(row: dict, tier: str) -> str:
    parts = [row["name"], tier, row["kind"], row["does"], f"wants: {row['wants']}" if row["wants"] else ""]
    if row["items"]:
        parts.append("multiplied by items: " + "; ".join(f"{i['name']} ({i['why']})" for i in row["items"]))
    if row["augments"]:
        parts.append("by augments: " + "; ".join(f"{a['name']} ({a['why']})" for a in row["augments"]))
    if row["dead"]:
        parts.append(f"dead when: {row['dead']}")
    return " | ".join(p for p in parts if p)


def champion_request(sd, champ_id: str) -> str:
    """Everything the champion task reads: the kit, the item checks and the augment map."""
    from . import champfit                        # imported here: champfit imports advisor, which imports this module
    champ = sd.champions[champ_id]
    notes = sd.champion_notes(champ_id)
    if not notes:
        raise llm.LLMError(f"No ability notes for {champ['name']}.")
    reach = (champ.get("base") or {}).get("attackrange")
    out = [PREFACE + CHAMPION_TASK.replace("<<NAME>>", champ["name"]),
           f"CHAMPION: {champ['name']} ({', '.join(champ['tags']) or 'no class'})"
           + (f" | attack range {reach:g} ({'melee' if reach <= 300 else 'ranged'})" if reach else "")
           + (f" | resource: {champ['resource']}" if champ.get("resource") else "")]
    liked = champfit.favourites(sd).get(champ_id)
    out.append("  familiarity: " + (f"the player says they {liked} playing this champion and know how it works" if liked
                                    else "not one of the champions the player says they know"))
    out.append(f"  {notes['passive']}")
    out += [f"  {s}" for s in notes["spells"]]
    casts = sd.how_cast(champ_id)
    if casts:
        out.append("  how each ability is cast and what it does in detail:")
        out += [f"    {slot}: {casts[slot]['text']}" for slot in "PQWER" if slot in casts]
    checks = itemcheck.facts(sd, champ_id, sd.catalog("std"))
    if checks:
        out.append("  ITEM CHECKS (worked out by the coach from this kit and the player's profile):")
        out += [f"    {line}" for line in checks]
    known = (augment_map(sd) or {}).get("augments") or {}
    if known:
        tiers = {_key(a["name"]): a["tier"] for a in sd.augments_described()}
        out += ["", "AUGMENT MAP (name | tier | kind | what it does | what it wants from a kit | what multiplies it | when it is dead):"]
        out += [_map_line(row, tiers.get(key, "")) for key, row in sorted(known.items()) if key in tiers]
    else:
        out += ["", "There is no augment map yet. Work from the augment list in your instructions."]
    return "\n".join(out)


def build_champion(sd, champ_id: str, on_start=None) -> dict:
    """Write the playbook for one champion and save it. One request at high effort. Returns the playbook."""
    raw, meta = _ask(sd, champion_request(sd, champ_id), on_start)
    book = clean_playbook(sd, champ_id, raw)
    if not book["combos"] and not book["augments"]:
        raise llm.LLMError(f"The playbook for {champ_id} came back empty.")
    book = {"version": VERSION, "patch": sd.version, "made": time.strftime("%Y-%m-%d %H:%M"),
            "champion": sd.champions[champ_id]["name"], "cost": meta.get("cost"), "latency": meta.get("latency"), **book}
    _save(sd, f"champion_{champ_id}.json", book)
    log("research", what=f"playbook {champ_id}", combos=len(book["combos"]), augments=len(book["augments"]),
        cost=meta.get("cost"), latency=meta.get("latency"))
    return book


def build_champions(sd, champ_ids: list, workers: int = 3) -> list:
    """Write several playbooks side by side. Returns [(champion id, playbook or the exception)]."""
    jobs = [lambda on_start, cid=cid: build_champion(sd, cid, on_start) for cid in champ_ids]
    return list(zip(champ_ids, _run_many(jobs, workers)))


def ensure(sd, champ_id: str | None = None):
    """Write what is missing, in the background: the augment map, then this champion's playbook.

    Called when a champion is picked. Research written for an earlier patch counts as present,
    so a new patch never starts paid work by itself. Does nothing unless ARAMCOACH_RESEARCH is 1.
    """
    if config.RESEARCH != "1":
        return
    need_map = augment_map(sd) is None
    need_book = bool(champ_id) and champ_id in sd.champions and playbook(sd, champ_id) is None
    job = champ_id if need_book else "map" if need_map else None
    with _lock:
        busy = job in _building or (need_map and "map" in _building)
        if job is None or busy or time.time() - _failed_at.get(job, 0) < RETRY_AFTER_FAILURE:
            return
        _building.add(job)
        if need_map:
            _building.add("map")

    def work():
        try:
            if need_map:
                build_map(sd)
            if need_book:
                build_champion(sd, champ_id)
        except Exception as exc:
            _failed_at[job] = time.time()        # each attempt is paid: do not repeat it every few seconds
            log("research_failed", what=job, error=str(exc)[:300])
        finally:
            with _lock:
                _building.discard(job)
                if need_map:
                    _building.discard("map")

    threading.Thread(target=work, name="research", daemon=True).start()


# ---- as lines for a request --------------------------------------------------

def _held(state: dict) -> tuple:
    me = state.get("me") or {}
    return ({_key(n) for n in state.get("my_augments") or []}, {_key(i["name"]) for i in me.get("items") or []})


def _written_on(sd, data: dict) -> str:
    return "" if data.get("patch") == sd.version else f", written on patch {data.get('patch') or '?'}"


def matters(sd, champ_id, name: str) -> bool:
    """Whether taking this augment is a reason to remake the build, as far as the research knows.

    With a playbook: only an augment it calls core or strong on this kit. An augment with no
    entry there is worth what it is worth on any champion, which is no reason to change items.
    Without a playbook: an augment the map calls an engine or an amplifier. An augment the
    research does not know, or with research turned off, counts as mattering, as before.
    Stat shards never do. In one match five augments brought five remakes, and each changed
    one to three of the items the player was working toward.
    """
    if re.search(r"\bShard$", name.strip()):
        return False
    book, chart = playbook(sd, champ_id), augment_map(sd)
    real = _augment_name(sd, name) or name
    if book:
        return (book["augments"].get(_key(real)) or {}).get("fit") in ("core", "strong")
    row = ((chart or {}).get("augments") or {}).get(_key(real))
    return row is None or row["kind"] in ("engine", "amplifier")


def _general(sd, state: dict, name: str, known: dict, with_items: bool = True) -> str:
    """What the augment map says about one augment, with the pieces the player holds marked.

    with_items: list the items the map links to the augment. Left out when the champion has a
    playbook. The map's links hold on any champion and say nothing of this champion's job: a
    front-line Volibear was told to buy Blade of The Ruined King because it multiplies BEES!!!.
    The playbook's combinations are where items for this kit come from.
    """
    row = known.get(_key(name))
    if not row:
        return ""
    augments, items = _held(state)
    mark = lambda n, held, word: f"{n} [{word}]" if _key(n) in held else n
    because = lambda why: f" ({why.rstrip('.')})" if why else ""
    parts = [f"Wants: {row['wants'][:1].lower() + row['wants'][1:]}"] if row["wants"] else []
    if row["items"] and with_items:
        parts.append("Items that multiply it: " + "; ".join(
            mark(i["name"], items, "OWNED") + because(i["why"]) for i in row["items"]))
    links = {a["name"]: a["why"] for a in row["augments"]}
    for other in known.values():                 # a link written from the other side counts as well
        for back in other["augments"]:
            if _key(back["name"]) == _key(row["name"]):
                links.setdefault(other["name"], back["why"])
    links.pop(row["name"], None)
    if links:
        ordered = sorted(links, key=lambda n: _key(n) not in augments)        # the ones held come first
        parts.append("Augments it compounds with: " + "; ".join(
            mark(n, augments, "HELD") + because(links[n]) for n in ordered[:4]))
    if row["dead"]:
        parts.append(f"Does little when: {row['dead'][:1].lower() + row['dead'][1:]}")
    return " ".join(part.rstrip(".") + "." for part in parts)


def plan_lines(sd, state: dict, ahead: bool = False) -> list:
    """The prepared research that applies to this player's champion and augments, as lines for a request.

    A combination is opened when the player holds one of its augments. During a match the
    items and the chain of one that is not opened are left out: in the first real match with
    a playbook, a plan bought Imperial Mandate out of a combination whose five augments the
    player held none of. ahead: the request is made in champion select, where every
    combination is given in full because the item set has to hold the items for each.
    """
    me = state.get("me")
    if not me or not me.get("champ_id"):
        return []
    book, chart = playbook(sd, me["champ_id"]), augment_map(sd)
    known = (chart or {}).get("augments") or {}
    mine = [n for n in state.get("my_augments") or []]
    if not book and not (known and mine):
        return []
    augments, items = _held(state)
    out = []
    if book:
        out.append(f"PREPARED RESEARCH ON {me['champion'].upper()} (your own earlier working from the ability, augment and "
                   f"item text, done at length before this match{_written_on(sd, book)}; it has not seen this match):")
        if book["hooks"] or book["lacks"]:
            out.append("  What a combination can run through on this kit:")
            out += [f"    + {h}" for h in book["hooks"]] + [f"    - {l}" for l in book["lacks"]]
        if book["combos"]:
            def full(n, c):
                pieces = []
                if c["augments"]:
                    pieces.append("augments " + ", ".join(f"{a} [HELD]" if _key(a) in augments else a for a in c["augments"]))
                if c["items"]:
                    pieces.append("items " + ", ".join(f"{i} [OWNED]" if _key(i) in items else i for i in c["items"]))
                return [f"    {n}. {c['name']}: {'; '.join(pieces)}" + (f"; through {c['kit']}" if c["kit"] else "") + ".",
                        f"       {c['chain']}" + (f" Reaches: {c['reaches']}" if c["reaches"] else "")
                        + (f" Breaks: {c['breaks']}" if c["breaks"] else "")]

            usable = [c for c in book["combos"] if not c["augments"] or any(_key(a) in augments for a in c["augments"])]
            waiting = [c for c in book["combos"] if c not in usable]
            if ahead:
                out.append("  Combinations this kit supports, the one that grows furthest first. The build is made from the ones "
                           "that need no augment. The items of the others belong in `augment_builds`, not in the build:")
                for n, c in enumerate(book["combos"], 1):
                    out += full(n, c)
            else:
                if usable:
                    out.append("  Combinations whose pieces can be bought now, because the player holds one of their augments or "
                               "they need none ([HELD] and [OWNED] mark what the player has):")
                    for n, c in enumerate(usable, 1):
                        out += full(n, c)
                if waiting:
                    out.append("  Combinations not opened: the player holds none of their augments. Each is something to hope "
                               "for at an offer, and nothing is bought toward one before it is opened:")
                    out += [f"    - {c['name']}: opens with {', '.join(c['augments'])}"
                            + (f"; through {c['kit']}" if c["kit"] else "") + "."
                            + (f" Reaches: {c['reaches']}" if c["reaches"] else "") for c in waiting]
    elif known:
        out.append(f"PREPARED RESEARCH (your own earlier working from the augment and item text, done at length before this "
                   f"match{_written_on(sd, chart)}; there is none on {me['champion']}'s kit yet):")
    if mine:
        out.append("  The augments the player holds:")
        for name in mine:
            real = _augment_name(sd, name) or name
            row = ((book or {}).get("augments") or {}).get(_key(real))
            parts = [f"{row['fit']} on this kit: {row['why'].rstrip('.')}."] if row else []
            general = _general(sd, state, real, known, with_items=not book)
            if general:
                parts.append("On any champion: " + general)
            if parts:
                out.append(f"    {name}: " + " ".join(parts))
    return out if len(out) > 1 else []


def card_lines(sd, state: dict, names: list) -> list:
    """What the prepared research says about each augment on offer, as lines for an offer request."""
    me = state.get("me")
    if not me or not names:
        return []
    book, chart = playbook(sd, me.get("champ_id")), augment_map(sd)
    known = (chart or {}).get("augments") or {}
    if not book and not known:
        return []
    augments, _ = _held(state)
    out = ["WHAT THE PREPARED RESEARCH SAYS ABOUT THE CARDS ON OFFER"
           + ("" if book else f" (there is none on {me['champion']}'s kit yet, so only what holds on any champion)") + ":"]
    for name in names:
        real = _augment_name(sd, name) or name
        parts = []
        row = ((book or {}).get("augments") or {}).get(_key(real))
        if row:
            parts.append(f"{row['fit']} on {me['champion']}: {row['why'].rstrip('.')}.")
            for c in (book or {}).get("combos") or []:
                if _key(real) in {_key(a) for a in c["augments"]}:
                    others = [f"{a} [HELD]" if _key(a) in augments else a for a in c["augments"] if _key(a) != _key(real)]
                    parts.append(f"A piece of \"{c['name']}\"" + (f", with {', '.join(others)}" if others else "") + ".")
        elif book and _key(real) in known:       # a card the research never saw, such as a stat shard, gets no line
            parts.append(f"no entry for {me['champion']}: its worth here is ordinary, so judge it from its text.")
        general = _general(sd, state, real, known, with_items=not book)
        if general:
            parts.append("On any champion: " + general)
        if parts:
            out.append(f"  {name}: " + " ".join(parts))
    return out if len(out) > 1 else []


# ---- command line -----------------------------------------------------------

def show(sd, champ_id: str) -> str:
    """One champion's playbook as readable text."""
    book = playbook(sd, champ_id)
    if not book:
        return f"No playbook for {champ_id}."
    out = [f"{book['champion']} (patch {book['patch']}, written {book['made']})", "Hooks:"]
    out += [f"  + {h}" for h in book["hooks"]] + [f"  - {l}" for l in book["lacks"]] + ["Combinations:"]
    for c in book["combos"]:
        out += [f"  {c['name']}: augments [{', '.join(c['augments'])}] items [{', '.join(c['items'])}] through {c['kit']}",
                f"    {c['chain']}", f"    Reaches: {c['reaches']}", f"    Breaks: {c['breaks']}"]
    for fit in FITS:
        rows = [r for r in book["augments"].values() if r["fit"] == fit]
        out.append(f"{fit.capitalize()} augments ({len(rows)}):")
        out += [f"  {r['name']}: {r['why']}" for r in sorted(rows, key=lambda r: r["name"])]
    return "\n".join(out)


def main(argv: list) -> int:
    """python -m aramcoach.research [--map] [--force] [--show] [champion ...]

    With no champion named, works on the champions player.txt lists as loved or liked. First
    writes whatever the augment map for this patch lacks (all of it again with --map), then
    each playbook that is missing (all of them again with --force). --show prints saved
    playbooks and asks for nothing.
    """
    from . import champfit
    from .static_data import StaticData
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    flags = {a for a in argv if a.startswith("--")}
    names = [a for a in argv if not a.startswith("--")]
    sd = StaticData()
    ids = [sd.champ_id(n) for n in names] if names else list(champfit.favourites(sd))
    unknown = [n for n, cid in zip(names, ids) if cid is None]
    if unknown:
        print("Unknown champions:", ", ".join(unknown))
        return 2
    if "--show" in flags:
        print("\n\n".join(show(sd, cid) for cid in ids))
        return 0
    if config.RESEARCH == "0":
        print("ARAMCOACH_RESEARCH=0: research is turned off.")
        return 2
    here = lambda name: (_folder(sd) / name).exists() and _load(sd, name) is not None      # written for this patch
    if "--map" in flags or map_missing(sd):
        print("Writing the augment map...")
        result = build_map(sd, fresh="--map" in flags)
        print(f"  {result['written']} augments in {result['latency']}s for ${result['cost']}"
              + (f"; not written: {', '.join(result['missing'])}" if result["missing"] else ""))
    todo = [cid for cid in ids if "--force" in flags or not here(f"champion_{cid}.json")]
    if todo:
        print("Writing playbooks for:", ", ".join(todo))
        for cid, result in build_champions(sd, todo):
            if isinstance(result, Exception):
                print(f"  {cid}: failed: {result}")
            else:
                print(f"  {cid}: {len(result['combos'])} combinations, {len(result['augments'])} augment entries, "
                      f"{result['latency']}s, ${result['cost']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
